import os

from dotenv import load_dotenv
import mysql.connector

# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("DB_NAME", "medvision"),
}


# ============================================================
# REQUIRED CLINICAL FEATURES
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
# REQUIRED TARGET
# ============================================================

TARGET_COL = "target_triage_acuity"


# ============================================================
# CHECK DATABASE
# ============================================================


def check_database():

    print("=" * 60)
    print("MEDVISION DATABASE CHECK")
    print("=" * 60)

    if not DB_CONFIG["password"]:

        raise ValueError("MYSQL_PASSWORD was not found in .env")

    print("[INFO] Connecting to MySQL...")
    print("[INFO] Database: medvision")
    print("[INFO] Table: patient_records")

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:

        # ----------------------------------------------------
        # 1. Check patient_records exists
        # ----------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'medvision'
              AND table_name = 'patient_records'
        """)

        table_exists = cursor.fetchone()[0]

        if table_exists == 0:

            raise RuntimeError("Table medvision.patient_records does not exist.")

        print("[SUCCESS] patient_records table exists.")

        # ----------------------------------------------------
        # 2. Get actual table columns
        # ----------------------------------------------------

        cursor.execute("""
            SELECT COLUMN_NAME
            FROM information_schema.columns
            WHERE table_schema = 'medvision'
              AND table_name = 'patient_records'
            ORDER BY ORDINAL_POSITION
        """)

        columns = [row[0] for row in cursor.fetchall()]

        print("\n[INFO] Actual patient_records columns:")

        for column in columns:

            print(f"       {column}")

        # ----------------------------------------------------
        # 3. Check clinical features
        # ----------------------------------------------------

        missing_features = [column for column in FEATURE_COLS if column not in columns]

        if missing_features:

            raise RuntimeError("Missing clinical columns: " f"{missing_features}")

        print("\n[SUCCESS] All required clinical features exist.")

        # ----------------------------------------------------
        # 4. Check target
        # ----------------------------------------------------

        if TARGET_COL not in columns:

            print("\n[WARNING] target_triage_acuity does " "not exist.")

            print("[WARNING] No synthetic target will be created.")

            print("[WARNING] You need a real triage label " "from the source dataset.")

            return

        print("\n[SUCCESS] target_triage_acuity exists.")

        # ----------------------------------------------------
        # 5. Count actual patient records
        # ----------------------------------------------------

        cursor.execute("SELECT COUNT(*) FROM patient_records")

        total = cursor.fetchone()[0]

        print(f"\n[INFO] Actual patient records: {total}")

        if total == 0:

            print("[WARNING] patient_records is empty.")

            return

        # ----------------------------------------------------
        # 6. Check missing values
        # ----------------------------------------------------

        print("\n[INFO] Missing values in clinical features:")

        for column in FEATURE_COLS:

            cursor.execute(f"""
                SELECT COUNT(*)
                FROM patient_records
                WHERE `{column}` IS NULL
                """)

            missing = cursor.fetchone()[0]

            print(f"       {column}: {missing}")

        # ----------------------------------------------------
        # 7. Check target values
        # ----------------------------------------------------

        cursor.execute("""
            SELECT
                target_triage_acuity,
                COUNT(*)
            FROM patient_records
            GROUP BY target_triage_acuity
            ORDER BY target_triage_acuity
        """)

        target_rows = cursor.fetchall()

        print("\n[INFO] Actual target distribution:")

        for target, count in target_rows:

            print(f"       {target}: {count}")

        # ----------------------------------------------------
        # 8. Count labeled records
        # ----------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*)
            FROM patient_records
            WHERE target_triage_acuity IS NOT NULL
        """)

        labeled = cursor.fetchone()[0]

        print(f"\n[INFO] Records with real target labels: " f"{labeled}")

        if labeled == 0:

            print("\n[WARNING] There are no target labels.")

            print(
                "[WARNING] LightGBM cannot be trained for "
                "triage prediction until real labels exist."
            )

        elif labeled < total:

            print(f"[WARNING] {total - labeled} records " "have no target label.")

        else:

            print("[SUCCESS] Every patient record has " "a target label.")

    finally:

        cursor.close()
        conn.close()

    print("\n" + "=" * 60)
    print("DATABASE CHECK COMPLETE")
    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    check_database()


