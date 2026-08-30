import os
import json
import joblib
import xgboost as xgb
import numpy as np
import hashlib
from typing import Dict, Any, Tuple, Optional
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from supabase import create_client, Client

# torch/transformers are only needed for the DistilBERT NLP path, which has
# no real checkpoint committed to this repo yet and always falls back to
# keyword heuristics. Importing them unconditionally costs several hundred
# MB of RAM just to sit unused — enough on its own to OOM-kill a 512MB
# deployment (confirmed on Render). Import lazily so a deployment without
# them installed still runs; DistilBERT loading below already falls back
# gracefully via its own try/except when these are None.
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
except ImportError:
    torch = None
    AutoTokenizer = None
    AutoModelForSequenceClassification = None

load_dotenv()

# ── Model paths ───────────────────────────────────────────────────────────────
# DistilBERT checkpoint produced by train_custom_nlp.py (results/checkpoint-600)
DISTILBERT_PATH  = os.getenv("DISTILBERT_PATH",  "./results/checkpoint-600")
ENCODER_PATH     = os.getenv("ENCODER_PATH",     "./disease_label_encoder.pkl")

# XGBoost saved via model.save_model() in train_xgboost.py  →  native JSON
SEVERITY_MODEL_PATH = os.getenv("SEVERITY_MODEL_PATH", "./models/severity_model.json")

# LightGBM binary classifier trained in New/train_risk_model.py
RISK_MODEL_PATH  = os.getenv("RISK_MODEL_PATH",  "./models/risk_model.pkl")

