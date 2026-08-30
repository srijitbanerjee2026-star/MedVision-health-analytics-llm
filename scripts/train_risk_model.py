import os
import joblib
import numpy as np
import pandas as pd
import mysql.connector
import lightgbm as lgb

from dotenv import load_dotenv

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    roc_auc_score,
    classification_report,
    confusion_matrix,
)

# ============================================================
# 1. LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# 2. DATABASE CONFIGURATION
# ============================================================

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("DB_NAME", "medvision"),
}


# ============================================================
# 3. FEATURE DEFINITIONS
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


TARGET_COL = "target_triage_acuity"


# ============================================================
# 4. FETCH ACTUAL DATA FROM MYSQL
# ============================================================


def fetch_patient_data() -> pd.DataFrame:
    """
    Fetch actual patient records from the shared
    medvision.patient_records table.

    This function DOES NOT generate random data.
    """

    if not DB_CONFIG["password"]:
        raise ValueError(
            "MYSQL_PASSWORD was not found in the environment. " "Check your .env file."
        )

    print("[INFO] Connecting to MySQL...")
    print("[INFO] Database: medvision")
    print("[INFO] Table: patient_records")

    conn = mysql.connector.connect(**DB_CONFIG)

    try:

        query = f"""
            SELECT
                {", ".join(FEATURE_COLS)},
                {TARGET_COL}
            FROM patient_records_500
        """

        df = pd.read_sql(query, conn)

    finally:

        conn.close()

    print(f"[INFO] Retrieved {len(df)} patient records from MySQL.")

    return df


# ============================================================
# 5. VALIDATE DATA
# ============================================================


