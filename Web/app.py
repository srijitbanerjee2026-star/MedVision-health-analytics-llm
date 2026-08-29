import os, zipfile, shutil, json, textwrap

src = "/mnt/data/medvision-react.zip"
work = "/mnt/data/medvision-react-manual"
if os.path.exists(work):
    shutil.rmtree(work)
os.makedirs(work)

with zipfile.ZipFile(src, "r") as z:
    z.extractall(work)

# Find the actual project root (handle an enclosing folder).
roots = []
for root, dirs, files in os.walk(work):
    if "package.json" in files:
        roots.append(root)
        break
if not roots:
    raise FileNotFoundError("Could not find package.json in the uploaded frontend ZIP.")
root = roots[0]

# Inspect existing source files and replace the app with a manual-entry UI.
srcdir = os.path.join(root, "src")
os.makedirs(srcdir, exist_ok=True)

app_jsx = r'''import { useEffect, useMemo, useState } from "react";
import "./App.css";

const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

const MAX_TEXT_CHARS = 4000;

const emptyPatient = {
  patient_id: "",
  age: "",
  spo2: "",
  heart_rate: "",
  systolic_bp: "",
  findings: "",
};

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function severityStyle(level) {
  const map = {
    1: ["Non-Urgent", "#6b7280"],
    2: ["Low", "#8a92a0"],
    3: ["Moderate", "#b8bec7"],
    4: ["High", "#ff3b30"],
    5: ["Critical", "#ff3b30"],
  };
  return map[level] || ["Unknown", "#888"];
}

function vitalClass(value, low, high) {
  const n = Number(value);
  return n < low || n > high ? "alert" : "ok";
}

function SeverityRing({ level, color }) {
  const safeLevel = typeof level === "number" ? clamp(level, 0, 5) : 0;
  const circumference = 2 * Math.PI * 42;
  const offset = circumference * (1 - safeLevel / 5);

  return (
    <div className="mvg-ring">
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle
          cx="50"
          cy="50"
          r="42"
          fill="none"
          stroke="rgba(255,255,255,0.1)"
          strokeWidth="7"
        />
        <circle
          cx="50"
          cy="50"
          r="42"
          fill="none"
          stroke={color}
          strokeWidth="7"
          strokeLinecap="butt"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 50 50)"
          className={level === 5 ? "critical-ring" : ""}
        />
      </svg>
      <div className="mvg-ring-num" style={{ color }}>
        {level ?? "—"}
      </div>
    </div>
  );
}

export default function App() {
  const [patient, setPatient] = useState(emptyPatient);
  const [result, setResult] = useState(null);
  const [activeTab, setActiveTab] = useState("criticality");
  const [health, setHealth] = useState({ healthy: false, name: "Backend" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => {
    let alive = true;
    fetch(`${BACKEND_URL}/`)
      .then(async (r) => {
        if (!r.ok) throw new Error();
        return r.json().catch(() => ({}));
      })
      .then((data) => {
        if (alive) {
          setHealth({
            healthy: true,
            name: data.system || "Backend",
          });
        }
      })
      .catch(() => {
        if (alive) setHealth({ healthy: false, name: "Backend" });
      });
    return () => {
      alive = false;
    };
  }, []);

  const update = (key, value) => {
    setPatient((p) => ({ ...p, [key]: value }));
  };

  const reset = () => {
    setPatient(emptyPatient);
    setResult(null);
    setError("");
    setShowRaw(false);
    setActiveTab("criticality");
  };

  const canAnalyze =
    patient.age !== "" &&
    patient.spo2 !== "" &&
    patient.heart_rate !== "" &&
    patient.systolic_bp !== "";

  async function analyzePatient(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);

    try {
      // Frontend-only change: send the entered clinical values as JSON.
      // Change only this endpoint/payload if your backend uses a different
      // non-PDF route.
      const payload = {
        patient_id: patient.patient_id || "—",
        age: Number(patient.age),
        spo2: Number(patient.spo2),
        heart_rate: Number(patient.heart_rate),
        systolic_bp: Number(patient.systolic_bp),
        findings: patient.findings.trim(),
      };

      const response = await fetch(`${BACKEND_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}.`);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(
        err?.message ||
          "Could not analyze the patient. Check that the backend is running."
      );
    } finally {
      setLoading(false);
    }
  }

  const analysis = useMemo(() => {
    if (!result || result.status !== "success") return null;

    const vitals = result.parsed_vitals || {
      patient_id: patient.patient_id || "—",
      age: patient.age,
      spo2: patient.spo2,
      heart_rate: patient.heart_rate,
      systolic_bp: patient.systolic_bp,
      findings: patient.findings,
    };

    const severityLevel =
      result.triage_severity_level == null
        ? null
        : Number(result.triage_severity_level);

    const [severityLabel, severityColor] = severityStyle(severityLevel);
    const disease = result.predicted_disease || "Unknown";
    const confidence = Number(result.disease_confidence || 0);
    const findings = vitals.findings || result.findings || "";
    const snippet = result.raw_text_snippet || "";
    const probabilities =
      result.disease_probabilities || { [disease]: confidence };
    const lifeExpectancy = result.life_expectancy_years || {};

    const ranked = Object.entries(probabilities)
      .map(([name, p]) => [name, clamp(Number(p) || 0, 0, 1)])
      .sort((a, b) => b[1] - a[1]);

    return {
      vitals,
      severityLevel,
      severityLabel,
      severityColor,
      disease,
      confidence,
      findings,
      snippet: String(snippet).slice(0, MAX_TEXT_CHARS),
      ranked,
      lifeExpectancy,
    };
  }, [result, patient]);

  return (
    <main className="app-shell">
      <header className="mvg-hero">
        <div>
          <div className="mvg-title">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path
                d="M2 12h4l2 7 4-14 2 7h8"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            MedVision Guard
          </div>
          <div className="mvg-subtitle">
            AI-powered clinical decision support & ER triage
          </div>
        </div>
        <div className="mvg-badge">
          <span className={`mvg-dot ${health.healthy ? "online" : "offline"}`} />
          {health.healthy ? "SYSTEM ONLINE" : "SYSTEM UNREACHABLE"}
        </div>
      </header>

      {!health.healthy && (
        <div className="notice warning">
          Could not reach the backend at <code>{BACKEND_URL}</code>. Make sure
          your backend is running, then refresh this page.
        </div>
      )}

      <form className="input-card" onSubmit={analyzePatient}>
        <div className="section-heading">
          <div>
            <span className="eyebrow">Manual assessment</span>
            <h2>Patient Information</h2>
          </div>
          <button type="button" className="secondary-btn" onClick={reset}>
            New analysis
          </button>
        </div>

        <div className="form-grid two">
          <label>
            <span>Patient ID</span>
            <input
              value={patient.patient_id}
              onChange={(e) => update("patient_id", e.target.value)}
              placeholder="P001"
            />
          </label>
          <label>
            <span>Age</span>
            <input
              type="number"
              min="0"
              max="130"
              value={patient.age}
              onChange={(e) => update("age", e.target.value)}
              placeholder="45"
              required
            />
          </label>
        </div>

        <div className="section-heading compact">
          <div>
            <span className="eyebrow">Clinical measurements</span>
            <h2>Vital Signs</h2>
          </div>
        </div>

        <div className="form-grid three">
          <label>
            <span>SpO₂ (%)</span>
            <input
              type="number"
              min="0"
              max="100"
              step="0.1"
              value={patient.spo2}
              onChange={(e) => update("spo2", e.target.value)}
              placeholder="97"
              required
            />
          </label>
          <label>
            <span>Heart Rate (bpm)</span>
            <input
              type="number"
              min="0"
              max="300"
              step="1"
              value={patient.heart_rate}
              onChange={(e) => update("heart_rate", e.target.value)}
              placeholder="82"
              required
            />
          </label>
          <label>
            <span>Systolic BP (mmHg)</span>
            <input
              type="number"
              min="0"
              max="300"
              step="1"
              value={patient.systolic_bp}
              onChange={(e) => update("systolic_bp", e.target.value)}
              placeholder="120"
              required
            />
          </label>
        </div>

        <label className="findings-field">
          <span>Clinical Findings</span>
          <textarea
            rows="4"
            maxLength={MAX_TEXT_CHARS}
            value={patient.findings}
            onChange={(e) => update("findings", e.target.value)}
            placeholder="Enter relevant symptoms, observations, or clinical findings..."
          />
        </label>

        <div className="form-footer">
          <span className="helper">
            Enter the required values to run the clinical analysis.
          </span>
          <button
            className="primary-btn"
            type="submit"
            disabled={!canAnalyze || loading}
          >
            {loading ? "ANALYZING..." : "ANALYZE PATIENT"}
          </button>
        </div>
      </form>

      {error && <div className="notice error">{error}</div>}

      {!result && !loading && (
        <div className="empty-state">
          <div className="empty-icon">+</div>
          <h3>Ready for assessment</h3>
          <p>
            Enter the patient values above and run an analysis to see triage
            criticality and diagnosis results.
          </p>
        </div>
      )}

      {loading && (
        <div className="loading-card">
          <div className="loader" />
          <div>
            <strong>Analyzing patient data</strong>
            <p>Processing the entered clinical values…</p>
          </div>
        </div>
      )}

      {analysis && (
        <section className="results">
          <div className="tabs">
            <button
              className={activeTab === "criticality" ? "active" : ""}
              onClick={() => setActiveTab("criticality")}
              type="button"
            >
              Criticality
            </button>
            <button
              className={activeTab === "diagnosis" ? "active" : ""}
              onClick={() => setActiveTab("diagnosis")}
              type="button"
            >
              Diagnosis
            </button>
          </div>

          {activeTab === "criticality" ? (
            <div className="results-grid">
              <div className="mvg-card">
                <h4>Patient Vitals — {analysis.vitals.patient_id || "—"}</h4>
                <Metric label="Age" value={analysis.vitals.age || "—"} />
                <Metric
                  label="SpO₂"
                  value={`${analysis.vitals.spo2 ?? "—"}%`}
                  cls={vitalClass(analysis.vitals.spo2, 92, 100)}
                />
                <Metric
                  label="Heart Rate"
                  value={`${analysis.vitals.heart_rate ?? "—"} bpm`}
                  cls={vitalClass(analysis.vitals.heart_rate, 60, 100)}
                />
                <Metric
                  label="Systolic BP"
                  value={`${analysis.vitals.systolic_bp ?? "—"} mmHg`}
                  cls={vitalClass(analysis.vitals.systolic_bp, 90, 130)}
                />
              </div>

              <div className="mvg-card">
                <h4>Triage Severity</h4>
                <div className="severity-wrap">
                  <SeverityRing
                    level={analysis.severityLevel}
                    color={analysis.severityColor}
                  />
                  <span
                    className="severity-label"
                    style={{
                      color: analysis.severityColor,
                      borderColor: `${analysis.severityColor}55`,
                      background: `${analysis.severityColor}18`,
                    }}
                  >
                    {analysis.severityLabel}
                  </span>
                </div>
              </div>

              <div className="mvg-card full">
                <h4>Clinical Findings</h4>
                <div className="findings">
                  {analysis.findings || "No findings text returned."}
                </div>
              </div>

              {analysis.snippet && (
                <div className="mvg-card full">
                  <button
                    className="raw-toggle"
                    type="button"
                    onClick={() => setShowRaw((v) => !v)}
                  >
                    Raw extracted text snippet
                    <span>{showRaw ? "−" : "+"}</span>
                  </button>
                  {showRaw && <pre className="snippet">{analysis.snippet}</pre>}
                </div>
              )}
            </div>
          ) : (
            <div className="mvg-card">
              <h4>Disease Probability Breakdown</h4>
              <div className="diagnosis-summary">
                <div>
                  <span className="eyebrow">Predicted disease</span>
                  <strong>{analysis.disease}</strong>
                </div>
                <div className="confidence">
                  {(analysis.confidence * 100).toFixed(1)}%
                  <small>confidence</small>
                </div>
              </div>

              {analysis.ranked.length ? (
                <div className="probabilities">
                  {analysis.ranked.map(([name, prob], i) => {
                    const top = i === 0;
                    const life = analysis.lifeExpectancy[name];
                    return (
                      <div className="prob-row" key={name}>
                        <div className="prob-head">
                          <span className={top ? "top" : ""}>
                            {name}
                            {top && <em>Top match</em>}
                          </span>
                          <span>{(prob * 100).toFixed(1)}%</span>
                        </div>
                        <div className="prob-track">
                          <div
                            className={`prob-fill ${top ? "top" : ""}`}
                            style={{ width: `${prob * 100}%` }}
                          />
                        </div>
                        <div className="prob-sub">
                          {life != null
                            ? `Est. life expectancy: ${Number(life).toFixed(1)} yrs`
                            : "Est. life expectancy: not available"}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="muted">No probability data returned.</p>
              )}
            </div>
          )}
        </section>
      )}
    </main>
  );
}

function Metric({ label, value, cls = "ok" }) {
  return (
    <div className="metric-row">
      <span>{label}</span>
      <strong className={cls}>{value}</strong>
    </div>
  );
}
'''

