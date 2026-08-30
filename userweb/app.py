import logging
import os
from pathlib import Path

import joblib
import numpy as np
import xgboost as xgb
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn.error")

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

app = FastAPI(title="MedVision Guard Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Feature order the model was trained on (New/train_risk_model.py FEATURE_COLS) —
# the model takes a positional vector, so this order must match exactly.
RISK_FEATURE_COLS = [
    "age", "spo2", "heart_rate", "resp_rate", "sys_bp", "dias_bp", "temp",
    "pain_score", "hist_asthma", "hist_diabetes", "hist_hypertension",
    "hist_cad", "hist_stroke",
]

RISK_MODEL_PATH = Path(__file__).parent / "models" / "risk_model.pkl"
try:
    risk_model = joblib.load(RISK_MODEL_PATH)
except FileNotFoundError:
    risk_model = None
    logger.warning("risk_model.pkl not found at %s — /analyze-vitals will run without risk scoring", RISK_MODEL_PATH)

# Trained on the project's patient_records dataset (see train_xgboost.py).
# Every response using it is still flagged "is_demo": true so the frontend
# can caveat it — it's a classifier trained for this project, not a
# clinically validated model.
SEVERITY_MODEL_PATH = Path(__file__).parent / "models" / "severity_model.json"
try:
    severity_model = xgb.XGBClassifier()
    severity_model.load_model(SEVERITY_MODEL_PATH)
except (FileNotFoundError, xgb.core.XGBoostError):
    severity_model = None
    logger.warning("severity_model.json not found at %s — /analyze-vitals will run without ML severity scoring", SEVERITY_MODEL_PATH)


class VitalsInput(BaseModel):
    patient_id: str = Field(..., min_length=1, max_length=64)
    age: int = Field(..., ge=0, le=130)
    spo2: float = Field(..., ge=0, le=100)
    heart_rate: float = Field(..., ge=0, le=300)
    systolic_bp: float = Field(..., ge=0, le=300)
    diastolic_bp: float = Field(..., ge=0, le=200)
    resp_rate: float = Field(..., ge=0, le=80)
    temp: float = Field(..., ge=30, le=45)
    pain_score: int = Field(..., ge=0, le=10)
    hist_asthma: bool = False
    hist_diabetes: bool = False
    hist_hypertension: bool = False
    hist_cad: bool = False
    hist_stroke: bool = False
    findings: str = Field("", max_length=4000)


def score_manual_vitals(spo2: float, heart_rate: float, systolic_bp: float, temp: float, age: int) -> int:
    """Simple rule-based triage score for manually-entered vitals. Each
    out-of-range vital adds to the score, clamped into a 1-5 severity scale."""
    score = 1
    if spo2 < 92:
        score += 2
    if heart_rate < 60 or heart_rate > 100:
        score += 1
    if systolic_bp < 90 or systolic_bp > 130:
        score += 1
    if temp < 35 or temp > 39.5:
        score += 2
    elif temp < 36 or temp > 38.5:
        score += 1
    if age >= 65:
        score += 1
    return max(1, min(5, score))


def score_disease_probabilities(spo2: float, heart_rate: float, systolic_bp: float, temp: float, age: int) -> dict:
    """Rule-based likelihood estimate across a fixed set of conditions, driven
    by how far vitals sit from normal ranges. This is a heuristic, not a
    trained model — there's no ML backend behind manually-entered vitals."""
    scores = {
        "Normal": 1.0,
        "Respiratory Infection": 0.0,
        "Cardiac Event": 0.0,
        "Sepsis": 0.0,
        "Hypertensive Crisis": 0.0,
    }

    if spo2 < 92:
        scores["Respiratory Infection"] += (92 - spo2) * 0.3
        scores["Sepsis"] += (92 - spo2) * 0.15

    if heart_rate > 100:
        scores["Cardiac Event"] += (heart_rate - 100) * 0.08
        scores["Sepsis"] += (heart_rate - 100) * 0.05
    elif heart_rate < 60:
        scores["Cardiac Event"] += (60 - heart_rate) * 0.1

    if systolic_bp > 130:
        scores["Hypertensive Crisis"] += (systolic_bp - 130) * 0.1
        scores["Cardiac Event"] += (systolic_bp - 130) * 0.03
    elif systolic_bp < 90:
        scores["Sepsis"] += (90 - systolic_bp) * 0.15
        scores["Cardiac Event"] += (90 - systolic_bp) * 0.05

    if temp > 38.5:
        scores["Respiratory Infection"] += (temp - 38.5) * 0.6
        scores["Sepsis"] += (temp - 38.5) * 0.5
    elif temp < 35:
        scores["Sepsis"] += (35 - temp) * 0.6

    if age >= 65:
        scores["Cardiac Event"] += 1.0

    abnormal_total = sum(v for k, v in scores.items() if k != "Normal")
    scores["Normal"] = max(0.1, 5.0 - abnormal_total)

    total = sum(scores.values())
    return {name: round(value / total, 4) for name, value in scores.items()}


def score_patient_risk(vitals: "VitalsInput") -> dict | None:
    """Runs the trained LightGBM model (New/train_risk_model.py) and derives a
    care plan from its risk score. Returns None if the model didn't load."""
    if risk_model is None:
        return None

    feature_values = {
        "age": vitals.age, "spo2": vitals.spo2, "heart_rate": vitals.heart_rate,
        "resp_rate": vitals.resp_rate, "sys_bp": vitals.systolic_bp, "dias_bp": vitals.diastolic_bp,
        "temp": vitals.temp, "pain_score": vitals.pain_score,
        "hist_asthma": int(vitals.hist_asthma), "hist_diabetes": int(vitals.hist_diabetes),
        "hist_hypertension": int(vitals.hist_hypertension), "hist_cad": int(vitals.hist_cad),
        "hist_stroke": int(vitals.hist_stroke),
    }
    x = np.array([[feature_values[col] for col in RISK_FEATURE_COLS]], dtype=np.float32)
    risk_score = round(float(risk_model.predict_proba(x)[0][1]) * 100, 2)

    return {
        "risk_score": risk_score,
        **generate_care_plan(risk_score, vitals.age),
    }


SEVERITY_ML_LABELS = {1: "Non-Urgent", 2: "Low", 3: "Moderate", 4: "High", 5: "Critical"}


def score_severity_ml(vitals: "VitalsInput") -> dict | None:
    """Runs the XGBoost severity classifier (train_xgboost.py) — see the
    module-level comment on severity_model. Returns None if the model
    didn't load."""
    if severity_model is None:
        return None

    feature_values = {
        "age": vitals.age, "spo2": vitals.spo2, "heart_rate": vitals.heart_rate,
        "resp_rate": vitals.resp_rate, "sys_bp": vitals.systolic_bp, "dias_bp": vitals.diastolic_bp,
        "temp": vitals.temp, "pain_score": vitals.pain_score,
        "hist_asthma": int(vitals.hist_asthma), "hist_diabetes": int(vitals.hist_diabetes),
        "hist_hypertension": int(vitals.hist_hypertension), "hist_cad": int(vitals.hist_cad),
        "hist_stroke": int(vitals.hist_stroke),
    }
    x = np.array([[feature_values[col] for col in RISK_FEATURE_COLS]], dtype=np.float32)
    proba = severity_model.predict_proba(x)[0]
    predicted_class = int(np.argmax(proba))
    # train_xgboost.py labels classes as (raw_acuity 1-5) -> LabelEncoder ->
    # contiguous 0-4 in ascending order, so class index + 1 recovers the 1-5
    # inverted-acuity scale (5 = most severe), same convention as SEVERITY_MAP.
    level = predicted_class + 1

    return {
        "level": level,
        "label": SEVERITY_ML_LABELS.get(level, "Unknown"),
        "confidence": round(float(proba[predicted_class]) * 100, 1),
        "is_demo": True,
        "note": "Model prediction, not a clinical diagnosis — a clinician makes the final call.",
    }


def generate_care_plan(risk_score: float, age: int) -> dict:
    """Ported from New/train_risk_model.py's generate_recommendation()."""
    if risk_score >= 85:
        recommendation = ["Immediate senior clinical review", "Continuous monitoring", "ICU evaluation"]
        estimated_stay = "5-7+ days" if age >= 75 else "4-6 days" if age >= 60 else "3-5 days"
        return {"recommendation": recommendation, "monitoring": "Continuous",
                "estimated_stay": estimated_stay, "disposition": "Hospital admission"}
    if risk_score >= 70:
        recommendation = ["Hospital admission recommended", "Close clinical monitoring", "Senior clinical review"]
        estimated_stay = "4-6 days" if age >= 75 else "3-5 days" if age >= 60 else "2-4 days"
        return {"recommendation": recommendation, "monitoring": "Every 1-2 hours",
                "estimated_stay": estimated_stay, "disposition": "Hospital admission"}
    if risk_score >= 40:
        recommendation = ["Continue hospital observation", "Repeat vital-sign assessment",
                           "Clinical reassessment before discharge"]
        if age >= 75:
            monitoring, estimated_stay = "Every 2 hours", "1-3 days"
        elif age >= 60:
            monitoring, estimated_stay = "Every 2-4 hours", "12-48 hours"
        else:
            monitoring, estimated_stay = "Every 4 hours", "Observation only"
        return {"recommendation": recommendation, "monitoring": monitoring,
                "estimated_stay": estimated_stay, "disposition": "Observation"}
    recommendation = ["Routine monitoring", "Reassess vital signs", "Consider discharge if clinically stable"]
    if age >= 75:
        monitoring, estimated_stay = "Every 4 hours", "12-24 hours observation"
    elif age >= 60:
        monitoring, estimated_stay = "Every 4-6 hours", "6-12 hours observation"
    else:
        monitoring, estimated_stay = "Every 6 hours", "May discharge after monitoring"
    return {"recommendation": recommendation, "monitoring": monitoring,
            "estimated_stay": estimated_stay, "disposition": "Possible discharge after observation"}


@app.get("/")
def health():
    return {
        "status": "active",
        "system": "MedVision Guard Engine",
        "risk_model_loaded": risk_model is not None,
        "severity_model_loaded": severity_model is not None,
    }


@app.post("/analyze-vitals")
def analyze_vitals(vitals: VitalsInput):
    patient_id = vitals.patient_id.strip()
    if not patient_id:
        raise HTTPException(status_code=422, detail="patient_id is required")

    severity_level = score_manual_vitals(vitals.spo2, vitals.heart_rate, vitals.systolic_bp, vitals.temp, vitals.age)
    disease_probabilities = score_disease_probabilities(
        vitals.spo2, vitals.heart_rate, vitals.systolic_bp, vitals.temp, vitals.age
    )
    risk = score_patient_risk(vitals)
    severity_ml = score_severity_ml(vitals)

    return {
        "status": "success",
        "parsed_vitals": {
            "patient_id": patient_id,
            "age": vitals.age,
            "spo2": vitals.spo2,
            "heart_rate": vitals.heart_rate,
            "systolic_bp": vitals.systolic_bp,
            "diastolic_bp": vitals.diastolic_bp,
            "resp_rate": vitals.resp_rate,
            "temp": vitals.temp,
            "pain_score": vitals.pain_score,
            "hist_asthma": vitals.hist_asthma,
            "hist_diabetes": vitals.hist_diabetes,
            "hist_hypertension": vitals.hist_hypertension,
            "hist_cad": vitals.hist_cad,
            "hist_stroke": vitals.hist_stroke,
            "findings": vitals.findings.strip(),
        },
        "triage_severity_level": severity_level,
        "disease_probabilities": disease_probabilities,
        "risk_assessment": risk,
        "severity_assessment_ml": severity_ml,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
