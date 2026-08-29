import pandas as pd
import mysql.connector

# ============================================================
# STEP 1 — CSV FILE
# ============================================================

CSV_FILE = "data/xgboost_training.csv"


# ============================================================
# STEP 2 — LOAD CSV
# ============================================================

print("Loading prepared dataset...")

df = pd.read_csv(CSV_FILE)

print(f"Rows loaded: {len(df)}")
print(f"Columns: {len(df.columns)}")


# ============================================================
# STEP 3 — CHECK COLUMNS
# ============================================================

expected_columns = [
    "subject_id",
    "hadm_id",
    "stay_id",
    "age",
    "spo2",
    "heart_rate",
    "systolic_bp",
    "diastolic_bp",
    "hospital_expire_flag",
]


if list(df.columns) != expected_columns:

    raise ValueError(
        "CSV columns do not match expected columns.\n"
        f"Found: {list(df.columns)}\n"
        f"Expected: {expected_columns}"
    )


print("Column structure verified.")


# ============================================================
# STEP 4 — CONNECT TO MYSQL
# ============================================================

print("\nConnecting to MySQL...")

connection = mysql.connector.connect(
    host="localhost", user="root", password="SaraswatiMa19$", database="medvision"
)


cursor = connection.cursor()

print("MySQL connection successful.")


# ============================================================
# STEP 5 — INSERT QUERY
# ============================================================

insert_query = """

INSERT INTO xgboost_training
(
    subject_id,
    hadm_id,
    stay_id,
    age,
    spo2,
    heart_rate,
    systolic_bp,
    diastolic_bp,
    hospital_expire_flag
)

VALUES
(
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s
)

"""


# ============================================================
# STEP 6 — CONVERT DATAFRAME TO TUPLES
# ============================================================

rows = [tuple(row) for row in df.itertuples(index=False, name=None)]


# ============================================================
# STEP 7 — INSERT
# ============================================================

print(f"\nInserting {len(rows)} rows...")

cursor.executemany(insert_query, rows)


# ============================================================
# STEP 8 — COMMIT
# ============================================================

connection.commit()


print(f"Inserted rows: {cursor.rowcount}")


# ============================================================
# STEP 9 — CLOSE CONNECTION
# ============================================================

cursor.close()

connection.close()


print("\nMySQL loading complete.")
