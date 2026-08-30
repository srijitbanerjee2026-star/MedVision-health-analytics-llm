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

load_dotenv()

# ── Model paths ───────────────────────────────────────────────────────────────
# Both models live in the root-level models/ directory (see models/README or
# git history — they used to live under userweb/models/ before app.py was
# retired). Pointing anywhere else silently falls back to rule-based scoring.
SEVERITY_MODEL_PATH = os.getenv("SEVERITY_MODEL_PATH", "./models/severity_model.json")
RISK_MODEL_PATH     = os.getenv("RISK_MODEL_PATH",     "./models/risk_model.pkl")

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
    """Orchestrates Semantic Clinical NLP, XGBoost, and LightGBM for triage inference."""

    def __init__(self):
        # Populated with the exception text on failure, so it can be surfaced
        # via GET / without needing access to server logs.
        self.xgb_error = None
        self.lgb_error = None

        # ── XGBoost (ESI acuity classifier) ─────────────────────────────────
        self.xgb_model = None
        try:
            self.xgb_model = xgb.XGBClassifier()
            self.xgb_model.load_model(SEVERITY_MODEL_PATH)
            print(f"[OK] XGBoost loaded from '{SEVERITY_MODEL_PATH}'")
        except Exception as e:
            self.xgb_error = f"{type(e).__name__}: {e}"
            print(f"[WARN] XGBoost not loaded — falling back to rule-based acuity. ({e})")

        # ── LightGBM (binary risk classifier) ────────────────────────────────
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
        if any(w in t for w in ["breath", "cough", "lung", "wheeze", "asthma", "spo2", "respiratory", "choking", "stridor", "sputum", "pneumo"]):
            return "PULMONARY"
        if any(w in t for w in ["chest", "heart", "bp", "palpitations", "cardiac", "angina", "aortic", "bradycardia", "tachycardia", "edema"]):
            return "CARDIOVASCULAR"
        if any(w in t for w in ["headache", "seizure", "numb", "dizzy", "stroke", "slurred", "vision", "syncope", "faint", "vertigo", "palsy"]):
            return "NEUROLOGICAL"
        if any(w in t for w in ["abdomen", "stomach", "vomit", "nausea", "diarrhea", "bowel", "appendix", "liver", "epigastric", "jaundice", "melena"]):
            return "GASTROINTESTINAL"
        if any(w in t for w in ["fracture", "cut", "wound", "bleed", "trauma", "laceration", "burn", "stab", "accident", "torsion", "sprain"]):
            return "TRAUMA"
        return "GENERAL TRIAGE"

    # Flat, order-independent condition list — every entry is checked against
    # every complaint regardless of category, and the entry with the MOST
    # matching keywords wins (ties broken by list order below). The previous
    # version nested these under a per-category "or" gate and returned on the
    # first category whose broad, single-keyword trigger matched (e.g. any
    # mention of "chest" routed straight into Cardiovascular, "breath"
    # anywhere — including inside "breathing" — routed into Pulmonary), so a
    # complaint could never reach a more specific, correct condition in a
    # later-checked category. See: an appendicitis complaint ("right lower
    # quadrant", "rebound") fell through to the generic fallback because it
    # never said "abdomen"/"stomach"; a DKA complaint ("fruity breath...")
    # got diagnosed as generic Pulmonary distress because "breathing"
    # contains "breath"; a PE complaint got diagnosed as Pericarditis because
    # both share the keyword "pleuritic" but Cardiovascular was checked first.
    _CONDITIONS = [
        # ── CARDIOVASCULAR ──────────────────────────────────────────
        (["crushing", "retrosternal", "arm", "jaw", "diaphoresis", "substernal"],
         "Acute Coronary Syndrome (STEMI / NSTEMI)", 0.94, "CARDIOVASCULAR"),
        (["tearing", "back", "shoulder blades", "aortic"],
         "Acute Aortic Dissection", 0.92, "CARDIOVASCULAR"),
        (["palpitation", "rapid heartbeat", "rapid heart rate", "racing heart", "irregular heartbeat", "flutter"],
         "Supraventricular / Atrial Arrhythmia", 0.88, "CARDIOVASCULAR"),
        (["edema", "orthopnea", "nocturnal", "swelling"],
         "Decompensated Congestive Heart Failure", 0.89, "CARDIOVASCULAR"),
        (["pleuritic", "leaning forward", "pericard"],
         "Acute Pericarditis", 0.86, "CARDIOVASCULAR"),
        (["bradycardia", "dizziness", "faint", "syncope"],
         "Symptomatic Bradycardia / AV Block", 0.91, "CARDIOVASCULAR"),
        (["calf", "dvt", "flight", "leg swelling"],
         "Deep Vein Thrombosis (DVT)", 0.87, "CARDIOVASCULAR"),
        (["pulseless", "cold", "pale leg", "ischemia"],
         "Acute Peripheral Arterial Occlusion", 0.93, "CARDIOVASCULAR"),

        # ── PULMONARY ───────────────────────────────────────────────
        (["stridor", "peanut", "throat tightness", "swelling", "anaphylaxis"],
         "Acute Anaphylaxis / Airway Compromise", 0.96, "PULMONARY"),
        (["hemoptysis", "coughing up blood", "pleuritic", "sudden dyspnea", "sudden onset dyspnea"],
         "Acute Pulmonary Embolism", 0.93, "PULMONARY"),
        (["wheez", "asthma", "unable to speak"],
         "Acute Severe Asthma Exacerbation", 0.92, "PULMONARY"),
        (["rust", "fever", "productive", "sputum"],
         "Community-Acquired Bacterial Pneumonia", 0.90, "PULMONARY"),
        (["unilateral", "tall", "slim", "pneumothorax"],
         "Spontaneous Pneumothorax", 0.89, "PULMONARY"),
        (["copd", "smoker", "purulence"],
         "Acute Exacerbation of COPD", 0.91, "PULMONARY"),
        (["night sweats", "bloody streaks", "weight loss"],
         "Pulmonary Tuberculosis / Chronic Cavitary Infection", 0.88, "PULMONARY"),
        (["foreign body", "choking", "barking"],
         "Foreign Body Airway Obstruction", 0.94, "PULMONARY"),
        (["rhinorrhea", "sore throat", "runny"],
         "Upper Respiratory Tract Infection (URTI)", 0.95, "PULMONARY"),

        # ── NEUROLOGICAL ────────────────────────────────────────────
        (["facial drooping", "arm weakness", "slurred", "speech"],
         "Acute Ischemic Stroke (CVA)", 0.97, "NEUROLOGICAL"),
        (["thunderclap", "worst headache", "neck stiffness"],
         "Subarachnoid Hemorrhage (SAH)", 0.95, "NEUROLOGICAL"),
        (["tonic-clonic", "seizure", "convulsion"],
         "Status Epilepticus / Generalized Seizure", 0.94, "NEUROLOGICAL"),
        (["kernig", "photophobia", "mening"],
         "Acute Bacterial Meningitis", 0.93, "NEUROLOGICAL"),
        (["ascending", "weakness", "numbness"],
         "Guillain-Barré Syndrome", 0.87, "NEUROLOGICAL"),
        (["asterixis", "liver failure", "cirrhosis"],
         "Hepatic Encephalopathy", 0.89, "NEUROLOGICAL"),
        (["vertigo", "nystagmus", "rotary"],
         "Benign Paroxysmal Positional Vertigo (BPPV)", 0.90, "NEUROLOGICAL"),
        (["facial nerve", "forehead", "bell"],
         "Bell's Palsy (Peripheral Facial Neuropathy)", 0.91, "NEUROLOGICAL"),
        (["throbbing", "unilateral headache", "aura"],
         "Acute Migraine with Photophobia", 0.92, "NEUROLOGICAL"),
        (["tension", "band-like", "workday"],
         "Tension-Type Headache", 0.94, "NEUROLOGICAL"),

        # ── GASTROINTESTINAL ────────────────────────────────────────
        (["right lower quadrant", "rebound", "appendix"],
         "Acute Appendicitis", 0.95, "GASTROINTESTINAL"),
        (["hematemesis", "melena", "coffee ground"],
         "Upper Gastrointestinal Bleed", 0.94, "GASTROINTESTINAL"),
        (["epigastric", "radiating to back", "pancrea"],
         "Acute Pancreatitis", 0.92, "GASTROINTESTINAL"),
        (["murphy", "fatty meal", "right upper quadrant", "cholecyst"],
         "Acute Cholecystitis / Biliary Colic", 0.91, "GASTROINTESTINAL"),
        (["distension", "bilious", "obstipation", "obstruction"],
         "Acute Mechanical Bowel Obstruction", 0.93, "GASTROINTESTINAL"),
        (["left lower quadrant", "diverticul"],
         "Acute Diverticulitis", 0.90, "GASTROINTESTINAL"),
        (["jaundice", "clay-colored", "dark urine"],
         "Obstructive Jaundice / Cholangitis", 0.89, "GASTROINTESTINAL"),
        (["hematochezia", "bright red", "rectal"],
         "Lower Gastrointestinal Bleed", 0.91, "GASTROINTESTINAL"),
        (["diarrhea", "street food", "cramping"],
         "Acute Infectious Gastroenteritis", 0.94, "GASTROINTESTINAL"),
        (["pyrosis", "reflux", "regurgitation"],
         "Gastroesophageal Reflux Disease (GERD)", 0.92, "GASTROINTESTINAL"),

        # ── TRAUMA & ACUTE EMERGENCIES ──────────────────────────────
        (["collision", "steering wheel", "deformed"],
         "Polytrauma with Suspected Femur Fracture", 0.96, "TRAUMA"),
        (["pulsatile", "arterial", "laceration", "bleed"],
         "Major Arterial Vascular Injury", 0.95, "TRAUMA"),
        (["burn", "body surface area"],
         "Severe Thermal Burn Injury", 0.97, "TRAUMA"),
        (["septic", "purpuric", "obtunded"],
         "Septic Shock / Disseminated Meningococcemia", 0.98, "TRAUMA"),
        (["flank", "groin", "hematuria", "calculus", "stone"],
         "Acute Nephrolithiasis (Renal Colic)", 0.93, "TRAUMA"),
        (["kussmaul", "fruity", "ketoacidosis"],
         "Diabetic Ketoacidosis (DKA)", 0.96, "TRAUMA"),
        (["torsion", "scrotal", "testicular"],
         "Acute Testicular Torsion (Surgical Emergency)", 0.97, "TRAUMA"),
        (["ankle", "twisted", "sprain"],
         "Acute Ankle Ligament Sprain", 0.94, "TRAUMA"),
        (["paper cut"],
         "Superficial Cutaneous Abrasion", 0.99, "TRAUMA"),
        (["conjunctivitis", "itchy", "watery eyes"],
         "Allergic Conjunctivitis", 0.95, "TRAUMA"),
    ]

    # How many conditions above list each keyword — used to down-weight
    # keywords shared across conditions (see predict_nlp_disease).
    _KEYWORD_FREQUENCY: Dict[str, int] = {}
    for _keywords, *_rest in _CONDITIONS:
        for _kw in _keywords:
            _KEYWORD_FREQUENCY[_kw] = _KEYWORD_FREQUENCY.get(_kw, 0) + 1
    del _keywords, _rest, _kw

    # Generic per-subsystem fallback used only when no specific condition
    # above matched, but identify_subsystem() still recognized a broad
    # category keyword (e.g. "chest" with nothing more specific).
    _SUBSYSTEM_FALLBACK = {
        "CARDIOVASCULAR": ("Acute Coronary Syndrome", 0.85),
        "PULMONARY": ("Acute Respiratory Distress", 0.86),
        "NEUROLOGICAL": ("Acute Neurological Deficit", 0.85),
        "GASTROINTESTINAL": ("Acute Abdominal Pathology", 0.85),
        "TRAUMA": ("Acute Trauma / Hemorrhage", 0.88),
    }

    # ── Subsystem-Aware Clinical Pattern NLP Classifier ───────────────────────
    def predict_nlp_disease(self, complaint_text: str) -> Tuple[str, float, str]:
        """Classifies clinical condition across multi-organ specialties.

        Scores every known condition by how many of its keywords appear in
        the complaint and returns the best match, rather than gating checks
        behind a single-keyword category guess (see _CONDITIONS docstring)."""
        t = complaint_text.lower()

        # Weight each keyword match by 1/(number of conditions it appears in)
        # so a keyword shared across conditions (e.g. "pleuritic" appearing
        # for both Pericarditis and Pulmonary Embolism) can't single-handedly
        # win a match the way a keyword unique to one condition can.
        best_match = None
        best_score = 0.0
        for keywords, condition, confidence, subsystem in self._CONDITIONS:
            score = sum(1.0 / self._KEYWORD_FREQUENCY.get(k, 1) for k in keywords if k in t)
            if score > best_score:
                best_score = score
                best_match = (condition, confidence, subsystem)

        if best_match:
            return best_match

        subsystem = self.identify_subsystem(complaint_text)
        if subsystem in self._SUBSYSTEM_FALLBACK:
            condition, confidence = self._SUBSYSTEM_FALLBACK[subsystem]
            return condition, confidence, subsystem

        return "Acute Undifferentiated Febrile Illness", 0.82, "GENERAL TRIAGE"

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

        spo2   = feature_vector[0][1]
        sys_bp = feature_vector[0][4]
        pain   = feature_vector[0][7]

        # ── ESI level via XGBoost ─────────────────────────────────────────────
        esi_level = None
        if self.xgb_model is not None:
            try:
                raw_class = int(self.xgb_model.predict(feature_vector)[0])
                esi_level = max(1, min(5, 5 - raw_class))
            except Exception as e:
                print(f"[WARN] XGBoost predict failed: {e}")

        # Deterministic Clinical Safety Invariants
        if spo2 < 90 or sys_bp < 90:
            esi_level = 1
        elif pain >= 8 and (esi_level is None or esi_level > 2):
            esi_level = 2
        elif esi_level is None:
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

        # ── Length of stay ────────────────────────────────────────────────────
        los_map = {1: 6.0, 2: 4.0, 3: 2.5, 4: 1.5, 5: 0.5}
        los_days = los_map.get(esi_level, 2.5)

        return esi_level, los_days, icu_risk