def validate_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate the actual database data before training.
    """

    required_cols = FEATURE_COLS + [TARGET_COL]

    # --------------------------------------------------------
    # Check required columns
    # --------------------------------------------------------

    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:

        raise ValueError(f"Missing columns in patient_records: {missing_cols}")

    # --------------------------------------------------------
    # Check number of records
    # --------------------------------------------------------

    if len(df) == 0:

        raise ValueError(
            "patient_records contains no data. " "The model cannot be trained."
        )

    # --------------------------------------------------------
    # Display missing values
    # --------------------------------------------------------

    print("\n[INFO] Missing values:")

    missing = df[required_cols].isnull().sum()

    for col, count in missing.items():

        print(f"       {col}: {count}")

    # --------------------------------------------------------
    # Remove rows with missing training values
    # --------------------------------------------------------

    before = len(df)

    df = df.dropna(subset=required_cols).copy()

    removed = before - len(df)

    if removed > 0:

        print(f"\n[INFO] Removed {removed} incomplete records.")

    print(f"[INFO] Records available for training: {len(df)}")

    # --------------------------------------------------------
    # Check target values
    # --------------------------------------------------------

    print("\n[INFO] Target values found:")

    print(df[TARGET_COL].value_counts().sort_index())

    # --------------------------------------------------------
    # Ensure target contains expected acuity values
    # --------------------------------------------------------

    valid_acuity = {1, 2, 3, 4, 5}

    actual_acuity = set(df[TARGET_COL].astype(int).unique())

    invalid_acuity = actual_acuity - valid_acuity

    if invalid_acuity:

        raise ValueError(
            f"Unexpected target_triage_acuity values: "
            f"{invalid_acuity}. Expected values are 1-5."
        )

    return df


# ============================================================
# 6. PREPROCESS ACTUAL DATA
# ============================================================


def preprocess_data(df: pd.DataFrame):
    """
    Convert the actual triage-acuity target into
    a binary high-risk classification.

    Acuity:
        1 = most urgent
        2 = very urgent
        3 = moderate
        4 = less urgent
        5 = least urgent

    Mapping:

        1 or 2 -> HIGH RISK = 1
        3, 4 or 5 -> LOWER RISK = 0
    """

    # --------------------------------------------------------
    # Create binary target
    # --------------------------------------------------------

    df = df.copy()

    df["is_high_risk"] = df[TARGET_COL].astype(int).isin([1, 2]).astype(np.int32)

    # --------------------------------------------------------
    # Feature matrix
    # --------------------------------------------------------

    X = df[FEATURE_COLS].astype(np.float32)

    # --------------------------------------------------------
    # Target vector
    # --------------------------------------------------------

    y = df["is_high_risk"].astype(np.int32)

    print("\n[INFO] Feature columns:")

    for col in FEATURE_COLS:
        print(f"       {col}")

    print(f"\n[INFO] Feature matrix shape: {X.shape}")

    print(f"[INFO] High-risk records: {int(y.sum())}")

    print(f"[INFO] Lower-risk records: " f"{int(len(y) - y.sum())}")

    # --------------------------------------------------------
    # Check both classes exist
    # --------------------------------------------------------

    if y.nunique() < 2:

        raise ValueError(
            "Training data contains only one risk class. "
            "Both high-risk and lower-risk records are required."
        )

    return X, y


# ============================================================
# 7. TRAIN LIGHTGBM MODEL
# ============================================================


def train_and_evaluate(X: pd.DataFrame, y: pd.Series) -> lgb.LGBMClassifier:
    """
    Train and evaluate the LightGBM classifier
    using actual patient data.
    """

    # --------------------------------------------------------
    # Train / test split
    # --------------------------------------------------------

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42,
        stratify=y,
    )

    print("\n[INFO] Data split:")

    print(f"       Training records: {len(X_train)}")

    print(f"       Testing records: {len(X_test)}")

    # --------------------------------------------------------
    # Create LightGBM classifier
    # --------------------------------------------------------

    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=100,
        learning_rate=0.05,
        max_depth=5,
        random_state=42,
        verbosity=-1,
    )

    # --------------------------------------------------------
    # Train
    # --------------------------------------------------------

    print("\n[INFO] Training LightGBM...")

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

    # --------------------------------------------------------
    # Store metrics inside model
    # --------------------------------------------------------

    model.validation_accuracy = float(accuracy)

    model.validation_roc_auc = float(roc_auc)

    model.classification_report = classification_report(y_test, y_pred)

    model.confusion_matrix = confusion_matrix(y_test, y_pred).tolist()

    # --------------------------------------------------------
    # Feature importance
    # --------------------------------------------------------

    model.feature_importance = dict(
        zip(FEATURE_COLS, model.feature_importances_.tolist())
    )

    return model


# ============================================================
# 8. GENERATE RECOMMENDATION
# ============================================================


def generate_recommendation(risk_score: float, patient: dict) -> dict:
    """
    Generate the backend recommendation based on
    the model's predicted risk score.

    NOTE:
    These are application-level recommendations,
    not clinical diagnosis or medical advice.
    """

    age = float(patient["age"])

    # --------------------------------------------------------
    # VERY HIGH RISK
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # HIGH RISK
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # MODERATE RISK
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # LOW RISK
    # --------------------------------------------------------

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
# 9. PREDICT ONE PATIENT
# ============================================================


def predict_patient(model: lgb.LGBMClassifier, patient: dict) -> dict:
    """
    Predict risk for one actual patient.

    The patient dictionary must contain the same
    clinical features used during training.
    """

    # --------------------------------------------------------
    # Validate fields
    # --------------------------------------------------------

    missing_cols = [col for col in FEATURE_COLS if col not in patient]

    if missing_cols:

        raise ValueError(f"Missing patient fields: {missing_cols}")

    # --------------------------------------------------------
    # Create one-row DataFrame
    #
    # Using the original feature names prevents
    # feature-order mistakes.
    # --------------------------------------------------------

    X_patient = pd.DataFrame(
        [[patient[col] for col in FEATURE_COLS]],
        columns=FEATURE_COLS,
    )

    X_patient = X_patient.astype(np.float32)

    # --------------------------------------------------------
    # Predict probability
    # --------------------------------------------------------

    probability = float(model.predict_proba(X_patient)[0][1])

    # --------------------------------------------------------
    # Convert probability to percentage
    # --------------------------------------------------------

    risk_score = probability * 100

    # --------------------------------------------------------
    # Generate recommendation
    # --------------------------------------------------------

    care_plan = generate_recommendation(risk_score, patient)

    # --------------------------------------------------------
    # Final backend response
    # --------------------------------------------------------

    return {
        "risk_score": round(risk_score, 2),
        "recommendation": care_plan["recommendation"],
        "monitoring": care_plan["monitoring"],
        "estimated_stay": care_plan["estimated_stay"],
        "disposition": care_plan["disposition"],
    }


# ============================================================
# 10. SAVE MODEL
# ============================================================


def save_model(model: lgb.LGBMClassifier, filepath="risk_model.pkl"):
    """
    Save trained LightGBM model.
    """

    joblib.dump(model, filepath)

    print(f"[SUCCESS] Model saved to: {filepath}")


# ============================================================
# 11. MAIN
# ============================================================


def main():

    print("=" * 60)
    print("MEDVISION LIGHTGBM RISK MODEL")
    print("=" * 60)

    # --------------------------------------------------------
    # Fetch ACTUAL database data
    # --------------------------------------------------------

    print("\n[1/5] Fetching actual patient data...")

    df = fetch_patient_data()

    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    print("\n[2/5] Validating patient data...")

    df = validate_data(df)

    # --------------------------------------------------------
    # Preprocess
    # --------------------------------------------------------

    print("\n[3/5] Preparing training data...")

    X, y = preprocess_data(df)

    # --------------------------------------------------------
    # Train
    # --------------------------------------------------------

    print("\n[4/5] Training and evaluating LightGBM...")

    model = train_and_evaluate(X, y)

    # --------------------------------------------------------
    # Print metrics
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("MODEL EVALUATION")
    print("=" * 60)

    print(f"\nValidation Accuracy: " f"{model.validation_accuracy:.4f}")

    print(f"Validation ROC-AUC: " f"{model.validation_roc_auc:.4f}")

    print("\nClassification Report:")

    print(model.classification_report)

    print("\nConfusion Matrix:")

    print(np.array(model.confusion_matrix))

    # --------------------------------------------------------
    # Feature importance
    # --------------------------------------------------------

    print("\nFeature Importance:")

    sorted_importance = sorted(
        model.feature_importance.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    for feature, importance in sorted_importance:

        print(f"  {feature:<25} {importance}")

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    print("\n[5/5] Saving model...")

    save_model(model, "risk_model.pkl")

    print("\n" + "=" * 60)
    print("[SUCCESS] LIGHTGBM TRAINING COMPLETE")
    print("=" * 60)


# ============================================================
# 12. ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
