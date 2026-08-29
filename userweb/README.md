# MedVision Guard

AI-powered clinical decision support & ER triage dashboard — a FastAPI
backend (`app.py`) plus a React frontend (`frontend/`).

## Features

- Manually enter a patient's vitals (patient ID, age, SpO2, heart rate, systolic BP, clinical findings) and run a triage analysis — no file upload required
- **Criticality** view — patient vitals with out-of-range flagging, an animated triage severity ring, and clinical findings
- Live backend health check

## Backend (`app.py`)

```bash
pip install -r requirements.txt
python app.py
```

This starts the FastAPI server on `http://127.0.0.1:8000`. Endpoints:

- `GET /` — health check, returns `{"status": "active", "system": "..."}`
- `POST /analyze-vitals` — accepts `{patient_id, age, spo2, heart_rate, systolic_bp, findings}` and returns the parsed vitals plus a locally computed `triage_severity_level` (1-5)

Allowed CORS origins default to the Vite dev server (`http://localhost:5173`).
Override with a comma-separated `ALLOWED_ORIGINS` environment variable.

## Frontend (`frontend/`)

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`). By default the
frontend calls the backend at `http://127.0.0.1:8000`; override with a
`VITE_BACKEND_URL` environment variable (e.g. in a `frontend/.env` file).
