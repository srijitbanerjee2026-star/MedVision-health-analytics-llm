from pathlib import Path

import pandas as pd

# ============================================================
# PATHS
# ============================================================

BASE = Path("mimic-iv-clinical-database-demo-2.2")

HOSP = BASE / "hosp"

ICU = BASE / "icu"


OUTPUT = Path("data/xgboost_training.csv")


# ============================================================
# LOAD PATIENTS
# ============================================================

print("\n[1/8] Loading patients.csv...")

patients = pd.read_csv(HOSP / "patients.csv")

patients = patients[["subject_id", "anchor_age"]].copy()


patients = patients.rename(columns={"anchor_age": "age"})


print(f"Patients loaded: {len(patients):,}")


# ============================================================
# LOAD ADMISSIONS
# ============================================================

print("\n[2/8] Loading admissions.csv...")

admissions = pd.read_csv(HOSP / "admissions.csv")

admissions = admissions[["subject_id", "hadm_id", "hospital_expire_flag"]].copy()


print(f"Admissions loaded: {len(admissions):,}")


# ============================================================
# LOAD ICU STAYS
# ============================================================

print("\n[3/8] Loading icustays.csv...")

icustays = pd.read_csv(ICU / "icustays.csv")

icustays = icustays[["subject_id", "hadm_id", "stay_id", "intime", "outtime"]].copy()


icustays["intime"] = pd.to_datetime(icustays["intime"])

icustays["outtime"] = pd.to_datetime(icustays["outtime"])


print(f"ICU stays loaded: {len(icustays):,}")


# ============================================================
# MERGE PATIENT + ADMISSION + ICU STAY
# ============================================================

print("\n[4/8] Merging patient information...")


base = icustays.merge(patients, on="subject_id", how="left").merge(
    admissions, on=["subject_id", "hadm_id"], how="left"
)


print(f"Base dataset: {len(base):,} ICU stays")


print("\nBase columns:")

print(base.columns.tolist())


# ============================================================
# LOAD ITEM DICTIONARY
# ============================================================

print("\n[5/8] Loading d_items.csv...")

items = pd.read_csv(ICU / "d_items.csv")

items = items[["itemid", "label", "abbreviation", "category", "unitname"]].copy()


# ============================================================
# FIND ITEM IDS
# ============================================================


def find_items(items, keywords):

    mask = False

    for keyword in keywords:

        current = (
            items["label"].fillna("").str.contains(keyword, case=False, regex=False)
        )

        mask = mask | current

    return items.loc[mask].copy()


heart_rate_items = find_items(items, ["heart rate"])


spo2_items = find_items(items, ["oxygen saturation", "o2 saturation", "o2 sat", "spo2"])


systolic_items = find_items(
    items, ["systolic blood pressure", "blood pressure systolic"]
)


diastolic_items = find_items(
    items, ["diastolic blood pressure", "blood pressure diastolic"]
)

# ============================================================
# SHOW MATCHES
# ============================================================

print("\nHeart rate candidates:")
print(
    heart_rate_items[
        ["itemid", "label", "abbreviation", "category", "unitname"]
    ].to_string(index=False)
)


print("\nSpO2 candidates:")
print(
    spo2_items[["itemid", "label", "abbreviation", "category", "unitname"]].to_string(
        index=False
    )
)


print("\nSystolic BP candidates:")
print(
    systolic_items[
        ["itemid", "label", "abbreviation", "category", "unitname"]
    ].to_string(index=False)
)


print("\nDiastolic BP candidates:")
print(
    diastolic_items[
        ["itemid", "label", "abbreviation", "category", "unitname"]
    ].to_string(index=False)
)

# ============================================================
# STEP 26 — LOAD CHARTEVENTS
# ============================================================

print("\n[6/8] Loading chartevents.csv...")

chartevents = pd.read_csv(
    ICU / "chartevents.csv",
    usecols=[
        "subject_id",
        "hadm_id",
        "stay_id",
        "charttime",
        "itemid",
        "valuenum",
        "valueuom",
    ],
)

print(f"Chartevents loaded: {len(chartevents):,}")

# ============================================================
# STEP 27 — ACTUAL VITAL-SIGN ITEM IDs
# ============================================================

HEART_RATE_ID = 220045

SPO2_ID = 220277

SYSTOLIC_BP_ID = 220179

DIASTOLIC_BP_ID = 220180


VITAL_ITEM_IDS = [HEART_RATE_ID, SPO2_ID, SYSTOLIC_BP_ID, DIASTOLIC_BP_ID]


print("\nUsing the following MIMIC item IDs:")

print("Heart Rate:", HEART_RATE_ID)

print("SpO2:", SPO2_ID)

