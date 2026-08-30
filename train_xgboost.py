import os
import sqlite3

import numpy as np
import xgboost as xgb
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

MODEL_FILE = "severity_model.json"
DB_FILE = "medvision_guard.db"

FEATURE_COLS = [
    "age", "spo2", "heart_rate", "resp_rate", "sys_bp", "dias_bp", "temp",
    "pain_score", "hist_asthma", "hist_diabetes", "hist_hypertension",
    "hist_cad", "hist_stroke",
]


def init_sqlite_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patient_records (
            patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
            age INTEGER, spo2 REAL, heart_rate REAL, resp_rate REAL,
            sys_bp REAL, dias_bp REAL, temp REAL, pain_score INTEGER,
            hist_asthma INTEGER, hist_diabetes INTEGER, hist_hypertension INTEGER,
            hist_cad INTEGER, hist_stroke INTEGER, target_triage_acuity INTEGER
        );
    """)
    conn.commit()


def seed_if_empty(conn: sqlite3.Connection, num_records: int = 500) -> None:
    """Generates synthetic patient records with the same distributions as
    New/seed_db.py — no external dataset or MySQL server required. Only runs
    once; leaves real data alone if the table is already populated."""
    (count,) = conn.execute("SELECT COUNT(*) FROM patient_records").fetchone()
    if count > 0:
        print(f"[INFO] patient_records already has {count} rows — skipping seed.")
        return

    print(f"[INFO] Seeding {num_records} synthetic patient records into '{DB_FILE}'...")
    rng = np.random.default_rng(42)

    spo2 = np.clip(np.round(rng.normal(96, 3, num_records), 1), 70, 100)
    rows = list(zip(
        rng.integers(18, 90, num_records).tolist(),
        spo2.tolist(),
        np.round(rng.normal(78, 15, num_records), 1).tolist(),
        np.round(rng.normal(18, 4, num_records), 1).tolist(),
        np.round(rng.normal(122, 18, num_records), 1).tolist(),
        np.round(rng.normal(78, 12, num_records), 1).tolist(),
        np.round(rng.normal(37.0, 0.8, num_records), 1).tolist(),
        rng.integers(0, 11, num_records).tolist(),
        rng.choice([0, 1], num_records, p=[0.85, 0.15]).tolist(),
        rng.choice([0, 1], num_records, p=[0.75, 0.25]).tolist(),
        rng.choice([0, 1], num_records, p=[0.60, 0.40]).tolist(),
        rng.choice([0, 1], num_records, p=[0.85, 0.15]).tolist(),
        rng.choice([0, 1], num_records, p=[0.92, 0.08]).tolist(),
        rng.choice([1, 2, 3, 4, 5], num_records, p=[0.1, 0.2, 0.4, 0.2, 0.1]).tolist(),
    ))

    conn.executemany(
        f"""INSERT INTO patient_records ({', '.join(FEATURE_COLS)}, target_triage_acuity)
            VALUES ({', '.join(['?'] * (len(FEATURE_COLS) + 1))})""",
        rows,
    )
    conn.commit()
    print(f"✅ Seeded {num_records} synthetic patient records.")


def load_data_from_sqlite() -> tuple[np.ndarray, np.ndarray]:
    conn = sqlite3.connect(DB_FILE)
    try:
        init_sqlite_db(conn)
        seed_if_empty(conn)
        rows = conn.execute(
            f"SELECT {', '.join(FEATURE_COLS)}, target_triage_acuity FROM patient_records"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        raise ValueError(f"'{DB_FILE}' table 'patient_records' is empty!")

    X_list, y_list = [], []
    for row in rows:
        *features, raw_acuity = row
        X_list.append([float(v) if v is not None else 0.0 for v in features])
        y_list.append(6 - int(raw_acuity))

    X = np.array(X_list, dtype=np.float32)
    y_raw = np.array(y_list, dtype=np.int32)
    return X, y_raw


def train_xgboost_model():
    X, y_raw = load_data_from_sqlite()
    print(f"[INFO] Successfully loaded {X.shape[0]} rows with {X.shape[1]} features.")

    le = LabelEncoder()
    y = le.fit_transform(y_raw)
    num_classes = len(np.unique(y))

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("[INFO] Training XGBoost Classifier...")
    model = xgb.XGBClassifier(
        objective='multi:softprob',
        num_class=num_classes,
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        random_state=42
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\n--- Model Performance Summary ---")
    print(classification_report(y_test, y_pred))

    model.save_model(MODEL_FILE)
    print(f"✅ XGBoost model trained successfully and saved to '{MODEL_FILE}'!")


if __name__ == "__main__":
    train_xgboost_model()