'''import os

from dotenv import load_dotenv
import numpy as np
import mysql.connector

load_dotenv()

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": "medvision",
}

NUM_RECORDS = 500


def main():

    print("=" * 60)
    print("MEDVISION RISK DATA POPULATION")
    print("=" * 60)

    np.random.seed(42)

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:

        # --------------------------------------------------
        # 1. Check / add target_triage_acuity
        # --------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'medvision'
              AND TABLE_NAME = 'patient_records'
              AND COLUMN_NAME = 'target_triage_acuity'
        """)

        if cursor.fetchone()[0] == 0:

            print("[INFO] Adding target_triage_acuity...")

            cursor.execute("""
                ALTER TABLE patient_records
                ADD COLUMN target_triage_acuity INT NULL
            """)

            conn.commit()

        else:
            print("[INFO] target_triage_acuity already exists.")

        # --------------------------------------------------
        # 2. Check existing records
        # --------------------------------------------------

        cursor.execute("SELECT COUNT(*) FROM patient_records")

        existing = cursor.fetchone()[0]

        print(f"[INFO] Existing patient_records: {existing}")

        if existing > 0:
            print("[INFO] Records already exist.")
            print("[INFO] Nothing was inserted.")
            return

        # --------------------------------------------------
        # 3. Generate identifiers
        # --------------------------------------------------

        subject_ids = np.arange(10000001, 10000001 + NUM_RECORDS)

        hadm_ids = np.arange(20000001, 20000001 + NUM_RECORDS)

        stay_ids = np.arange(30000001, 30000001 + NUM_RECORDS)

        # --------------------------------------------------
        # 4. Generate clinical features
        # --------------------------------------------------

        age = np.random.randint(18, 90, NUM_RECORDS)

        spo2 = np.clip(np.round(np.random.normal(96, 3, NUM_RECORDS), 1), 70, 100)

        heart_rate = np.round(np.random.normal(78, 15, NUM_RECORDS), 1)

        resp_rate = np.round(np.random.normal(18, 4, NUM_RECORDS), 1)

        sys_bp = np.round(np.random.normal(122, 18, NUM_RECORDS), 1)

        dias_bp = np.round(np.random.normal(78, 12, NUM_RECORDS), 1)

        temp = np.round(np.random.normal(37.0, 0.8, NUM_RECORDS), 1)

        pain_score = np.random.randint(0, 11, NUM_RECORDS)

        hist_asthma = np.random.choice([0, 1], NUM_RECORDS, p=[0.85, 0.15])

        hist_diabetes = np.random.choice([0, 1], NUM_RECORDS, p=[0.75, 0.25])

        hist_hypertension = np.random.choice([0, 1], NUM_RECORDS, p=[0.60, 0.40])

        hist_cad = np.random.choice([0, 1], NUM_RECORDS, p=[0.85, 0.15])

        hist_stroke = np.random.choice([0, 1], NUM_RECORDS, p=[0.92, 0.08])

        # --------------------------------------------------
        # 5. Generate LightGBM target
        # --------------------------------------------------

        target_triage_acuity = np.random.choice(
            [1, 2, 3, 4, 5], NUM_RECORDS, p=[0.10, 0.20, 0.40, 0.20, 0.10]
        )

        # --------------------------------------------------
        # 6. Populate existing hospital_expire_flag
        #
        # This column is required by the existing schema.
        #
        # We keep it 0 for these synthetic triage records.
        # It is NOT used by train_risk_model.py.
        # --------------------------------------------------

        hospital_expire_flag = np.zeros(NUM_RECORDS, dtype=int)

        # --------------------------------------------------
        # 7. Build rows
        # --------------------------------------------------

        rows = []

        for i in range(NUM_RECORDS):

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

        # --------------------------------------------------
        # 8. Insert into shared patient_records
        # --------------------------------------------------

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

        print(f"[INFO] Inserting {NUM_RECORDS} records...")

        cursor.executemany(insert_query, rows)

        conn.commit()

        print(f"[SUCCESS] Inserted {cursor.rowcount} records.")

        # --------------------------------------------------
        # 9. Verify patient_records
        # --------------------------------------------------

        cursor.execute("SELECT COUNT(*) FROM patient_records")

        count = cursor.fetchone()[0]

        print(f"[SUCCESS] patient_records: {count}")

        # --------------------------------------------------
        # 10. Verify triage distribution
        # --------------------------------------------------

        cursor.execute("""
            SELECT
                target_triage_acuity,
                COUNT(*)
            FROM patient_records
            GROUP BY target_triage_acuity
            ORDER BY target_triage_acuity
        """)

        print("\nTriage distribution:")

        for acuity, number in cursor.fetchall():

            print(f"  Acuity {acuity}: {number}")

    finally:

        cursor.close()
        conn.close()

    print("=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()'''
