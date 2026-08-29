'''"""
train_risk_model.py
MedVision Guard - Model 3: LightGBM Clinical Risk Engine
"""

import os
import joblib
import numpy as np
import pandas as pd
import mysql.connector
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report


def fetch_patient_data() -> pd.DataFrame:
    """Connects to MySQL database and fetches patient clinical records."""
    db_config = {
        "host": "localhost",
        "user": "root",
        "password": os.getenv("MYSQL_PASSWORD"),
        "database": "medvision_db",
    }

    query = """
        SELECT
            age, spo2, heart_rate, resp_rate, sys_bp, dias_bp, temp, pain_score,
            hist_asthma, hist_diabetes, hist_hypertension, hist_cad, hist_stroke,
            target_triage_acuity
        FROM patient_records;
    """

    conn = mysql.connector.connect(**db_config)
    df = pd.read_sql(query, conn)
    conn.close()

    return df


def preprocess_data(df: pd.DataFrame):
    """
    Engineers the target variable and converts features into float32 NumPy matrix.

    Target Mapping:
      - Acuity 1 or 2 -> 1 (High Risk / Potential ICU Candidate)
      - Acuity 3, 4, or 5 -> 0 (Stable / Non-Emergent)
    """
    feature_cols = [
        "age",
        "spo2",
        "heart_rate",
        "resp_rate",
        "sys_bp",
        "dias_bp",
        "temp",
        "pain_score",
        "hist_asthma",
        "hist_diabetes",
        "hist_hypertension",
        "hist_cad",
        "hist_stroke",
    ]

    # Binary Target Engineering
    df["is_critical_risk"] = df["target_triage_acuity"].isin([1, 2]).astype(np.int32)

    # Feature Matrix Conversion
    X = df[feature_cols].values.astype(np.float32)
    y = df["is_critical_risk"].values

    return X, y


def train_and_evaluate(X: np.ndarray, y: np.ndarray) -> lgb.LGBMClassifier:
    """Splits data, trains LightGBM classifier, and outputs evaluation metrics."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    model = lgb.LGBMClassifier(
        n_estimators=100, learning_rate=0.05, max_depth=5, random_state=42
    )

    model.fit(X_train, y_train)

    # Predictions & Evaluation
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_proba)

    print(f"Validation Accuracy : {accuracy:.4f}")
    print(f"Validation ROC-AUC   : {roc_auc:.4f}\n")
    print("Classification Report:")
    print(classification_report(y_test, y_pred))

    return model


def save_model(model: lgb.LGBMClassifier, filepath: str = "risk_model.pkl") -> None:
    """Saves trained model artifact to disk."""
    joblib.dump(model, filepath)
    print(f"Model saved successfully to {os.path.abspath(filepath)}")


def main():
    df = fetch_patient_data()
    X, y = preprocess_data(df)
    model = train_and_evaluate(X, y)
    save_model(model)


if __name__ == "__main__":
    main()'''

"""
train_risk_model.py

MedVision Guard - Model 3: LightGBM Clinical Risk Engine

Backend ML component.

Flow:
    Patient clinical data
            ↓
       LightGBM Model
            ↓
       Risk Score (%)
            ↓
    Recommendation
            ↓
    Monitoring Period
            ↓
    Estimated Hospital Stay

Model output:
    risk_score
    recommendation
    monitoring
    estimated_stay
    disposition

IMPORTANT:
    This is a hackathon decision-support prototype.
    Recommendations and estimated stay durations are
    rule-based and are NOT medical guidelines.
"""


import os
from dotenv import load_dotenv

load_dotenv()

import os
import joblib
import numpy as np
import pandas as pd
import mysql.connector
import lightgbm as lgb

from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report

# ============================================================
# 1. FEATURE DEFINITIONS
# ============================================================

FEATURE_COLS = [
    "age",
    "spo2",
    "heart_rate",
    "resp_rate",
    "sys_bp",
    "dias_bp",
    "temp",
    "pain_score",
    "hist_asthma",
    "hist_diabetes",
    "hist_hypertension",
    "hist_cad",
    "hist_stroke",
]


# ============================================================
# 2. FETCH PATIENT DATA FROM MYSQL
# ============================================================


