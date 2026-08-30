import mysql.connector
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report
import os
import re
import joblib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = os.path.join(SCRIPT_DIR, "severity_model.json")
MODEL_PICKLE_FILE = os.path.join(SCRIPT_DIR, "severity_model.pkl")
SQL_FILE = os.path.join(SCRIPT_DIR, "medvision_full.sql")

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": os.environ["MYSQL_PASSWORD"],
}

def seed_database_from_sql():
    if not os.path.exists(SQL_FILE):
        raise FileNotFoundError(f"Cannot find '{SQL_FILE}' in project root.")

    print("[INFO] Connecting to local MySQL server...")
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
    except mysql.connector.Error as err:
        raise ConnectionError(f"MySQL connection failed: {err}")

    print(f"[INFO] Reading and executing '{SQL_FILE}' to build 'medvision' database...")
    with open(SQL_FILE, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # multi=True delegates statement splitting to mysql-connector's own SQL
    # parser, which correctly handles semicolons inside string literals,
    # comments, and stored procedures — a naive str.split(";") would corrupt
    # any dump file containing those.
    statements = cursor.execute(sql_content, multi=True)
    while True:
        try:
            result = next(statements)
        except StopIteration:
            break
        except mysql.connector.Error as err:
            if err.errno in (1007, 1050):
                continue  # database/table already exists — safe to ignore
            conn.rollback()
            conn.close()
            raise RuntimeError(f"Failed executing SQL from '{SQL_FILE}': {err}") from err
        if result.with_rows:
            result.fetchall()

    conn.commit()
    conn.close()
    print("✅ Database 'medvision' and table 'patient_records' ready!")

def load_data_from_mysql():

    config_with_db = MYSQL_CONFIG.copy()
    config_with_db["database"] = "medvision"

    conn = mysql.connector.connect(**config_with_db)
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT age, spo2, heart_rate, resp_rate, sys_bp, dias_bp, temp, pain_score,
               hist_asthma, hist_diabetes, hist_hypertension, hist_cad, hist_stroke,
               target_triage_acuity
        FROM patient_records
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        raise ValueError("MySQL table 'patient_records' is empty!")

    FEATURE_DEFAULTS = {
        "age": 45, "spo2": 95, "heart_rate": 75, "resp_rate": 16, "sys_bp": 120,
        "dias_bp": 80, "temp": 37.0, "pain_score": 0, "hist_asthma": 0,
        "hist_diabetes": 0, "hist_hypertension": 0, "hist_cad": 0, "hist_stroke": 0,
    }

    X_list = []
    y_list = []
    null_counts = {col: 0 for col in FEATURE_DEFAULTS}

    for row in rows:
        feature_vector = []
        for col, default in FEATURE_DEFAULTS.items():
            value = row[col]
            if value is None:
                null_counts[col] += 1
                value = default
            feature_vector.append(float(value))

        X_list.append(feature_vector)
        raw_acuity = int(row['target_triage_acuity'])
        inverted_acuity = 6 - raw_acuity

        y_list.append(inverted_acuity)

    total_nulls = sum(null_counts.values())
    if total_nulls:
        print(f"[WARN] Substituted defaults for {total_nulls} missing value(s) across {len(rows)} rows:")
        for col, count in null_counts.items():
            if count:
                print(f"[WARN]   {col}: {count} missing ({count / len(rows):.1%} of rows)")

    X = np.array(X_list, dtype=np.float32)
    y_raw = np.array(y_list, dtype=np.int32)

    return X, y_raw

def train_xgboost_model():
    X, y_raw = load_data_from_mysql()
    print(f"[INFO] Successfully loaded {X.shape[0]} rows with {X.shape[1]} features.")

    le = LabelEncoder()
    y = le.fit_transform(y_raw)
    num_classes = len(np.unique(y))

    # app.py recovers the 1-5 severity scale as `predicted_class + 1`, which
    # only holds if every acuity level 1-5 is present so LabelEncoder maps
    # them to contiguous indices 0-4 in order. If any level is missing from
    # the data, that mapping silently shifts and every prediction downstream
    # is mislabeled by one or more severity levels with no error raised.
    expected_classes = np.array([1, 2, 3, 4, 5])
    if not np.array_equal(le.classes_, expected_classes):
        raise ValueError(
            f"Expected all 5 acuity levels {expected_classes.tolist()} in the training "
            f"data, but found only {le.classes_.tolist()}. Fix the data before training — "
            "app.py's class-index-to-severity mapping assumes all 5 are present."
        )

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
    joblib.dump(model, MODEL_PICKLE_FILE)
    print("✅ Trained model saved successfully to 'severity_model.pkl'!")
if __name__ == "__main__":
    train_xgboost_model()