app_css = r'''@import url("https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&display=swap");

:root {
  font-family: "Outfit", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #f5f6f7;
  background: #0b0f17;
  font-synthesis: none;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  min-width: 320px;
  background: #0b0f17;
}

button, input, textarea { font: inherit; }

button { cursor: pointer; }

.app-shell {
  width: min(1100px, calc(100% - 40px));
  margin: 0 auto;
  padding: 28px 0 48px;
}

.mvg-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 18px;
  margin-bottom: 22px;
  border-bottom: 1px solid rgba(255,255,255,.09);
}

.mvg-title {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 1.6rem;
  font-weight: 700;
  letter-spacing: -.02em;
}

.mvg-subtitle {
  margin-top: 3px;
  color: #8a92a0;
  font-size: .85rem;
  text-transform: uppercase;
  letter-spacing: .06em;
}

.mvg-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  border: 1px solid rgba(255,255,255,.09);
  border-radius: 4px;
  background: #10141c;
  font: 600 .76rem "SFMono-Regular", Consolas, monospace;
  white-space: nowrap;
}

.mvg-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.mvg-dot.online { background: #3fb950; box-shadow: 0 0 8px #3fb95066; }
.mvg-dot.offline { background: #ff3b30; }

.input-card, .mvg-card, .empty-state, .loading-card {
  border: 1px solid rgba(255,255,255,.09);
  border-radius: 5px;
  background: #10141c;
}

.input-card { padding: 22px; }

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.section-heading.compact { margin-top: 28px; margin-bottom: 14px; }

.eyebrow {
  display: block;
  color: #8a92a0;
  font-size: .68rem;
  font-weight: 700;
  letter-spacing: .1em;
  text-transform: uppercase;
}
h2 { margin: 3px 0 0; font-size: 1.02rem; }

.form-grid { display: grid; gap: 14px; }
.form-grid.two { grid-template-columns: 1fr 1fr; }
.form-grid.three { grid-template-columns: repeat(3, 1fr); }

label { display: block; }
label > span {
  display: block;
  margin-bottom: 7px;
  color: #8a92a0;
  font-size: .76rem;
  font-weight: 600;
}

input, textarea {
  width: 100%;
  color: #f5f6f7;
  background: #090c12;
  border: 1px solid rgba(255,255,255,.11);
  border-radius: 4px;
  outline: none;
  padding: 11px 12px;
  transition: border-color .15s ease, box-shadow .15s ease;
}
input:focus, textarea:focus {
  border-color: rgba(255,255,255,.38);
  box-shadow: 0 0 0 3px rgba(255,255,255,.035);
}
textarea { resize: vertical; min-height: 100px; }

.findings-field { margin-top: 14px; }

.form-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-top: 18px;
}
.helper { color: #727b89; font-size: .78rem; }

.primary-btn, .secondary-btn {
  border-radius: 4px;
  padding: 10px 15px;
  font-weight: 700;
  transition: .15s ease;
}
.primary-btn {
  color: #0b0f17;
  background: #f5f6f7;
  border: 1px solid #f5f6f7;
}
.primary-btn:hover:not(:disabled) { transform: translateY(-1px); }
.primary-btn:disabled { opacity: .35; cursor: not-allowed; }
.secondary-btn {
  color: #cfd3d9;
  background: transparent;
  border: 1px solid rgba(255,255,255,.14);
}
.secondary-btn:hover { border-color: rgba(255,255,255,.35); }

.notice {
  padding: 11px 13px;
  margin: 0 0 16px;
  border: 1px solid rgba(255,255,255,.1);
  border-radius: 4px;
  font-size: .82rem;
}
.notice.warning { color: #b8bec7; background: #151920; }
.notice.error { color: #ff8f89; border-color: #ff3b3038; background: #ff3b3012; }
code { font-family: Consolas, monospace; }

.empty-state {
  margin-top: 18px;
  padding: 48px 24px;
  text-align: center;
  color: #8a92a0;
}
.empty-icon {
  width: 34px; height: 34px; margin: 0 auto 12px;
  display: grid; place-items: center;
  border: 1px solid rgba(255,255,255,.15);
  border-radius: 50%;
  color: #f5f6f7;
}
.empty-state h3 { margin: 0 0 6px; color: #f5f6f7; }
.empty-state p { max-width: 560px; margin: auto; font-size: .84rem; }

.loading-card {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 18px;
  padding: 20px;
}
.loading-card strong { font-size: .9rem; }
.loading-card p { margin: 4px 0 0; color: #8a92a0; font-size: .78rem; }
.loader {
  width: 24px; height: 24px;
  border: 2px solid rgba(255,255,255,.12);
  border-top-color: #f5f6f7;
  border-radius: 50%;
  animation: spin .75s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.results { margin-top: 22px; }
.tabs {
  display: flex;
  gap: 22px;
  border-bottom: 1px solid rgba(255,255,255,.09);
}
.tabs button {
  color: #8a92a0;
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  padding: 10px 2px;
  font-size: .82rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .04em;
}
.tabs button.active { color: #f5f6f7; border-bottom-color: #f5f6f7; }

.results-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-top: 16px;
}

.mvg-card { padding: 17px; }
.mvg-card.full { grid-column: 1 / -1; }
.mvg-card h4 {
  margin: 0 0 13px;
  color: #8a92a0;
  font-size: .68rem;
  letter-spacing: .09em;
  text-transform: uppercase;
}

.metric-row {
  display: flex;
  justify-content: space-between;
  gap: 15px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255,255,255,.07);
  font: .86rem "SFMono-Regular", Consolas, monospace;
}
.metric-row:last-child { border-bottom: 0; }
.metric-row > span { color: #8a92a0; font-family: inherit; }
.metric-row strong.alert { color: #ff3b30; }
.metric-row strong.ok { color: #f5f6f7; }

.severity-wrap {
  min-height: 120px;
  display: flex;
  align-items: center;
  gap: 22px;
}
.mvg-ring { position: relative; width: 105px; height: 105px; flex: 0 0 auto; }
.mvg-ring svg { width: 100%; height: 100%; }
.mvg-ring-num {
  position: absolute; inset: 0;
  display: grid; place-items: center;
  font-size: 1.75rem; font-weight: 800;
}
.mvg-ring svg circle:last-child {
  transition: stroke-dashoffset .6s ease-out;
}
.critical-ring { animation: pulse 1.4s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: .5; } }

.severity-label {
  padding: 5px 9px;
  border: 1px solid;
  border-radius: 3px;
  font-size: .75rem;
  font-weight: 700;
  text-transform: uppercase;
}

.findings {
  color: #cfd3d9;
  font-size: .87rem;
  line-height: 1.55;
  white-space: pre-wrap;
}

.raw-toggle {
  width: 100%;
  display: flex;
  justify-content: space-between;
  padding: 0;
  color: #8a92a0;
  background: none;
  border: 0;
  font-size: .68rem;
  font-weight: 700;
  letter-spacing: .09em;
  text-transform: uppercase;
}
.raw-toggle span { font-size: 1rem; }
.snippet {
  margin: 12px 0 0;
  padding: 12px;
  color: #9aa1ac;
  background: #090c12;
  border: 1px solid rgba(255,255,255,.08);
  border-radius: 3px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: .75rem/1.5 Consolas, monospace;
}

.diagnosis-summary {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 20px;
  padding: 8px 0 20px;
  border-bottom: 1px solid rgba(255,255,255,.07);
}
.diagnosis-summary strong {
  display: block;
  margin-top: 5px;
  font-size: 1.35rem;
}
.confidence {
  font-size: 1.45rem;
  font-weight: 800;
  text-align: right;
}
.confidence small {
  display: block;
  color: #8a92a0;
  font-size: .66rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: .05em;
}
.probabilities { margin-top: 18px; }
.prob-row {
  padding: 0 0 14px;
  margin-bottom: 14px;
  border-bottom: 1px solid rgba(255,255,255,.07);
}
.prob-row:last-child { border-bottom: 0; margin-bottom: 0; }
.prob-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 7px;
  font-size: .86rem;
}
.prob-head > span:last-child { color: #8a92a0; font: .8rem Consolas, monospace; }
.prob-head .top { font-weight: 700; }
.prob-head em {
  margin-left: 7px;
  padding: 2px 5px;
  border: 1px solid rgba(255,255,255,.25);
  border-radius: 3px;
  color: #f5f6f7;
  font-size: .58rem;
  font-style: normal;
  text-transform: uppercase;
}
.prob-track {
  height: 5px;
  overflow: hidden;
  background: rgba(255,255,255,.08);
  border-radius: 2px;
}
.prob-fill {
  height: 100%;
  background: #8a92a0;
  transition: width .5s ease;
}
.prob-fill.top { background: #f5f6f7; }
.prob-sub {
  margin-top: 5px;
  color: #727b89;
  font: .68rem Consolas, monospace;
}
.muted { color: #727b89; }

@media (max-width: 720px) {
  .app-shell { width: min(100% - 24px, 1100px); padding-top: 18px; }
  .mvg-hero, .form-footer { align-items: flex-start; flex-direction: column; }
  .mvg-badge { align-self: flex-start; }
  .form-grid.two, .form-grid.three, .results-grid { grid-template-columns: 1fr; }
  .mvg-card.full { grid-column: auto; }
  .form-footer .primary-btn { width: 100%; }
}
'''

