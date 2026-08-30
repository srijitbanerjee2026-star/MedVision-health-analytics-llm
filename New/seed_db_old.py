import os
import numpy as np
import mysql.connector

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": os.getenv("MY SQL_PASSWORD"),
    "database": "medvision",
}


# ============================================================
# 1. ADD TARGET COLUMN IF NEEDED
# ============================================================


def create_target_column(cursor):
    """
    Add target_triage_acuity to the existing shared
    medvision.patient_records table if it does not exist.
    """

    cursor.execute("""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'medvision'
          AND TABLE_NAME = 'patient_records'
          AND COLUMN_NAME = 'target_triage_acuity'
    """)

    exists = cursor.fetchone()[0]

    if not exists:

        cursor.execute("""
            ALTER TABLE patient_records
            ADD COLUMN target_triage_acuity INT NULL
        """)

        print("[INFO] Added target_triage_acuity column.")

    else:

        print("[INFO] target_triage_acuity already exists.")


# ============================================================
# 2. GENERATE AND INSERT PATIENT RECORDS
# ============================================================


def seed_patient_records(num_records=500):
    """
    Populate the existing shared medvision.patient_records table.

    Does NOT modify xgboost_training.
    """

    np.random.seed(42)

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:

        # ----------------------------------------------------
        # Make sure target column exists
        # ----------------------------------------------------

        create_target_column(cursor)
        conn.commit()

        # ----------------------------------------------------
        # Check existing records
        # ----------------------------------------------------

        cursor.execute("SELECT COUNT(*) FROM patient_records")

        existing_count = cursor.fetchone()[0]

        if existing_count > 0:

            print(
                f"[INFO] patient_records already contains " f"{existing_count} records."
            )

            print("[INFO] No new records inserted.")

            return

        # ----------------------------------------------------
        # Generate synthetic clinical data
        # ----------------------------------------------------

        age = np.random.randint(18, 90, size=num_records)

        spo2 = np.round(np.random.normal(96, 3, size=num_records), 1)

        heart_rate = np.round(np.random.normal(78, 15, size=num_records), 1)

        resp_rate = np.round(np.random.normal(18, 4, size=num_records), 1)

        sys_bp = np.round(np.random.normal(122, 18, size=num_records), 1)

        dias_bp = np.round(np.random.normal(78, 12, size=num_records), 1)

        temp = np.round(np.random.normal(37.0, 0.8, size=num_records), 1)

        pain_score = np.random.randint(0, 11, size=num_records)

        hist_asthma = np.random.choice([0, 1], size=num_records, p=[0.85, 0.15])

        hist_diabetes = np.random.choice([0, 1], size=num_records, p=[0.75, 0.25])

        hist_hypertension = np.random.choice([0, 1], size=num_records, p=[0.60, 0.40])

        hist_cad = np.random.choice([0, 1], size=num_records, p=[0.85, 0.15])

        hist_stroke = np.random.choice([0, 1], size=num_records, p=[0.92, 0.08])

        # ----------------------------------------------------
        # Keep SpO2 within physical limits
        # ----------------------------------------------------

        spo2 = np.clip(spo2, 70, 100)

        # ----------------------------------------------------
        # Generate triage acuity
        #
        # 1 = most urgent
        # 5 = least urgent
        #
        # Synthetic labels for demonstration/training pipeline.
        # ----------------------------------------------------

        target_triage_acuity = np.random.choice(
            [1, 2, 3, 4, 5], size=num_records, p=[0.10, 0.20, 0.40, 0.20, 0.10]
        )

        # ----------------------------------------------------
        # Existing shared table also requires
        # hospital_expire_flag.
        #
        # This field belongs to the teammate's existing
        # database schema and is NOT used by this model.
        # ----------------------------------------------------

        hospital_expire_flag = np.zeros(num_records, dtype=int)

        # ----------------------------------------------------
        # Existing shared table also requires IDs.
        # ----------------------------------------------------

        subject_ids = np.arange(10000001, 10000001 + num_records)

        hadm_ids = np.arange(20000001, 20000001 + num_records)

        stay_ids = np.arange(30000001, 30000001 + num_records)

        # ----------------------------------------------------
        # Build rows
        # ----------------------------------------------------

        rows = []

        for i in range(num_records):

            rows.append(
                (
                    int(subject_ids[i]),
                    int(hadm_ids[i]),
                    int(stay_ids[i]),
                    int(age[i]),
                    float(spo2[i]),
                    float(heart_rate[i]),
                    float(resp_rate[i]),
                    float(sys_bp[i]),
                    float(dias_bp[i]),
                    float(temp[i]),
                    int(pain_score[i]),
                    int(hist_asthma[i]),
                    int(hist_diabetes[i]),
                    int(hist_hypertension[i]),
                    int(hist_cad[i]),
                    int(hist_stroke[i]),
                    int(hospital_expire_flag[i]),
                    int(target_triage_acuity[i]),
                )
            )

        # ----------------------------------------------------
        # Insert into shared patient_records table
        # ----------------------------------------------------

        insert_query = """
            INSERT INTO patient_records (
                subject_id,
                hadm_id,
                stay_id,
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
                hospital_expire_flag,
                target_triage_acuity
            )
            VALUES (
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
        """

        print(f"[INFO] Inserting {num_records} patient records...")

        cursor.executemany(insert_query, rows)

        conn.commit()

        print(
            f"[SUCCESS] Inserted {cursor.rowcount} "
            f"patient records into medvision.patient_records."
        )

        # ----------------------------------------------------
        # Verify record count
        # ----------------------------------------------------

        cursor.execute("SELECT COUNT(*) FROM patient_records")

        total_records = cursor.fetchone()[0]

        print(f"[INFO] patient_records now contains " f"{total_records} records.")

        # ----------------------------------------------------
        # Display target distribution
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                target_triage_acuity,
                COUNT(*)
            FROM patient_records
            GROUP BY target_triage_acuity
            ORDER BY target_triage_acuity
        """)

        print("\n[INFO] Triage distribution:")

        for acuity, count in cursor.fetchall():

            print(f"       Acuity {acuity}: {count}")

    finally:

        cursor.close()
        conn.close()


# ============================================================
# 3. MAIN
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("MEDVISION DATABASE SEED")
    print("=" * 60)

    seed_patient_records(500)

    print("=" * 60)
    print("SEEDING COMPLETE")
    print("=" * 60)