print("Systolic BP:", SYSTOLIC_BP_ID)

print("Diastolic BP:", DIASTOLIC_BP_ID)


# ============================================================
# STEP 28 — KEEP ONLY REQUIRED VITALS
# ============================================================

chartevents = chartevents[chartevents["itemid"].isin(VITAL_ITEM_IDS)].copy()


print(f"\nVital measurements retained: " f"{len(chartevents):,}")

# ============================================================
# STEP 29 — VERIFY VITAL IDS
# ============================================================

print("\nVital ID counts:")

print(chartevents["itemid"].value_counts().sort_index())

# ============================================================
# STEP 30 — CONVERT TIMESTAMP
# ============================================================

chartevents["charttime"] = pd.to_datetime(chartevents["charttime"])

# ============================================================
# STEP 31 — CONVERT MEASUREMENTS TO NUMERIC
# ============================================================

chartevents["valuenum"] = pd.to_numeric(chartevents["valuenum"], errors="coerce")

chartevents = chartevents.dropna(subset=["valuenum"])

# ============================================================
# STEP 32 — ADD ICU ADMISSION TIME
# ============================================================

chartevents = chartevents.merge(
    base[["subject_id", "hadm_id", "stay_id", "intime"]],
    on=["subject_id", "hadm_id", "stay_id"],
    how="inner",
)

# ============================================================
# STEP 33 — HOURS FROM ICU ADMISSION
# ============================================================

chartevents["hours_from_icu"] = (
    chartevents["charttime"] - chartevents["intime"]
).dt.total_seconds() / 3600


# ============================================================
# STEP 34 — FIRST 24 HOURS
# ============================================================

chartevents = chartevents[
    (chartevents["hours_from_icu"] >= 0) & (chartevents["hours_from_icu"] <= 24)
].copy()


print("\nMeasurements in first 24 hours:", len(chartevents))

# ============================================================
# STEP 35 — MAP ITEM IDs TO FEATURE NAMES
# ============================================================


def get_feature_name(itemid):

    if itemid == HEART_RATE_ID:
        return "heart_rate"

    elif itemid == SPO2_ID:
        return "spo2"

    elif itemid == SYSTOLIC_BP_ID:
        return "systolic_bp"

    elif itemid == DIASTOLIC_BP_ID:
        return "diastolic_bp"

    else:
        return None


chartevents["feature"] = chartevents["itemid"].apply(get_feature_name)


print("\nFeature mapping:")

print(
    chartevents[["itemid", "feature"]]
    .drop_duplicates()
    .sort_values("itemid")
    .to_string(index=False)
)

# ============================================================
# STEP 37 — MEDIAN VITAL VALUE
# ============================================================

vitals = (
    chartevents.groupby(["subject_id", "hadm_id", "stay_id", "feature"])["valuenum"]
    .median()
    .reset_index()
)


print("\nMedian vital values:")

print(vitals.head(20).to_string(index=False))

# ============================================================
# STEP 38 — PIVOT
# ============================================================

vitals = vitals.pivot_table(
    index=["subject_id", "hadm_id", "stay_id"], columns="feature", values="valuenum"
).reset_index()

vitals.columns.name = None

print("\nWide vital dataset:")

print(vitals.head(10).to_string(index=False))

# ============================================================
# STEP 40 — MERGE FEATURES WITH OUTCOME
# ============================================================

dataset = base.merge(vitals, on=["subject_id", "hadm_id", "stay_id"], how="inner")

dataset = dataset[
    [
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
]

print("\nFinal dataset shape:")

print(dataset.shape)


print("\nFinal columns:")

print(dataset.columns.tolist())


print("\nFirst 10 records:")

print(dataset.head(10).to_string(index=False))

print("\nMissing values:")

print(dataset.isnull().sum())

dataset.fillna(0)

print("\nFeature statistics:")

print(dataset[["age", "spo2", "heart_rate", "systolic_bp", "diastolic_bp"]].describe())

dataset = dataset[dataset["age"].between(18, 100)]

dataset = dataset[dataset["spo2"].between(50, 100)]

dataset = dataset[dataset["heart_rate"].between(20, 250)]

dataset = dataset[dataset["systolic_bp"].between(40, 300)]

dataset = dataset[dataset["diastolic_bp"].between(20, 200)]

print("\nHospital mortality distribution:")

print(dataset["hospital_expire_flag"].value_counts(dropna=False))

# ============================================================
# STEP 46 — SAVE FINAL DATASET
# ============================================================

OUTPUT.parent.mkdir(parents=True, exist_ok=True)


dataset.to_csv(OUTPUT, index=False)


print(f"\nSaved dataset to: {OUTPUT}")


print(f"Final number of rows: {len(dataset):,}")
