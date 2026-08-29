import mysql.connector
import pandas as pd
import joblib

from sklearn.model_selection import GroupShuffleSplit

from sklearn.pipeline import Pipeline

from sklearn.impute import SimpleImputer

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)

from xgboost import XGBClassifier

# ============================================================
# STEP 1 — CONNECT TO MYSQL
# ============================================================

print("Connecting to MySQL...")

connection = mysql.connector.connect(
    host="localhost", user="root", password="SaraswatiMa19$", database="medvision"
)


# ============================================================
# STEP 2 — READ DATA FROM MYSQL
# ============================================================

query = """

SELECT

    subject_id,

    hadm_id,

    stay_id,

    age,

    spo2,

    heart_rate,

    systolic_bp,

    diastolic_bp,

    hospital_expire_flag

FROM xgboost_training

"""


df = pd.read_sql(query, connection)


connection.close()


print(f"Dataset loaded from MySQL: {df.shape}")


# ============================================================
# STEP 3 — DEFINE FEATURES
# ============================================================

FEATURES = ["age", "spo2", "heart_rate", "systolic_bp", "diastolic_bp"]


TARGET = "hospital_expire_flag"


X = df[FEATURES]

y = df[TARGET]

groups = df["subject_id"]


# ============================================================
# STEP 4 — CHECK TARGET
# ============================================================

print("\nTarget distribution:")

print(y.value_counts())


# ============================================================
# STEP 5 — PATIENT-LEVEL TRAIN/TEST SPLIT
# ============================================================

splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)


train_indices, test_indices = next(splitter.split(X, y, groups=groups))


X_train = X.iloc[train_indices]

X_test = X.iloc[test_indices]


y_train = y.iloc[train_indices]

y_test = y.iloc[test_indices]


print("\nTraining rows:", len(X_train))

print("Testing rows:", len(X_test))


print("Training patients:", groups.iloc[train_indices].nunique())

print("Testing patients:", groups.iloc[test_indices].nunique())


# ============================================================
# STEP 6 — CALCULATE CLASS WEIGHT
# ============================================================

negative_count = (y_train == 0).sum()

positive_count = (y_train == 1).sum()


if positive_count == 0:

    raise ValueError("Training set contains no positive cases.")


scale_pos_weight = negative_count / positive_count


print("\nNegative training cases:", negative_count)

print("Positive training cases:", positive_count)

print("scale_pos_weight:", scale_pos_weight)


# ============================================================
# STEP 7 — CREATE XGBOOST PIPELINE
# ============================================================

model = Pipeline(
    [
        ("imputer", SimpleImputer(strategy="median")),
        (
            "xgboost",
            XGBClassifier(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                objective="binary:logistic",
                eval_metric="logloss",
                scale_pos_weight=scale_pos_weight,
                random_state=42,
            ),
        ),
    ]
)


# ============================================================
# STEP 8 — TRAIN
# ============================================================

print("\nTraining XGBoost...")


model.fit(X_train, y_train)


print("Training complete.")


# ============================================================
# STEP 9 — PREDICTIONS
# ============================================================

predictions = model.predict(X_test)


probabilities = model.predict_proba(X_test)[:, 1]


# ============================================================
# STEP 10 — EVALUATION
# ============================================================

print("\n==============================")

print("MODEL PERFORMANCE")

print("==============================")


accuracy = accuracy_score(y_test, predictions)


print("\nAccuracy:", round(accuracy, 4))


# ------------------------------------------------------------
# ROC-AUC
# ------------------------------------------------------------

if y_test.nunique() == 2:

    auc = roc_auc_score(y_test, probabilities)

    print("ROC-AUC:", round(auc, 4))

else:

    print("ROC-AUC: unavailable " "(test set has one class)")


# ------------------------------------------------------------
# CLASSIFICATION REPORT
# ------------------------------------------------------------

print("\nClassification Report:")


print(classification_report(y_test, predictions, zero_division=0))


# ------------------------------------------------------------
# CONFUSION MATRIX
# ------------------------------------------------------------

print("Confusion Matrix:")


print(confusion_matrix(y_test, predictions))


# ============================================================
# STEP 11 — SAVE MODEL
# ============================================================

model_path = "saved_models/xgboost_risk.pkl"


os.makedirs("saved_models", exist_ok=True)
joblib.dump(model, model_path)


print(f"\nModel saved to: {model_path}")
