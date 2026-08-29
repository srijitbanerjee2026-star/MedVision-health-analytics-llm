import sqlite3
import os

SQL_FILE = "medvision_full.sql"
DB_FILE = "medvision_guard.db"

def build_sqlite():
    if not os.path.exists(SQL_FILE):
        raise FileNotFoundError(
            f"'{SQL_FILE}' not found. Run 'git pull origin main' to get the file from GitHub."
        )

    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    print(f"[INFO] Reading '{SQL_FILE}' pulled from GitHub...")
    with open(SQL_FILE, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Adapt MySQL DDL statements to SQLite dialect
    clean_lines = []
    for line in sql_content.splitlines():
        if line.startswith("CREATE DATABASE") or line.startswith("USE medvision"):
            continue
        line = line.replace("AUTO_INCREMENT", "AUTOINCREMENT").replace("FLOAT", "REAL")
        clean_lines.append(line)

    clean_script = "\n".join(clean_lines)

    print(f"[INFO] Building local database '{DB_FILE}'...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.executescript(clean_script)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM patient_records")
    row_count = cursor.fetchone()[0]
    conn.close()

    print(f"✅ Created '{DB_FILE}' with {row_count} patient records!")

if __name__ == "__main__":
    build_sqlite()