# Feature columns — must match both training scripts exactly (13 features)
FEATURE_COLS = [
    "age", "spo2", "heart_rate", "resp_rate",
    "sys_bp", "dias_bp", "temp", "pain_score",
    "hist_asthma", "hist_diabetes", "hist_hypertension",
    "hist_cad", "hist_stroke",
]

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://your-supabase-project.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your-anon-key")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="MedVision Health Analytics Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Health Consensus Engine ───────────────────────────────────────────────────
class HealthConsensusEngine:
    """Orchestrates DistilBERT, XGBoost and LightGBM for triage inference."""

    def __init__(self):
        # Populated with the exception text on failure, so it can be surfaced
        # via GET / without needing access to server logs.
        self.distilbert_error = None
        self.xgb_error = None
        self.lgb_error = None

        # ── DistilBERT (NLP disease classification) ──────────────────────────
        self.tokenizer = None
        self.distilbert_model = None
        self.label_encoder = None
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(DISTILBERT_PATH)
            self.distilbert_model = AutoModelForSequenceClassification.from_pretrained(
                DISTILBERT_PATH
            )
            self.distilbert_model.eval()
            self.label_encoder = joblib.load(ENCODER_PATH)
            print(f"[OK] DistilBERT loaded from '{DISTILBERT_PATH}'")
        except Exception as e:
            self.distilbert_error = f"{type(e).__name__}: {e}"
            print(f"[WARN] DistilBERT not loaded — falling back to rule-based NLP. ({e})")

        # ── XGBoost (ESI acuity classifier, native JSON format) ──────────────
        self.xgb_model = None
        try:
            self.xgb_model = xgb.XGBClassifier()
            self.xgb_model.load_model(SEVERITY_MODEL_PATH)
            print(f"[OK] XGBoost loaded from '{SEVERITY_MODEL_PATH}'")
        except Exception as e:
            self.xgb_error = f"{type(e).__name__}: {e}"
            print(f"[WARN] XGBoost not loaded — falling back to rule-based acuity. ({e})")

        # ── LightGBM (binary risk classifier → ICU risk probability) ─────────
        self.lgb_model = None
        try:
            self.lgb_model = joblib.load(RISK_MODEL_PATH)
            print(f"[OK] LightGBM loaded from '{RISK_MODEL_PATH}'")
        except Exception as e:
            self.lgb_error = f"{type(e).__name__}: {e}"
            print(f"[WARN] LightGBM not loaded — falling back to rule-based risk. ({e})")

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def hash_patient_id(raw_id: str) -> str:
        return hashlib.sha256(raw_id.encode()).hexdigest()[:16]

    @staticmethod
    def identify_subsystem(text: str) -> str:
        t = text.lower()
        if any(w in t for w in ["breath", "cough", "lung", "wheeze", "asthma", "spo2"]):
            return "PULMONARY"
        if any(w in t for w in ["chest", "heart", "bp", "palpitations", "cardiac"]):
            return "CARDIOVASCULAR"
        if any(w in t for w in ["headache", "seizure", "numb", "dizzy", "stroke", "slurred"]):
            return "NEUROLOGICAL"
        if any(w in t for w in ["fracture", "cut", "wound", "bleed", "trauma", "laceration"]):
            return "TRAUMA"
        return "GENERAL TRIAGE"

    # ── NLP disease prediction ────────────────────────────────────────────────
    def predict_nlp_disease(self, complaint_text: str) -> Tuple[str, float, str]:
        """Returns (condition, confidence, subsystem). Uses DistilBERT when available,
        otherwise falls back to keyword heuristics."""
        subsystem = self.identify_subsystem(complaint_text)

        if self.distilbert_model and self.tokenizer and self.label_encoder:
            try:
                inputs = self.tokenizer(
                    complaint_text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=128,
                )
                with torch.no_grad():
                    logits = self.distilbert_model(**inputs).logits
                    probs = torch.nn.functional.softmax(logits, dim=-1)
                    conf_tensor, pred = torch.max(probs, dim=-1)
                conf = round(float(conf_tensor.item()), 4)
                if conf >= 0.50:
                    condition = self.label_encoder.inverse_transform([pred.item()])[0]
                    return condition, conf, subsystem
                print(f"[INFO] DistilBERT conf={conf:.3f} < 0.50, using keyword fallback.")
            except Exception as e:
                print(f"[WARN] DistilBERT inference failed: {e}")

        # Rule-based fallback
        t = complaint_text.lower()
        if "chest pain" in t or "cardiac" in t or "substernal" in t:
            return "Acute Coronary Syndrome", 0.94, subsystem
        if "dyspnea" in t or "wheez" in t or "breath" in t:
            return "Acute Asthma / COPD Exacerbation", 0.91, subsystem
        if "slurred" in t or "facial drooping" in t or "numb" in t:
            return "Acute Ischemic Stroke", 0.96, subsystem
        if "trauma" in t or "laceration" in t or "hemorrhage" in t:
            return "Polytrauma / Severe Hemorrhage", 0.89, subsystem
        if "fever" in t or "cough" in t or "sputum" in t:
            return "Bacterial Pneumonia", 0.87, subsystem
        return "Acute General Febrile Illness", 0.82, subsystem

    # ── Tabular predictions ───────────────────────────────────────────────────
    def predict_tabular_metrics(self, vitals: Dict[str, Any]) -> Tuple[int, float, float]:
        """Returns (esi_level, los_days, icu_risk)."""
        feature_vector = np.array([[
            float(vitals.get("age",               45)),
            float(vitals.get("spo2",              98.0)),
            float(vitals.get("heart_rate",        75.0)),
            float(vitals.get("resp_rate",         16.0)),
            float(vitals.get("sys_bp",            120.0)),
            float(vitals.get("dias_bp",           80.0)),
            float(vitals.get("temperature",       37.0)),
            float(vitals.get("pain_score",        3)),
            float(vitals.get("hist_asthma",       0)),
            float(vitals.get("hist_diabetes",     0)),
            float(vitals.get("hist_hypertension", 0)),
            float(vitals.get("hist_cad",          0)),
            float(vitals.get("hist_stroke",       0)),
        ]], dtype=np.float32)

        spo2     = feature_vector[0][1]
        sys_bp   = feature_vector[0][4]
        pain     = feature_vector[0][7]

        # ── ESI level via XGBoost ─────────────────────────────────────────────
        esi_level = None
        if self.xgb_model is not None:
            try:
                raw_class = int(self.xgb_model.predict(feature_vector)[0])
                esi_level = max(1, min(5, 5 - raw_class))
            except Exception as e:
                print(f"[WARN] XGBoost predict failed: {e}")

        if esi_level is None:
            if spo2 < 90 or sys_bp < 90:
                esi_level = 1
            elif pain >= 8:
                esi_level = 2
            else:
                esi_level = 3

        # ── ICU risk via LightGBM ─────────────────────────────────────────────
        icu_risk = None
        if self.lgb_model is not None:
            try:
                icu_risk = round(float(self.lgb_model.predict_proba(feature_vector)[0][1]), 4)
            except Exception as e:
                print(f"[WARN] LightGBM predict failed: {e}")

        if icu_risk is None:
            icu_risk = 0.88 if (spo2 < 90 and sys_bp < 90) else 0.12

        # ── Length of stay (derived from ESI) ─────────────────────────────────
        los_map = {1: 6.0, 2: 4.0, 3: 2.5, 4: 1.5, 5: 0.5}
        los_days = los_map.get(esi_level, 2.5)

        return esi_level, los_days, icu_risk


