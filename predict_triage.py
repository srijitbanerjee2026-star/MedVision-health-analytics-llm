import numpy as np
import xgboost as xgb

MODEL_FILE = "severity_model.json"
MODEL_PICKLE_FILE = "severity_model.pkl"
def predict_patient_acuity(patient_vitals):
    
    model = xgb.XGBClassifier()
    model.load_model(MODEL_FILE)

    input_data = np.array([patient_vitals], dtype=np.float32)

    predicted_class = model.predict(input_data)[0]
    acuity_score = int(predicted_class) + 1

    probabilities = model.predict_proba(input_data)[0]

    return acuity_score, probabilities

if __name__ == "__main__":
    # Example 1: Critical Patient (Low SpO2, High Heart Rate, Severe Pain, Cardiac History)
    critical_patient = [
        72.0,  # age (Elderly)
    82.0,  # spo2 (%) - Severe Hypoxia
    138.0, # heart_rate (bpm) - Severe Tachycardia
    32.0,  # resp_rate - Severe Tachypnea
    82.0,  # sys_bp - Hypotension/Shock
    48.0,  # dias_bp
    30.0,  # temp (°C) - High Fever
    9.0,   # pain_score (0-10) - Extreme Pain
    1.0,   # hist_asthma (Yes)
    1.0,   # hist_diabetes (Yes)
    1.0,   # hist_hypertension (Yes)
    1.0,   # hist_cad (Yes - Coronary Artery Disease)
    1.0    # hist_stroke (Yes)

    ]

    # Example 2: Stable Patient (Normal Vitals, Minor Pain)
    stable_patient = [
        25.0,  # age
        99.0,  # spo2 (%)
        72.0,  # heart_rate
        14.0,  # resp_rate
        118.0, # sys_bp
        78.0,  # dias_bp
        36.8,  # temp (°C)
        2.0,   # pain_score
        0.0,   # hist_asthma
        0.0,   # hist_diabetes
        0.0,   # hist_hypertension
        0.0,   # hist_cad
        0.0    # hist_stroke
    ]

    print("--- Testing Critical Patient ---")
    score, probs = predict_patient_acuity(critical_patient)
    print(f"Predicted Triage Severity Score: Level {score}")
    print(f"Confidence Probabilities (Levels 1-5): {[round(p, 3) for p in probs]}\n")

    print("--- Testing Stable Patient ---")
    score, probs = predict_patient_acuity(stable_patient)
    print(f"Predicted Triage Severity Score: Level {score}")
    print(f"Confidence Probabilities (Levels 1-5): {[round(p, 3) for p in probs]}")
