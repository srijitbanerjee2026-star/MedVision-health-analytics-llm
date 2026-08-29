"""
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
        "password": "SaraswatiMa19$",
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
    main()
