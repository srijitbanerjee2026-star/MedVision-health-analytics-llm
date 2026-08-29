import { useEffect, useState } from "react";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

const SEVERITY_MAP = {
  1: ["Non-Urgent", "#6b7280"],
  2: ["Low", "#8a92a0"],
  3: ["Moderate", "#b8bec7"],
  4: ["High", "#ff3b30"],
  5: ["Critical", "#ff3b30"],
};

const RING_RADIUS = 42;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

function vitalClass(value, low, high) {
  return value < low || value > high ? "alert" : "ok";
}

function SeverityRing({ level, color, size = 110 }) {
  const clamped = Math.max(0, Math.min(5, level || 0));
  const offset = RING_CIRCUMFERENCE * (1 - clamped / 5);
  return (
    <div className="mvg-ring" style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={RING_RADIUS} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="7" />
        <circle
          cx="50"
          cy="50"
          r={RING_RADIUS}
          fill="none"
          stroke={color}
          strokeWidth="7"
          strokeLinecap="butt"
          strokeDasharray={RING_CIRCUMFERENCE.toFixed(2)}
          strokeDashoffset={offset.toFixed(2)}
          transform="rotate(-90 50 50)"
        />
      </svg>
      <div className="mvg-ring-num" style={{ color }}>
        {level ?? "—"}
      </div>
    </div>
  );
}

const DISEASE_INFO = {
  Normal: "No signs of infection or organ strain in these vitals.",
  "Respiratory Infection": "An infection in the lungs. Usually treated with oxygen and antibiotics, often in hospital.",
  "Cardiac Event": "A possible strain on the heart. May need urgent monitoring and cardiac tests.",
  Sepsis: "A body-wide reaction to infection that can escalate quickly and needs urgent treatment.",
  "Hypertensive Crisis": "Blood pressure high enough to risk organ damage if not treated quickly.",
};

const SCAN_HEADLINE = {
  Normal: "Your vitals are within the range we'd expect for someone without acute illness.",
  "Respiratory Infection": "Your oxygen level and breathing-related vitals point to a possible lung infection.",
  "Cardiac Event": "Your heart rate and blood pressure pattern suggest possible strain on your heart.",
  Sepsis: "Your vitals show a pattern sometimes seen with a body-wide infection response.",
  "Hypertensive Crisis": "Your blood pressure is high enough to need prompt evaluation.",
};

const BANNER_BY_SEVERITY = {
  5: {
    title: "Your results need urgent attention",
    body: "Several of your vitals are well outside the normal range. Stay where you are and wait for the care team.",
  },
  4: {
    title: "Your results need prompt attention",
    body: "Some of your vitals are outside the normal range and should be checked by the care team soon.",
  },
  3: {
    title: "Your results show some concerns",
    body: "A few vitals are slightly outside the normal range. The care team will review them.",
  },
  2: {
    title: "Your results are mostly reassuring",
    body: "Your vitals are close to normal, with one or two small exceptions.",
  },
  1: {
    title: "Your results look normal",
    body: "All of your vitals are within the expected healthy range.",
  },
};

function vitalNarrative(kind, value) {
  switch (kind) {
    case "spo2":
      return value < 95
        ? { alert: true, text: "Low — should be 95% or higher" }
        : { alert: false, text: "Normal — 95% or higher is healthy" };
    case "heart_rate":
      if (value < 60) return { alert: true, text: "Slow — usual range is 60 to 100" };
      if (value > 100) return { alert: true, text: "Fast — usual range is 60 to 100" };
      return { alert: false, text: "Normal — usual range is 60 to 100" };
    case "systolic_bp":
      return value >= 130
        ? { alert: true, text: "High — should be under 120" }
        : { alert: false, text: "Normal — under 120 is healthy" };
    default:
      return { alert: false, text: "" };
  }
}

const initialForm = {
  patientId: "",
  age: 0,
  spo2: 98,
  heartRate: 75,
  systolicBp: 120,
  findings: "",
};