# ── Singleton Engine & Supabase Initialization ────────────────────────────────
engine = HealthConsensusEngine()

try:
    if SUPABASE_URL and not SUPABASE_URL.startswith("https://your-supabase-project"):
        supabase: Optional[Client] = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[OK] Supabase client connected successfully.")
    else:
        supabase = None
        print("[WARN] Supabase placeholder credentials detected. Persistence disabled.")
except Exception as e:
    supabase = None
    print(f"[WARN] Supabase initialization failed: {e}")


# ── Pydantic Request Models ───────────────────────────────────────────────────
class ComplaintPayload(BaseModel):
    chief_complaint_text: str


class TriagePayload(BaseModel):
    patient_id: Optional[str] = "ANON_PATIENT"
    chief_complaint_text: Optional[str] = ""
    dynamic_vitals: Optional[dict] = {}


# ── /analyze-vitals compatibility layer ───────────────────────────────────────
# Mirrors the retired userweb/app.py's request/response contract exactly, so
# the deployed frontend (userweb/frontend) can point at this backend with
# zero changes. Reuses the same rule-based scoring logic and the same loaded
# xgb_model / lgb_model instances as the HealthConsensusEngine above.


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


# ── API Routes (With Aliases to Prevent 404s) ──────────────────────────────────
@app.get("/")
def read_root():
    return {
        "message": "MedVision Engine Running.",
        "models": {
            "nlp_engine": True,
            "xgboost": engine.xgb_model is not None,
            "lightgbm": engine.lgb_model is not None,
        },
        "model_errors": {
            "xgboost": engine.xgb_error,
            "lightgbm": engine.lgb_error,
        },
        "supabase_connected": supabase is not None,
    }


