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