# ── Singleton instances ───────────────────────────────────────────────────────
engine = HealthConsensusEngine()

try:
    if SUPABASE_URL and not SUPABASE_URL.startswith("https://your-supabase-project"):
        supabase: Optional[Client] = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[OK] Supabase client connected successfully.")
    else:
        supabase = None
        print("[WARN] Supabase placeholder credentials detected. DB persistence disabled.")
except Exception as e:
    supabase = None
    print(f"[WARN] Failed to connect to Supabase: {e}")


# ── Pydantic models ───────────────────────────────────────────────────────────
class ComplaintPayload(BaseModel):
    chief_complaint_text: str


class TriagePayload(BaseModel):
    patient_id: str
    chief_complaint_text: str
    dynamic_vitals: dict


# ── /analyze-vitals compatibility layer ───────────────────────────────────────
# Mirrors userweb/app.py's request/response contract exactly, so the existing
# frontend (userweb/frontend) can point at this backend with zero changes.
# Reuses the same rule-based scoring logic and the same loaded xgb_model /
# lgb_model instances as the HealthConsensusEngine above.


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


SEVERITY_ML_LABELS = {1: "Non-Urgent", 2: "Low", 3: "Moderate", 4: "High", 5: "Critical"}


def score_patient_risk(vitals: VitalsInput) -> dict | None:
    """Runs engine.lgb_model and derives a care plan from its risk score.
    Returns None if the model didn't load."""
    if engine.lgb_model is None:
        return None

    feature_values = {
        "age": vitals.age, "spo2": vitals.spo2, "heart_rate": vitals.heart_rate,
        "resp_rate": vitals.resp_rate, "sys_bp": vitals.systolic_bp, "dias_bp": vitals.diastolic_bp,
        "temp": vitals.temp, "pain_score": vitals.pain_score,
        "hist_asthma": int(vitals.hist_asthma), "hist_diabetes": int(vitals.hist_diabetes),
        "hist_hypertension": int(vitals.hist_hypertension), "hist_cad": int(vitals.hist_cad),
        "hist_stroke": int(vitals.hist_stroke),
    }
    x = np.array([[feature_values[col] for col in FEATURE_COLS]], dtype=np.float32)
    risk_score = round(float(engine.lgb_model.predict_proba(x)[0][1]) * 100, 2)

    return {
        "risk_score": risk_score,
        **generate_care_plan(risk_score, vitals.age),
    }


def score_severity_ml(vitals: VitalsInput) -> dict | None:
    """Runs engine.xgb_model. Returns None if the model didn't load."""
    if engine.xgb_model is None:
        return None

    feature_values = {
        "age": vitals.age, "spo2": vitals.spo2, "heart_rate": vitals.heart_rate,
        "resp_rate": vitals.resp_rate, "sys_bp": vitals.systolic_bp, "dias_bp": vitals.diastolic_bp,
        "temp": vitals.temp, "pain_score": vitals.pain_score,
        "hist_asthma": int(vitals.hist_asthma), "hist_diabetes": int(vitals.hist_diabetes),
        "hist_hypertension": int(vitals.hist_hypertension), "hist_cad": int(vitals.hist_cad),
        "hist_stroke": int(vitals.hist_stroke),
    }
    x = np.array([[feature_values[col] for col in FEATURE_COLS]], dtype=np.float32)
    proba = engine.xgb_model.predict_proba(x)[0]
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


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def read_root():
    return {
        "message": "MedVision Engine Running.",
        "models": {
            "distilbert": engine.distilbert_model is not None,
            "xgboost": engine.xgb_model is not None,
            "lightgbm": engine.lgb_model is not None,
        },
        "model_errors": {
            "distilbert": engine.distilbert_error,
            "xgboost": engine.xgb_error,
            "lightgbm": engine.lgb_error,
        },
        "supabase_connected": supabase is not None,
    }


