from pathlib import Path
import pandas as pd

# ============================================================
# PATH
# ============================================================

BASE = Path("mimic-iv-clinical-database-demo-2.2")

ITEMS_FILE = BASE / "icu" / "d_items.csv"


# ============================================================
# LOAD ITEM DICTIONARY
# ============================================================

print("Loading d_items.csv...")

items = pd.read_csv(ITEMS_FILE)

print(f"Loaded {len(items):,} item definitions.")


# ============================================================
# SEARCH TERMS
# ============================================================

searches = {
    "heart_rate": ["heart rate"],
    "spo2": ["oxygen saturation", "o2 saturation", "o2 sat", "spo2"],
    "systolic_bp": ["systolic blood pressure", "blood pressure systolic"],
    "diastolic_bp": ["diastolic blood pressure", "blood pressure diastolic"],
}


# ============================================================
# SEARCH
# ============================================================

for feature, keywords in searches.items():

    print("\n" + "=" * 80)
    print(f"{feature.upper()}")
    print("=" * 80)

    mask = False

    for keyword in keywords:

        current = (
            items["label"].fillna("").str.contains(keyword, case=False, regex=False)
        )

        mask = mask | current

    results = items.loc[
        mask, ["itemid", "label", "abbreviation", "category", "unitname", "param_type"]
    ]

    if results.empty:

        print("NO MATCHES FOUND")

    else:

        print(results.sort_values("itemid").to_string(index=False))