# Update package.json to ensure React/Vite dependencies are present.
pkg_path = os.path.join(root, "package.json")
with open(pkg_path, "r", encoding="utf-8") as f:
    pkg = json.load(f)
pkg.setdefault("scripts", {})
pkg["scripts"]["dev"] = "vite"
pkg["scripts"]["build"] = "vite build"
pkg["scripts"]["preview"] = "vite preview"
pkg.setdefault("dependencies", {})
pkg["dependencies"].setdefault("react", "^18.3.1")
pkg["dependencies"].setdefault("react-dom", "^18.3.1")
pkg.setdefault("devDependencies", {})
pkg["devDependencies"].setdefault("vite", "^5.4.10")
with open(pkg_path, "w", encoding="utf-8") as f:
    json.dump(pkg, f, indent=2)
    f.write("\n")

with open(os.path.join(srcdir, "App.jsx"), "w", encoding="utf-8") as f:
    f.write(app_jsx)
with open(os.path.join(srcdir, "App.css"), "w", encoding="utf-8") as f:
    f.write(app_css)

# Remove common old Streamlit-ish/frontend files if present, while keeping package entry.
for name in ["main.py", "app.py"]:
    p = os.path.join(root, name)
    if os.path.exists(p):
        os.remove(p)

# Add a clear frontend-only README.
readme = """# MedVision Guard — Manual React Frontend

This frontend replaces the Streamlit PDF drag-and-drop UI with a React + Vite manual-entry interface.

## Run

```powershell
npm install
npm run dev
