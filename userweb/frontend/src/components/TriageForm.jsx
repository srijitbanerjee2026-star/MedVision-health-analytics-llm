import { useState } from "react";
import { analyzeVitals } from "../services/api.js";

const initialForm = {
  patientId: "",
  age: 0,
  spo2: 98,
  heartRate: 75,
  systolicBp: 120,
  diastolicBp: 80,
  respRate: 16,
  temp: 37.0,
  painScore: 0,
  histAsthma: false,
  histDiabetes: false,
  histHypertension: false,
  histCad: false,
  histStroke: false,
  findings: "",
};

const HISTORY_FIELDS = [
  { key: "histAsthma", label: "Asthma" },
  { key: "histDiabetes", label: "Diabetes" },
  { key: "histHypertension", label: "Hypertension" },
  { key: "histCad", label: "Coronary artery disease" },
  { key: "histStroke", label: "Prior stroke" },
];

const FORM_STEPS = [
  { title: "Core vitals", sub: "The essentials for a fast triage read" },
  { title: "Additional vitals", sub: "Fills in the full risk picture" },
  { title: "History & findings", sub: "Last step before analysis" },
];

export default function TriageForm({ onAnalyzed, onReset }) {
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState(0);

  function updateField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function goNext() {
    if (step === 0 && !form.patientId.trim()) {
      setError("Patient ID is required.");
      return;
    }
    setError("");
    setStep((s) => Math.min(s + 1, FORM_STEPS.length - 1));
  }

  function goBack() {
    setError("");
    setStep((s) => Math.max(s - 1, 0));
  }

  function handleReset() {
    setForm(initialForm);
    setError("");
    setStep(0);
    onReset();
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    if (!form.patientId.trim()) {
      setError("Patient ID is required.");
      return;
    }

    setSubmitting(true);
    try {
      const data = await analyzeVitals({
        patient_id: form.patientId.trim(),
        age: Number(form.age),
        spo2: Number(form.spo2),
        heart_rate: Number(form.heartRate),
        systolic_bp: Number(form.systolicBp),
        diastolic_bp: Number(form.diastolicBp),
        resp_rate: Number(form.respRate),
        temp: Number(form.temp),
        pain_score: Number(form.painScore),
        hist_asthma: form.histAsthma,
        hist_diabetes: form.histDiabetes,
        hist_hypertension: form.histHypertension,
        hist_cad: form.histCad,
        hist_stroke: form.histStroke,
        findings: form.findings.trim(),
      });
      onAnalyzed(data);
    } catch (err) {
      setError(err.message || "Analysis failed due to a network error.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="mvg-form-header">
        <h5>Enter patient vitals</h5>
        <button type="button" className="mvg-btn-secondary" onClick={handleReset}>
          New analysis
        </button>
      </div>

      <form className="mvg-card mvg-form" onSubmit={handleSubmit}>
        <div className="mvg-wizard-head">
          <div className="mvg-wizard-steps">
            {FORM_STEPS.map((s, i) => (
              <div key={s.title} className={`mvg-wizard-step${i === step ? " active" : i < step ? " done" : ""}`}>
                <span className="mvg-wizard-dot">{i < step ? "✓" : i + 1}</span>
                {s.title}
              </div>
            ))}
          </div>
          <div className="mvg-wizard-sub">{FORM_STEPS[step].sub}</div>
        </div>

        {step === 0 && (
          <div className="mvg-form-grid mvg-tab-panel" key="step-0">
            <label>
              Patient ID
              <input
                type="text"
                maxLength={64}
                autoFocus
                value={form.patientId}
                onChange={(e) => updateField("patientId", e.target.value)}
              />
            </label>
            <label>
              Age (years)
              <input
                type="number"
                min={0}
                max={130}
                step={1}
                value={form.age}
                onChange={(e) => updateField("age", e.target.value)}
              />
            </label>
            <label>
              SpO2 (%)
              <input
                type="number"
                min={0}
                max={100}
                step={0.1}
                value={form.spo2}
                onChange={(e) => updateField("spo2", e.target.value)}
              />
            </label>
            <label>
              Heart rate (bpm)
              <input
                type="number"
                min={0}
                max={300}
                step={1}
                value={form.heartRate}
                onChange={(e) => updateField("heartRate", e.target.value)}
              />
            </label>
            <label>
              Systolic BP (mmHg)
              <input
                type="number"
                min={0}
                max={300}
                step={1}
                value={form.systolicBp}
                onChange={(e) => updateField("systolicBp", e.target.value)}
              />
            </label>
          </div>
        )}

        {step === 1 && (
          <div className="mvg-form-grid mvg-tab-panel" key="step-1">
            <label>
              Diastolic BP (mmHg)
              <input
                type="number"
                min={0}
                max={200}
                step={1}
                value={form.diastolicBp}
                onChange={(e) => updateField("diastolicBp", e.target.value)}
              />
            </label>
            <label>
              Respiratory rate (breaths/min)
              <input
                type="number"
                min={0}
                max={80}
                step={1}
                value={form.respRate}
                onChange={(e) => updateField("respRate", e.target.value)}
              />
            </label>
            <label>
              Temperature (&deg;C)
              <input
                type="number"
                min={30}
                max={45}
                step={0.1}
                value={form.temp}
                onChange={(e) => updateField("temp", e.target.value)}
              />
            </label>
            <label>
              Pain score (0-10)
              <input
                type="number"
                min={0}
                max={10}
                step={1}
                value={form.painScore}
                onChange={(e) => updateField("painScore", e.target.value)}
              />
            </label>
          </div>
        )}

        {step === 2 && (
          <div className="mvg-tab-panel" key="step-2">
            <label className="mvg-history-label">
              Medical history
              <div className="mvg-history-grid">
                {HISTORY_FIELDS.map(({ key, label }) => (
                  <label className="mvg-checkbox" key={key}>
                    <input
                      type="checkbox"
                      checked={form[key]}
                      onChange={(e) => updateField(key, e.target.checked)}
                    />
                    {label}
                  </label>
                ))}
              </div>
            </label>
            <label className="mvg-findings-label">
              Clinical findings (optional)
              <textarea
                maxLength={4000}
                rows={3}
                value={form.findings}
                onChange={(e) => updateField("findings", e.target.value)}
              />
            </label>
          </div>
        )}

        {error && <div className="mvg-error">{error}</div>}

        <div className="mvg-wizard-nav">
          <button
            type="button"
            className="mvg-btn-secondary"
            onClick={goBack}
            disabled={step === 0}
            style={{ visibility: step === 0 ? "hidden" : "visible" }}
          >
            Back
          </button>
          {step < FORM_STEPS.length - 1 ? (
            <button type="button" className="mvg-btn-primary" onClick={goNext}>
              Next
            </button>
          ) : (
            <button type="submit" className="mvg-btn-primary" disabled={submitting}>
              {submitting ? "Analyzing..." : "Analyze vitals"}
            </button>
          )}
        </div>
      </form>
    </>
  );
}