@app.post("/api/patient/analyze-complaint")
@app.post("/api/analyze-complaint")
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
@app.post("/api/patient/evaluate")
@app.post("/api/evaluate-triage")
@app.post("/api/triage")
@app.post("/api/analyze-vitals")
async def evaluate_triage(payload: TriagePayload):
    try:
        complaint = payload.chief_complaint_text or ""
        vitals = payload.dynamic_vitals or {}
        patient_id = payload.patient_id or "ANON_PATIENT"

        nlp_condition, nlp_conf, subsystem = engine.predict_nlp_disease(complaint)
        esi_level, stay_days, icu_risk = engine.predict_tabular_metrics(vitals)

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
        patient_hash = engine.hash_patient_id(patient_id)

        # Asynchronous/Non-blocking logging to Supabase
        if supabase:
            try:
                supabase.table("master_patient_triage").insert({
                    "patient_id":       patient_hash,
                    "chief_complaint":  complaint,
                    "vitals_json":      json.dumps(vitals),
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


@app.get("/api/patient/records")
@app.get("/api/records")
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


@app.post("/analyze-vitals")
def analyze_vitals(vitals: VitalsInput):
    """Same request/response contract as the retired userweb/app.py's
    /analyze-vitals, so the deployed frontend can point at this backend
    unchanged."""
    patient_id = vitals.patient_id.strip()
    if not patient_id:
        raise HTTPException(status_code=422, detail="patient_id is required")

    severity_level = score_manual_vitals(vitals.spo2, vitals.heart_rate, vitals.systolic_bp, vitals.temp, vitals.age)
    disease_probabilities = score_disease_probabilities(
        vitals.spo2, vitals.heart_rate, vitals.systolic_bp, vitals.temp, vitals.age
    )
    risk = score_patient_risk(vitals)
    severity_ml = score_severity_ml(vitals)

    findings_text = vitals.findings.strip()
    nlp_diagnosis = None
    if findings_text:
        condition, confidence, subsystem = engine.predict_nlp_disease(findings_text)
        nlp_diagnosis = {
            "predicted_condition": condition,
            "confidence": confidence,
            "subsystem": subsystem,
        }

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
        "nlp_diagnosis": nlp_diagnosis,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
