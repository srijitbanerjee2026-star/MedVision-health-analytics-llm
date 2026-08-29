from pathlib import Path
import pandas as pd

DATA_DIRS = [
    Path("mimic-iv-clinical-database-demo-2.2/hosp"),
    Path("mimic-iv-clinical-database-demo-2.2/icu"),
]


for directory in DATA_DIRS:

    print("\n" + "=" * 80)
    print(f"DIRECTORY: {directory}")
    print("=" * 80)

    if not directory.exists():
        print("Directory does not exist.")
        continue

    csv_files = list(directory.glob("*.csv"))

    print(f"Found {len(csv_files)} CSV files.")

    for file in csv_files:

        print("\n" + "-" * 80)
        print(f"FILE: {file}")
        print("-" * 80)

        try:

            df = pd.read_csv(file, nrows=5)

            print("Columns:")
            print(df.columns.tolist())

            print("\nFirst 5 rows:")
            print(df.to_string(index=False))

        except Exception as e:

            print(f"ERROR: {e}")
