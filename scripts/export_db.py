import mysql.connector

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "user67",
    "database": "medvision",
}


def export_to_sql():
    print("[INFO] Connecting to 'medvision' database...")
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM patient_records")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("[ERROR] Table 'patient_records' is empty!")
        return

    print(f"[INFO] Fetched {len(rows)} records. Writing to medvision_full.sql...")

    with open("medvision_full.sql", "w", encoding="utf-8") as f:
        f.write("CREATE DATABASE IF NOT EXISTS medvision;\nUSE medvision;\n\n")
        f.write("DROP TABLE IF EXISTS patient_records;\n")
        f.write("""CREATE TABLE patient_records (
    visit_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id VARCHAR(50),
    age INT,
    sex VARCHAR(20),
    spo2 INT,
    heart_rate INT,
    resp_rate INT,
    sys_bp INT,
    dias_bp INT,
    temp FLOAT,
    pain_score INT,
    chief_complaint_text TEXT,
    hist_asthma INT DEFAULT 0,
    hist_diabetes INT DEFAULT 0,
    hist_hypertension INT DEFAULT 0,
    hist_cad INT DEFAULT 0,
    hist_stroke INT DEFAULT 0,
    disease_label VARCHAR(100),
    target_triage_acuity INT
);\n\n""")

        columns = list(rows[0].keys())

        if "visit_id" in columns:
            columns.remove("visit_id")

        cols_str = ", ".join(columns)

        for row in rows:
            values = []
            for col in columns:
                val = row[col]
                if val is None:
                    values.append("NULL")
                elif isinstance(val, str):
                    escaped_val = val.replace("'", "''").replace("\\", "\\\\")
                    values.append(f"'{escaped_val}'")
                else:
                    values.append(str(val))
            val_str = ", ".join(values)
            f.write(f"INSERT INTO patient_records ({cols_str}) VALUES ({val_str});\n")

    print("[SUCCESS] Export complete! Created 'medvision_full.sql'.")


if __name__ == "__main__":
    export_to_sql()