def fetch_patient_data() -> pd.DataFrame:
    """
    Fetches patient clinical records from MySQL.
    """

    db_config = {
        "host": "localhost",
        "user": "root",
        "password": os.getenv("MYSQL_PASSWORD"),
        "database": "medvision_db",
    }

    query = """
        SELECT
            age,
            spo2,
            heart_rate,
            resp_rate,
            sys_bp,
            dias_bp,
            temp,
            pain_score,
            hist_asthma,
            hist_diabetes,
            hist_hypertension,
            hist_cad,
            hist_stroke,
            target_triage_acuity
        FROM patient_records;
    """

    conn = mysql.connector.connect(**db_config)

    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    return df


# ============================================================
# 3. PREPROCESS DATA
# ============================================================


def preprocess_data(df: pd.DataFrame):
    """
    Creates the binary ML target.

    Current database contains target_triage_acuity
    rather than an actual hospital length-of-stay target.

    Target mapping:

        Acuity 1 or 2 -> 1
        Acuity 3, 4 or 5 -> 0

    The model therefore learns high-risk versus
    lower-risk classification.

    The probability produced by LightGBM becomes
    the patient's Risk Score.
    """

    required_cols = FEATURE_COLS + ["target_triage_acuity"]

    # --------------------------------------------------------
    # Validate columns
    # --------------------------------------------------------

    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f"Missing columns in database: {missing_cols}")

    # --------------------------------------------------------
    # Remove incomplete records
    # --------------------------------------------------------

    df = df.dropna(subset=required_cols).copy()

    # --------------------------------------------------------
    # Create binary target
    # --------------------------------------------------------

    df["is_high_risk"] = df["target_triage_acuity"].isin([1, 2]).astype(np.int32)

    # --------------------------------------------------------
    # Feature matrix
    # --------------------------------------------------------

    X = df[FEATURE_COLS].values.astype(np.float32)

    # --------------------------------------------------------
    # Target vector
    # --------------------------------------------------------

    y = df["is_high_risk"].values.astype(np.int32)

    return X, y


# ============================================================
# 4. TRAIN AND EVALUATE LIGHTGBM
# ============================================================


def train_and_evaluate(X: np.ndarray, y: np.ndarray) -> lgb.LGBMClassifier:
    """
    Trains and evaluates the LightGBM classifier.

    Returns:
        Trained LightGBM model.
    """

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    # --------------------------------------------------------
    # LightGBM classifier
    # --------------------------------------------------------

    model = lgb.LGBMClassifier(
        n_estimators=100, learning_rate=0.05, max_depth=5, random_state=42, verbosity=-1
    )

    model.fit(X_train, y_train)

    # --------------------------------------------------------
    # Predictions
    # --------------------------------------------------------

    y_pred = model.predict(X_test)

    y_proba = model.predict_proba(X_test)[:, 1]

    # --------------------------------------------------------
    # Evaluation
    # --------------------------------------------------------

    accuracy = accuracy_score(y_test, y_pred)

    roc_auc = roc_auc_score(y_test, y_proba)

    # Store evaluation information on the model object
    # so the backend can access it later if required.

    model.validation_accuracy = float(accuracy)

    model.validation_roc_auc = float(roc_auc)

    model.classification_report = classification_report(y_test, y_pred)

    return model


# ============================================================
# 5. GENERATE RECOMMENDATION
# ============================================================


