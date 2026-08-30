import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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


class VitalsInput(BaseModel):
    patient_id: str = Field(..., min_length=1, max_length=64)
    age: int = Field(..., ge=0, le=130)
    spo2: float = Field(..., ge=0, le=100)
    heart_rate: float = Field(..., ge=0, le=300)
    systolic_bp: float = Field(..., ge=0, le=300)
    findings: str = Field("", max_length=4000)


def score_manual_vitals(spo2: float, heart_rate: float, systolic_bp: float, age: int) -> int:
    """Simple rule-based triage score for manually-entered vitals. Each
    out-of-range vital adds to the score, clamped into a 1-5 severity scale."""
    score = 1
    if spo2 < 92:
        score += 2
    if heart_rate < 60 or heart_rate > 100:
        score += 1
    if systolic_bp < 90 or systolic_bp > 130:
        score += 1
    if age >= 65:
        score += 1
    return max(1, min(5, score))


def score_disease_probabilities(spo2: float, heart_rate: float, systolic_bp: float, age: int) -> dict:
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

    if age >= 65:
        scores["Cardiac Event"] += 1.0

    abnormal_total = sum(v for k, v in scores.items() if k != "Normal")
    scores["Normal"] = max(0.1, 5.0 - abnormal_total)

    total = sum(scores.values())
    return {name: round(value / total, 4) for name, value in scores.items()}


@app.get("/")
def health():
    return {"status": "active", "system": "MedVision Guard Engine"}


@app.post("/analyze-vitals")
def analyze_vitals(vitals: VitalsInput):
    patient_id = vitals.patient_id.strip()
    if not patient_id:
        raise HTTPException(status_code=422, detail="patient_id is required")

    severity_level = score_manual_vitals(vitals.spo2, vitals.heart_rate, vitals.systolic_bp, vitals.age)
    disease_probabilities = score_disease_probabilities(vitals.spo2, vitals.heart_rate, vitals.systolic_bp, vitals.age)

    return {
        "status": "success",
        "parsed_vitals": {
            "patient_id": patient_id,
            "age": vitals.age,
            "spo2": vitals.spo2,
            "heart_rate": vitals.heart_rate,
            "systolic_bp": vitals.systolic_bp,
            "findings": vitals.findings.strip(),
        },
        "triage_severity_level": severity_level,
        "disease_probabilities": disease_probabilities,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