@app.post("/api/patient/analyze-complaint")
async def analyze_complaint(payload: ComplaintPayload):
    subsystem = engine.identify_subsystem(payload.chief_complaint_text)
    required_vitals = [
        "age", "heart_rate", "sys_bp", "dias_bp",
        "spo2", "temperature", "pain_score",
        "resp_rate",
        "hist_asthma", "hist_diabetes",
        "hist_hypertension", "hist_cad", "hist_stroke",
    ]
    return {"subsystem": subsystem, "required_vitals": required_vitals}


@app.post("/api/patient/evaluate-triage")
async def evaluate_triage(payload: TriagePayload):
    try:
        nlp_condition, nlp_conf, subsystem = engine.predict_nlp_disease(
            payload.chief_complaint_text
        )
        esi_level, stay_days, icu_risk = engine.predict_tabular_metrics(
            payload.dynamic_vitals
        )

        esi_map = {
            1: "Level 1 (Immediate / Resuscitation)",
            2: "Level 2 (Emergent)",
            3: "Level 3 (Urgent)",
            4: "Level 4 (Less Urgent)",
            5: "Level 5 (Non-Urgent)",
        }
        esi_label = esi_map.get(esi_level, f"Level {esi_level}")
        recommendation = (
            "Reserve ICU Bed Immediately"
            if esi_level <= 2
            else "Assign to General Triage / Monitoring"
        )
        patient_hash = engine.hash_patient_id(payload.patient_id)

        # Database Logging via Supabase
        if supabase:
            try:
                supabase.table("master_patient_triage").insert({
                    "patient_id":       patient_hash,
                    "chief_complaint":  payload.chief_complaint_text,
                    "vitals_json":      json.dumps(payload.dynamic_vitals),
                    "esi_predicted":    esi_level,
                    "patient_hash":     patient_hash,
                }).execute()
            except Exception as db_err:
                print(f"[WARN] Supabase write failed: {db_err}")

        return {
            "status":         "success",
            "patient_hash":   patient_hash,
            "recommendation": recommendation,
            "subsystem":      subsystem,
            "predictions": {
                "nlp_disease": {
                    "predicted_condition": nlp_condition,
                    "confidence":          nlp_conf,
                },
                "xgboost_acuity": {
                    "esi_level":      esi_level,
                    "severity_label": esi_label,
                },
                "lightgbm_risk": {
                    "estimated_stay_days":  stay_days,
                    "icu_admission_risk":   icu_risk,
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze-vitals")
def analyze_vitals(vitals: VitalsInput):
    """Same request/response contract as userweb/app.py's /analyze-vitals,
    so the existing frontend can point at this backend unchanged."""
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


# ── New Supabase Retrieval Endpoints for Frontend / Claude Code ───────────────
@app.get("/api/patient/records")
async def get_all_records(limit: int = Query(50, ge=1, le=200)):
    """Fetches recent triage audit records for the frontend dashboard."""
    if not supabase:
        raise HTTPException(
            status_code=503,
            detail="Supabase client not connected. Ensure SUPABASE_URL and SUPABASE_KEY are configured in .env"
        )
    try:
        response = (
            supabase.table("master_patient_triage")
            .select("*")
            .limit(limit)
            .execute()
        )
        return {"status": "success", "count": len(response.data), "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch records: {str(e)}")


@app.get("/api/patient/records/{patient_id}")
async def get_patient_history(patient_id: str):
    """Fetches historical triage records for a specific patient."""
    if not supabase:
        raise HTTPException(
            status_code=503,
            detail="Supabase client not connected. Ensure SUPABASE_URL and SUPABASE_KEY are configured in .env"
        )
    try:
        p_hash = engine.hash_patient_id(patient_id)
        response = (
            supabase.table("master_patient_triage")
            .select("*")
            .or_(f"patient_id.eq.{patient_id},patient_hash.eq.{p_hash}")
            .execute()
        )
        return {"status": "success", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch patient history: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)