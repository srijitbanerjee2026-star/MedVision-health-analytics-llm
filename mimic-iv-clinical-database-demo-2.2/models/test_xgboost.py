import joblib
import pandas as pd

# ============================================================
# LOAD MODEL
# ============================================================

model = joblib.load("saved_models/xgboost_risk.pkl")


# ============================================================
# TEST PATIENT
# ============================================================

patient = pd.DataFrame(
    [{"age": 67, "spo2": 88, "heart_rate": 125, "systolic_bp": 90, "diastolic_bp": 55}]
)


# ============================================================
# PREDICT
# ============================================================

prediction = model.predict(patient)[0]


probability = model.predict_proba(patient)[0][1]


# ============================================================
# OUTPUT
# ============================================================

print("Predicted class:", int(prediction))


print("Estimated hospital mortality probability:", round(float(probability), 4))
