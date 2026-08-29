import os
import joblib
import mysql.connector
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report

from lightgbm import LGBMClassifier

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "SaraswatiMa19$",
    "database": "medvision",
}

MODEL_PATH = "risk_model.pkl"

FEATURE_COLUMNS = [
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

TARGET_COLUMN = "hospital_expire_flag"


# ---------------------------------------------------------
# Load data from MySQL
# ---------------------------------------------------------


def load_data_from_mysql():
    connection = mysql.connector.connect(**DB_CONFIG)

    query = f"""
    SELECT
        {", ".join(FEATURE_COLUMNS)},
        {TARGET_COLUMN}
    FROM patient_records
"""

    cursor = connection.cursor(dictionary=True)
    cursor.execute(query)

    rows = cursor.fetchall()

    cursor.close()
    connection.close()

    if not rows:
        raise ValueError("No records found in medvision.patient_records.")

    return rows


# ---------------------------------------------------------
# Prepare features and target
# ---------------------------------------------------------


def prepare_dataset(rows):
    X = np.array(
        [[row[column] for column in FEATURE_COLUMNS] for row in rows], dtype=np.float32
    )

    y = np.array([row[TARGET_COLUMN] for row in rows], dtype=np.int32)

    return X, y


# ---------------------------------------------------------
# Train LightGBM model
# ---------------------------------------------------------


def train_model(X_train, y_train):
    model = LGBMClassifier(
        n_estimators=100, learning_rate=0.05, max_depth=5, random_state=42
    )

    model.fit(X_train, y_train)

    return model


# ---------------------------------------------------------
# Evaluate model
# ---------------------------------------------------------


def evaluate_model(model, X_test, y_test):
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_prob)

    print(f"Validation Accuracy: {accuracy:.4f}")
    print(f"ROC-AUC: {roc_auc:.4f}")

    print("\nClassification Report:")
    print(
        classification_report(
            y_test,
            y_pred,
            target_names=["Non-Critical", "Critical Risk"],
            zero_division=0,
        )
    )


# ---------------------------------------------------------
# Save model
# ---------------------------------------------------------


def save_model(model):
    joblib.dump(model, MODEL_PATH)
    print(f"Model saved to: {os.path.abspath(MODEL_PATH)}")


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------


def main():
    rows = load_data_from_mysql()

    X, y = prepare_dataset(rows)

    print(f"Total records: {len(X)}")
    print(f"Critical-risk patients: {np.sum(y == 1)}")
    print(f"Non-critical patients: {np.sum(y == 0)}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    model = train_model(X_train, y_train)

    evaluate_model(model, X_test, y_test)

    save_model(model)


if __name__ == "__main__":
    main()
