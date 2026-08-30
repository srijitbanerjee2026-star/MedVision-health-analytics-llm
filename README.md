# MedVision: AI-Powered Clinical Triage Analytics Engine

MedVision is an enterprise-grade Clinical Decision Support System (CDSS) that evaluates unstructured patient chief complaints and real-time vital signs to deliver instant triage acuity predictions, disease classification, length of stay (LOS) estimates, and ICU escalation risks.

---

## System Architecture & Data Pipeline

MedVision operates on a hybrid data pipeline architecture split into Offline Training and Online Runtime phases:

======================================== OFFLINE TRAINING PIPELINE ========================================

 ┌──────────────────────┐        SQL Transformations       ┌────────────────────────┐
 │   Kaggle API Data    ├─────────────────────────────────►│ Model Training Pipeline│
 │ (Historical Datasets)│        & Feature Extraction      │ (DistilBERT/XGB/LGB)   │
 └──────────────────────┘                                  └───────────┬────────────┘
                                                                       │ Serialized Artifacts
                                                                       ▼ (.pkl / PyTorch Weights)

======================================== ONLINE RUNTIME PIPELINE =========================================

┌────────────────────────┐         Asynchronous HTTP         ┌────────────────────────┐
│  React.js Frontend UI  ├──────────────────────────────────►│ FastAPI Backend Engine │
│ (Single-Page App/Vite) │          (JSON Payload)           │ (HealthConsensusEngine)│
└────────────────────────┘                                   └───────────┬────────────┘
                                                                         │
                                                 ┌───────────────────────┴───────────────────────┐
                                                 ▼                                               ▼
                                  ┌─────────────────────────────┐                 ┌─────────────────────────────┐
                                  │   Multi-Model Inference     │                 │   Supabase PostgreSQL DB    │
                                  │ ├── DistilBERT (NLP)        │                 │ └── master_patient_triage   │
                                  │ ├── XGBoost (ESI Acuity)    │                 │     (Real-Time Anonymized   │
                                  │ └── LightGBM (LOS & Risk)   │                 │      Patient Ingestion)    │
                                  └─────────────────────────────┘                 └─────────────────────────────┘

### 1. Offline Training Phase
* Data Ingestion: Historical clinical triage and ESI records are programmatically ingested via the Kaggle API.
* SQL Transformations: Raw relational datasets are cleaned, normalized, and queried using SQL to extract feature matrices (age, pulse, blood pressure, SpO2, temperature, pain score, and chief complaints).
* Model Training: Cleaned datasets train three specialized ML models:
  * DistilBERT: Deep learning NLP transformer for chief complaint condition classification.
  * XGBoost: Tabular classifier for Emergency Severity Index (ESI Levels 1-5) rating.
  * LightGBM: Gradient-boosted regressor estimating Length of Stay (LOS in days) and ICU admission probability.

### 2. Online Runtime Phase
* React.js Frontend: Provides a zero-latency interface for clinicians to input chief complaints and patient vital arrays.
* FastAPI Backend: Coordinates request parsing and passes inputs to HealthConsensusEngine.
* Supabase Persistence: Live clinical evaluations are written asynchronously to Supabase (PostgreSQL). Patient identifiers are hashed using SHA-256 prior to database insertion for HIPAA compliance.

---

## Tech Stack

* Backend Framework: Python 3.10+, FastAPI, Uvicorn, Pydantic
* Machine Learning & NLP: PyTorch, Hugging Face Transformers, XGBoost, LightGBM, Joblib, NumPy, Scikit-Learn
* Frontend: React.js, Vite, ES6 JavaScript, HTML5/CSS3
* Database & Security: Supabase (PostgreSQL), Hashlib (SHA-256 Patient Anonymization)
* Data Pipeline: Kaggle API, SQL (Data Cleaning & Feature Engineering)
* Infrastructure: Docker, GitHub Actions (CI/CD)

---

## Local Setup Guide

### Prerequisites
* Python 3.10 or higher
* Node.js v18.0.0 or higher
* Git

### Backend Installation

1. Clone the repository:
   ```bash
   git clone [https://github.com/your-username/medvision.git](https://github.com/your-username/medvision.git)
   cd medvision
