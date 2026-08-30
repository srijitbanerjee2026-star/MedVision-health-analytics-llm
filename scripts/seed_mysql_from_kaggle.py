# seed_mysql_from_kaggle.py 
import csv
import mysql.connector
import os
import kagglehub

# MySQL Configuration
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "user67",  
    "database": "medvision"
}

def safe_int(val, default=0):
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return default

def safe_float(val, default=98.6):
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return default

def download_and_seed():
    print("[INFO] Downloading dataset via KaggleHub...")
    download_dir = kagglehub.dataset_download("reaper0ai/nhamcs-2018-22")
    print("[INFO] Path to dataset files:", download_dir)

   
    csv_file_path = None
    for root, dirs, files in os.walk(download_dir):
        for file in files:
            if file.endswith(".csv"):
                csv_file_path = os.path.join(root, file)
                break

    if not csv_file_path:
        print("[ERROR] No .csv file found in the downloaded dataset path!")
        return

    print(f"[INFO] Found CSV File: {csv_file_path}")

    
    print("[INFO] Connecting to MySQL database 'medvision_db'...")
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
    except mysql.connector.Error as err:
        print(f"[ERROR] Database Connection Failed: {err}")
        return

    
    batch_data = []
    with open(csv_file_path, mode="r", encoding="utf-8", errors="ignore") as file:
        reader = csv.DictReader(file)
        
        for i, row in enumerate(reader):
            age = safe_int(row.get("age"), 45)
            sex = str(row.get("sex", "Unknown"))
            spo2 = safe_int(row.get("spo2"), 96)
            heart_rate = safe_int(row.get("heart_rate"), 75)
            resp_rate = safe_int(row.get("resp_rate"), 16)
            sys_bp = safe_int(row.get("sys_bp"), 120)
            dias_bp = safe_int(row.get("dias_bp"), 80)
            temp = safe_float(row.get("temp"), 98.6)
            pain_score = safe_int(row.get("pain_score"), 0)

            chief_complaint = row.get("chief_complaint_text", "General discomfort")
            if not chief_complaint or chief_complaint.strip() == "":
                chief_complaint = "Routine evaluation"

            h_asthma = safe_int(row.get("hist_asthma"), 0)
            h_diab = safe_int(row.get("hist_diabetes_t2") or row.get("hist_diabetes_t1"), 0)
            h_htn = safe_int(row.get("hist_hypertension"), 0)
            h_cad = safe_int(row.get("hist_cad"), 0)
            h_stroke = safe_int(row.get("hist_stroke"), 0)

            disease_label = row.get("is_injury_poison") or "Acute Medical Condition"
            triage_acuity = safe_int(row.get("target_triage_acuity"), 3)
            triage_acuity = max(1, min(5, triage_acuity))

            patient_id = f"PAT-NHAMCS-{1000 + i}"

            record = (
                patient_id, age, sex, spo2, heart_rate, resp_rate,
                sys_bp, dias_bp, temp, pain_score, str(chief_complaint),
                h_asthma, h_diab, h_htn, h_cad, h_stroke,
                str(disease_label), triage_acuity
            )
            batch_data.append(record)

    
    print(f"[INFO] Inserting {len(batch_data)} records into MySQL table 'patient_records'...")
    insert_sql = """
    INSERT INTO patient_records 
    (patient_id, age, sex, spo2, heart_rate, resp_rate, sys_bp, dias_bp, temp, pain_score,
     chief_complaint_text, hist_asthma, hist_diabetes, hist_hypertension, hist_cad, hist_stroke,
     disease_label, target_triage_acuity)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    chunk_size = 500
    for j in range(0, len(batch_data), chunk_size):
        chunk = batch_data[j:j + chunk_size]
        cursor.executemany(insert_sql, chunk)
        conn.commit()

    print("[SUCCESS] MySQL database successfully populated with NHAMCS 2018-22 dataset.")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    download_and_seed()