def generate_recommendation(risk_score: float, patient: dict) -> dict:
    """
    Generates the backend care recommendation.

    Inputs:
        risk_score -> LightGBM probability converted to %
        patient    -> patient clinical information

    Returns:
        Dictionary containing:
            recommendation
            monitoring
            estimated_stay
            disposition
    """

    age = float(patient["age"])

    # ========================================================
    # VERY HIGH SCORE
    # ========================================================

    if risk_score >= 85:

        recommendation = [
            "Immediate senior clinical review",
            "Continuous monitoring",
            "ICU evaluation",
        ]

        if age >= 75:
            estimated_stay = "5-7+ days"

        elif age >= 60:
            estimated_stay = "4-6 days"

        else:
            estimated_stay = "3-5 days"

        return {
            "recommendation": recommendation,
            "monitoring": "Continuous",
            "estimated_stay": estimated_stay,
            "disposition": "Hospital admission",
        }

    # ========================================================
    # HIGH SCORE
    # ========================================================

    elif risk_score >= 70:

        recommendation = [
            "Hospital admission recommended",
            "Close clinical monitoring",
            "Senior clinical review",
        ]

        if age >= 75:
            estimated_stay = "4-6 days"

        elif age >= 60:
            estimated_stay = "3-5 days"

        else:
            estimated_stay = "2-4 days"

        return {
            "recommendation": recommendation,
            "monitoring": "Every 1-2 hours",
            "estimated_stay": estimated_stay,
            "disposition": "Hospital admission",
        }

    # ========================================================
    # MODERATE SCORE
    # ========================================================

    elif risk_score >= 40:

        recommendation = [
            "Continue hospital observation",
            "Repeat vital-sign assessment",
            "Clinical reassessment before discharge",
        ]

        if age >= 75:
            monitoring = "Every 2 hours"
            estimated_stay = "1-3 days"

        elif age >= 60:
            monitoring = "Every 2-4 hours"
            estimated_stay = "12-48 hours"

        else:
            monitoring = "Every 4 hours"
            estimated_stay = "Observation only"

        return {
            "recommendation": recommendation,
            "monitoring": monitoring,
            "estimated_stay": estimated_stay,
            "disposition": "Observation",
        }

    # ========================================================
    # LOW SCORE
    # ========================================================

    else:

        recommendation = [
            "Routine monitoring",
            "Reassess vital signs",
            "Consider discharge if clinically stable",
        ]

        if age >= 75:
            monitoring = "Every 4 hours"
            estimated_stay = "12-24 hours observation"

        elif age >= 60:
            monitoring = "Every 4-6 hours"
            estimated_stay = "6-12 hours observation"

        else:
            monitoring = "Every 6 hours"
            estimated_stay = "May discharge after monitoring"

        return {
            "recommendation": recommendation,
            "monitoring": monitoring,
            "estimated_stay": estimated_stay,
            "disposition": "Possible discharge after observation",
        }


# ============================================================
# 6. PREDICT ONE PATIENT
# ============================================================


def predict_patient(model: lgb.LGBMClassifier, patient: dict) -> dict:
    """
    Generates the complete backend response for one patient.

    Returns a dictionary that can directly be converted
    to JSON by Flask/FastAPI.
    """

    # --------------------------------------------------------
    # Validate patient data
    # --------------------------------------------------------

    missing_cols = [col for col in FEATURE_COLS if col not in patient]

    if missing_cols:
        raise ValueError(f"Missing patient fields: {missing_cols}")

    # --------------------------------------------------------
    # Create feature vector
    # --------------------------------------------------------

    X_patient = np.array(
        [patient[col] for col in FEATURE_COLS], dtype=np.float32
    ).reshape(1, -1)

    # --------------------------------------------------------
    # Get LightGBM probability
    # --------------------------------------------------------

    probability = float(model.predict_proba(X_patient)[0][1])

    # --------------------------------------------------------
    # Convert probability to percentage
    # --------------------------------------------------------

    risk_score = probability * 100

    # --------------------------------------------------------
    # Generate care recommendation
    # --------------------------------------------------------

    care_plan = generate_recommendation(risk_score, patient)

    # --------------------------------------------------------
    # Backend response
    # --------------------------------------------------------

    result = {
        "risk_score": round(risk_score, 2),
        "recommendation": care_plan["recommendation"],
        "monitoring": care_plan["monitoring"],
        "estimated_stay": care_plan["estimated_stay"],
        "disposition": care_plan["disposition"],
    }

    return result


# ============================================================
# 7. SAVE MODEL
# ============================================================


def save_model(model: lgb.LGBMClassifier, filepath: str = "risk_model.pkl") -> None:
    """
    Saves the trained LightGBM model.
    """

    joblib.dump(model, filepath)


# ============================================================
# 8. MAIN TRAINING FUNCTION
# ============================================================


def main():

    # --------------------------------------------------------
    # Fetch data
    # --------------------------------------------------------

    df = fetch_patient_data()

    # --------------------------------------------------------
    # Preprocess
    # --------------------------------------------------------

    X, y = preprocess_data(df)

    # --------------------------------------------------------
    # Train model
    # --------------------------------------------------------

    model = train_and_evaluate(X, y)

    # --------------------------------------------------------
    # Save model
    # --------------------------------------------------------

    save_model(model)


# ============================================================
# 9. ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
