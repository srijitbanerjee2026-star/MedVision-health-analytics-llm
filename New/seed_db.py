"""
seed_db.py - Creates medvision_db and seeds synthetic patient records.
"""

import numpy as np
import pandas as pd
import mysql.connector

# MySQL Root Connection (without specifying a database)
DB_HOST = "localhost"
DB_USER = "root"
DB_PASS = "SaraswatiMa19$"  # Update with your actual MySQL password


def init_database():
    conn = mysql.connector.connect(
        host="localhost", user="root", password="SaraswatiMa19$"
    )
    cursor = conn.cursor()

    cursor.execute("CREATE DATABASE IF NOT EXISTS medvision_db;")
    cursor.execute("USE medvision_db;")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patient_records (
        patient_id INT AUTO_INCREMENT PRIMARY KEY,
        age INT,
        spo2 FLOAT,
        heart_rate FLOAT,
        resp_rate FLOAT,
        sys_bp FLOAT,
        dias_bp FLOAT,
        temp FLOAT,
        pain_score INT,
        hist_asthma INT,
        hist_diabetes INT,
        hist_hypertension INT,
        hist_cad INT,
        hist_stroke INT,
        target_triage_acuity INT
    );
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print("Database 'medvision_db' and table 'patient_records' ready.")


def generate_and_seed_data(num_records: int = 500):
    np.random.seed(42)

    data = {
        "age": np.random.randint(18, 90, size=num_records),
        "spo2": np.round(np.random.normal(96, 3, size=num_records), 1),
        "heart_rate": np.round(np.random.normal(78, 15, size=num_records), 1),
        "resp_rate": np.round(np.random.normal(18, 4, size=num_records), 1),
        "sys_bp": np.round(np.random.normal(122, 18, size=num_records), 1),
        "dias_bp": np.round(np.random.normal(78, 12, size=num_records), 1),
        "temp": np.round(np.random.normal(37.0, 0.8, size=num_records), 1),
        "pain_score": np.random.randint(0, 11, size=num_records),
        "hist_asthma": np.random.choice([0, 1], size=num_records, p=[0.85, 0.15]),
        "hist_diabetes": np.random.choice([0, 1], size=num_records, p=[0.75, 0.25]),
        "hist_hypertension": np.random.choice([0, 1], size=num_records, p=[0.60, 0.40]),
        "hist_cad": np.random.choice([0, 1], size=num_records, p=[0.85, 0.15]),
        "hist_stroke": np.random.choice([0, 1], size=num_records, p=[0.92, 0.08]),
        "target_triage_acuity": np.random.choice(
            [1, 2, 3, 4, 5], size=num_records, p=[0.1, 0.2, 0.4, 0.2, 0.1]
        ),
    }

    df = pd.DataFrame(data)

    # Ensure physical limits
    df["spo2"] = df["spo2"].clip(70, 100)

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="SaraswatiMa19$",
        database="medvision_db",
    )
    cursor = conn.cursor()

    insert_query = """
    INSERT INTO patient_records (
        age, spo2, heart_rate, resp_rate, sys_bp, dias_bp, temp, pain_score,
        hist_asthma, hist_diabetes, hist_hypertension, hist_cad, hist_stroke, target_triage_acuity
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """

    cursor.executemany(insert_query, df.values.tolist())
    conn.commit()
    print(f"Successfully seeded {cursor.rowcount} patient records into MySQL!")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    init_database()
    generate_and_seed_data()
