import mysql.connector
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report
import os
import re

MODEL_FILE = "severity_model.json"
SQL_FILE = "medvision_full.sql"

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "user67" 
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

    statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]

    for stmt in statements:
        try:
            cursor.execute(stmt)
        except mysql.connector.Error as err:
            if err.errno not in (1007, 1050):
                print(f"[WARN] Statement execution notice: {err}")

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

    X_list = []
    y_list = []

    for row in rows:
        feature_vector = [
            float(row['age'] if row['age'] is not None else 45),
            float(row['spo2'] if row['spo2'] is not None else 95),
            float(row['heart_rate'] if row['heart_rate'] is not None else 75),
            float(row['resp_rate'] if row['resp_rate'] is not None else 16),
            float(row['sys_bp'] if row['sys_bp'] is not None else 120),
            float(row['dias_bp'] if row['dias_bp'] is not None else 80),
            float(row['temp'] if row['temp'] is not None else 37.0),
            float(row['pain_score'] if row['pain_score'] is not None else 0),
            float(row['hist_asthma'] if row['hist_asthma'] is not None else 0),
            float(row['hist_diabetes'] if row['hist_diabetes'] is not None else 0),
            float(row['hist_hypertension'] if row['hist_hypertension'] is not None else 0),
            float(row['hist_cad'] if row['hist_cad'] is not None else 0),
            float(row['hist_stroke'] if row['hist_stroke'] is not None else 0)
        ]
        
        X_list.append(feature_vector)
        raw_acuity = int(row['target_triage_acuity'])
        inverted_acuity = 6 - raw_acuity

        y_list.append(inverted_acuity)

    X = np.array(X_list, dtype=np.float32)
    y_raw = np.array(y_list, dtype=np.int32)

    return X, y_raw

def train_xgboost_model():
    X, y_raw = load_data_from_mysql()
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
