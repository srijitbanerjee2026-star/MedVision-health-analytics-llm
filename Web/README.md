# MedVision Guard — Frontend

AI-powered clinical decision support & ER triage dashboard, built with Streamlit.

## Features

- Upload a diagnostic report (PDF) and send it to a FastAPI backend for analysis
- **Criticality** tab — patient vitals with out-of-range flagging, an animated triage severity ring, and clinical findings
- **Diagnosis** tab — ranked disease probability breakdown with per-disease estimated life expectancy
- Live backend health check, cached analysis (no re-upload on unrelated reruns), and clear error states (timeout / connection / HTTP errors)

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

By default the app looks for a backend at `http://127.0.0.1:8000`. Override with:

```bash
export BACKEND_URL="https://your-backend.example.com"
```

## Backend contract

The app expects `POST {BACKEND_URL}/analyze-pdf` (multipart file upload, field name `file`) to return:

```json
{
  "status": "success",
  "parsed_vitals": {
    "patient_id": "PAT-1082",
    "age": 62,
    "spo2": 88,
    "heart_rate": 115,
    "systolic_bp": 145,
    "findings": "..."
  },
  "triage_severity_level": 4,
  "predicted_disease": "Pneumonia",
  "disease_confidence": 0.89,
  "disease_probabilities": {
    "Pneumonia": 0.89,
    "Bronchitis": 0.06,
    "COVID-19": 0.03,
    "Normal": 0.02
  },
  "life_expectancy_years": {
    "Pneumonia": 8.4,
    "Bronchitis": 14.1,
    "COVID-19": 12.7,
    "Normal": 22.0
  },
  "raw_text_snippet": "..."
}
```

`GET {BACKEND_URL}/` should return `{"status": "active", "system": "..."}` for the health check.

## Development

`mock_backend.py` is a dependency-free mock of the above contract for testing the UI without a real backend:

```bash
python mock_backend.py
streamlit run app.py
```