export default function App() {
  const [healthy, setHealthy] = useState(false);
  const [form, setForm] = useState(initialForm);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [tab, setTab] = useState("criticality");
  const [analyzedAt, setAnalyzedAt] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${BACKEND_URL}/`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(() => !cancelled && setHealthy(true))
      .catch(() => !cancelled && setHealthy(false));
    return () => {
      cancelled = true;
    };
  }, []);

  function updateField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
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
      const response = await fetch(`${BACKEND_URL}/analyze-vitals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_id: form.patientId.trim(),
          age: Number(form.age),
          spo2: Number(form.spo2),
          heart_rate: Number(form.heartRate),
          systolic_bp: Number(form.systolicBp),
          findings: form.findings.trim(),
        }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || `Backend returned status ${response.status}`);
      }
      const data = await response.json();
      setResult(data);
      setAnalyzedAt(new Date());
      setTab("criticality");
    } catch (err) {
      setError(err.message || "Analysis failed due to a network error.");
    } finally {
      setSubmitting(false);
    }
  }

  function handleReset() {
    setForm(initialForm);
    setResult(null);
    setError("");
    setAnalyzedAt(null);
  }

  const vitals = result?.parsed_vitals;
  const severityLevel = result?.triage_severity_level ?? null;
  const [severityLabel, severityColor] = SEVERITY_MAP[severityLevel] || ["Unknown", "#888"];
  const diseaseProbabilities = result?.disease_probabilities || {};
  const rankedDiseases = Object.entries(diseaseProbabilities).sort((a, b) => b[1] - a[1]);
  const topDisease = rankedDiseases[0]?.[0];

  return (
    <div className="mvg-app">
      <div className="mvg-hero">
        <div>
          <p className="mvg-title">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 12h4l2 7 4-14 2 7h8" />
            </svg>
            MedVision Guard
          </p>
          <p className="mvg-subtitle">AI-powered clinical decision support &amp; ER triage</p>
        </div>
        <div className="mvg-badge">
          <span className="mvg-dot" style={{ background: healthy ? "#3fb950" : "#ff3b30" }} />
          {healthy ? "SYSTEM ONLINE" : "SYSTEM UNREACHABLE"}
        </div>
      </div>

      {!healthy && (
        <div className="mvg-warning">
          Could not reach the backend at <code>{BACKEND_URL}</code>. Set the <code>VITE_BACKEND_URL</code> environment
          variable if it runs elsewhere, then refresh this page.
        </div>
      )}

      <div className="mvg-tabs">
        <button className={tab === "criticality" ? "active" : ""} onClick={() => setTab("criticality")}>
          Triage board
        </button>
        <button className={tab === "diagnosis" ? "active" : ""} onClick={() => setTab("diagnosis")}>
          Diagnosis &amp; outlook
        </button>
      </div>

      {tab === "criticality" && (
        <div className="mvg-tab-panel">
          <div className="mvg-form-header">
            <h5>Enter patient vitals</h5>
            <button type="button" className="mvg-btn-secondary" onClick={handleReset}>
              New analysis
            </button>
          </div>

          <form className="mvg-card mvg-form" onSubmit={handleSubmit}>
            <div className="mvg-form-grid">
              <label>
                Patient ID
                <input
                  type="text"
                  maxLength={64}
                  value={form.patientId}
                  onChange={(e) => updateField("patientId", e.target.value)}
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
            </div>
            <label className="mvg-findings-label">
              Clinical findings (optional)
              <textarea
                maxLength={4000}
                rows={3}
                value={form.findings}
                onChange={(e) => updateField("findings", e.target.value)}
              />
            </label>
            {error && <div className="mvg-error">{error}</div>}
            <button type="submit" className="mvg-btn-primary" disabled={submitting}>
              {submitting ? "Analyzing..." : "Analyze vitals"}
            </button>
          </form>

          {!result && (
            <div className="mvg-card mvg-placeholder">
              Enter a patient's vitals above and click "Analyze vitals" to run triage analysis.
            </div>
          )}

          {result && (
            <>
              <div className="mvg-card mvg-severity-card">
                <div className="mvg-card-label">Triage Severity — {vitals.patient_id}</div>
                <div className="mvg-ring-wrap-horizontal">
                  <SeverityRing level={severityLevel} color={severityColor} />
                  <div className="mvg-severity-info">
                    <div className="mvg-severity-text" style={{ color: severityColor }}>
                      {severityLabel}
                    </div>
                    <div className="mvg-severity-sub">Acuity level {severityLevel ?? "—"} of 5</div>
                  </div>
                </div>
              </div>

              <div className="mvg-card">
                <div className="mvg-card-label">Patient Vitals</div>
                <div className="mvg-metric-row">
                  <span className="mvg-metric-label">Age</span>
                  <span className="mvg-metric-value">{vitals.age}</span>
                </div>
                <div className="mvg-metric-row">
                  <span className="mvg-metric-label">SpO2</span>
                  <span className={`mvg-metric-value ${vitalClass(vitals.spo2, 92, 100)}`}>{vitals.spo2}%</span>
                </div>
                <div className="mvg-metric-row">
                  <span className="mvg-metric-label">Heart Rate</span>
                  <span className={`mvg-metric-value ${vitalClass(vitals.heart_rate, 60, 100)}`}>
                    {vitals.heart_rate} bpm
                  </span>
                </div>
                <div className="mvg-metric-row">
                  <span className="mvg-metric-label">Systolic BP</span>
                  <span className={`mvg-metric-value ${vitalClass(vitals.systolic_bp, 90, 130)}`}>
                    {vitals.systolic_bp} mmHg
                  </span>
                </div>
              </div>

              <div className="mvg-card">
                <div className="mvg-card-label">Clinical Findings</div>
                <div className="mvg-findings">{vitals.findings || "No findings entered."}</div>
              </div>
            </>
          )}
        </div>
      )}

      {tab === "diagnosis" && !result && (
        <div className="mvg-tab-panel">
          <div className="mvg-card mvg-placeholder">
            Submit a patient's vitals on the Triage board tab first to see the diagnosis and outlook.
          </div>
        </div>
      )}

      {tab === "diagnosis" && result && (() => {
            const banner = BANNER_BY_SEVERITY[severityLevel] || BANNER_BY_SEVERITY[3];
            const notified = severityLevel >= 4;
            const spo2Info = vitalNarrative("spo2", vitals.spo2);
            const hrInfo = vitalNarrative("heart_rate", vitals.heart_rate);
            const sbpInfo = vitalNarrative("systolic_bp", vitals.systolic_bp);
            const scanHeadline = SCAN_HEADLINE[topDisease] || "We could not determine a clear pattern from these vitals.";

            return (
              <div className="mvg-tab-panel">
                <div className="mvg-outlook-header">
                  <div className="mvg-outlook-patient">
                    {vitals.patient_id} · Age {vitals.age}
                  </div>
                  <div className="mvg-badge">
                    <span className="mvg-dot" style={{ background: notified ? "#3fb950" : "#8a92a0" }} />
                    {notified ? "CARE TEAM NOTIFIED" : "REVIEWED — NO ESCALATION NEEDED"}
                  </div>
                </div>

                <div className="mvg-banner" style={{ background: `${severityColor}1F`, borderColor: `${severityColor}55` }}>
                  <div className="mvg-banner-body">
                    <div className="mvg-banner-title">{banner.title}</div>
                    <div className="mvg-banner-text">{banner.body}</div>
                    <div className="mvg-banner-meta">
                      {notified
                        ? `Care team paged ${analyzedAt ? analyzedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}  ·  Stay where you are  ·  Do not drive yourself`
                        : "No action needed right now  ·  Contact your care team if symptoms change"}
                    </div>
                  </div>
                </div>

                <div className="mvg-outlook-row">
                  <div className="mvg-card mvg-urgency-card">
                    <div className="mvg-card-label">How urgent this is</div>
                    <div className="mvg-ring-wrap-horizontal">
                      <SeverityRing level={severityLevel} color={severityColor} size={118} />
                      <div className="mvg-severity-info">
                        <div className="mvg-severity-text-lg" style={{ color: severityColor }}>
                          {severityLabel}
                        </div>
                        <div className="mvg-severity-sub">Level {severityLevel ?? "—"} of 5</div>
                      </div>
                    </div>
                    <p className="mvg-plain-text">{banner.body}</p>
                  </div>

                  <div className="mvg-card mvg-scan-card">
                    <div className="mvg-card-label">What the scan shows</div>
                    <div className="mvg-scan-headline">{scanHeadline}</div>
                    <p className="mvg-plain-text">
                      This reading comes only from the vitals you entered — a clinician needs to confirm with an
                      exam and further tests.
                    </p>
                    <div className="mvg-scan-source">
                      <div className="mvg-card-label">The same thing, in your report</div>
                      <div className="mvg-snippet">
                        {vitals.findings || "No clinical findings were entered for this patient."}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mvg-card">
                  <div className="mvg-report-match-head">
                    <div className="mvg-card-label">What your report most looks like</div>
                    <div className="mvg-muted-text">A doctor confirms the diagnosis, not the computer.</div>
                  </div>
                  {rankedDiseases.length === 0 ? (
                    <p className="mvg-muted-text">No probability data returned.</p>
                  ) : (
                    rankedDiseases.map(([name, prob]) => {
                      const isTop = name === topDisease;
                      const pct = Math.min(Math.max(prob, 0), 1) * 100;
                      return (
                        <div className="mvg-prob-row" key={name}>
                          <div className="mvg-prob-head">
                            <span className={`mvg-prob-name${isTop ? " top" : ""}`}>
                              {name}
                              {isTop && <span className="mvg-prob-badge">Top match</span>}
                            </span>
                            <span className="mvg-prob-pct">{pct.toFixed(1)}%</span>
                          </div>
                          <div className="mvg-prob-track">
                            <div
                              className={`mvg-prob-fill${isTop ? " top" : ""}`}
                              style={{ width: `${pct.toFixed(1)}%` }}
                            />
                          </div>
                          <div className="mvg-prob-desc">{DISEASE_INFO[name] || ""}</div>
                        </div>
                      );
                    })
                  )}
                </div>

                <div className="mvg-outlook-row">
                  <div className="mvg-card">
                    <div className="mvg-card-label">Your numbers</div>
                    <div className="mvg-vital-row">
                      <div className="mvg-vital-name">Oxygen in your blood</div>
                      <div className={`mvg-vital-value ${spo2Info.alert ? "alert" : ""}`}>{vitals.spo2}%</div>
                      <div className={`mvg-vital-desc ${spo2Info.alert ? "alert" : ""}`}>{spo2Info.text}</div>
                    </div>
                    <div className="mvg-vital-row">
                      <div className="mvg-vital-name">Heart rate</div>
                      <div className={`mvg-vital-value ${hrInfo.alert ? "alert" : ""}`}>{vitals.heart_rate} bpm</div>
                      <div className={`mvg-vital-desc ${hrInfo.alert ? "alert" : ""}`}>{hrInfo.text}</div>
                    </div>
                    <div className="mvg-vital-row">
                      <div className="mvg-vital-name">Blood pressure, upper number</div>
                      <div className={`mvg-vital-value ${sbpInfo.alert ? "alert" : ""}`}>{vitals.systolic_bp} mmHg</div>
                      <div className={`mvg-vital-desc ${sbpInfo.alert ? "alert" : ""}`}>{sbpInfo.text}</div>
                    </div>
                    <div className="mvg-vital-row mvg-vital-row-inline">
                      <div className="mvg-vital-name">Age</div>
                      <div className="mvg-vital-value-inline">{vitals.age}</div>
                    </div>
                  </div>

                  <div className="mvg-card mvg-locked-card">
                    <div className="mvg-card-label">Long-term outlook</div>
                    <div className="mvg-locked-row">
                      <div className="mvg-vital-name">5-year outlook</div>
                      <div className="mvg-muted-text">Locked</div>
                    </div>
                    <div className="mvg-locked-row">
                      <div className="mvg-vital-name">Expected recovery time</div>
                      <div className="mvg-muted-text">Locked</div>
                    </div>
                    <p className="mvg-lock-note">
                      Long-term outlook needs a clinician's review and isn't generated automatically from vitals
                      alone.
                    </p>
                    <button type="button" className="mvg-btn-secondary mvg-lock-btn" disabled>
                      Request outlook from care team
                    </button>
                  </div>
                </div>

                <div className="mvg-outlook-footer">
                  <div className="mvg-muted-text">
                    Manual vitals entry · Reviewed{" "}
                    {analyzedAt
                      ? `${analyzedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}, ${analyzedAt.toLocaleDateString()}`
                      : "—"}
                  </div>
                  <div className="mvg-muted-text mvg-footer-disclaimer">
                    This page is a computer reading of your vitals. It is not a diagnosis and it is not a treatment
                    plan. Your care team decides both.
                  </div>
                </div>
              </div>
            );
          })()}
    </div>
  );
}
