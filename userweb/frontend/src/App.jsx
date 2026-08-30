import { useEffect, useState } from "react";
import { BACKEND_URL, checkHealth } from "./services/api.js";
import TriageForm from "./components/TriageForm.jsx";

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
  const critical = level === 5;
  return (
    <div className="mvg-ring" style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={RING_RADIUS} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="7" />
        <circle
          key={level}
          cx="50"
          cy="50"
          r={RING_RADIUS}
          fill="none"
          stroke={color}
          strokeWidth="7"
          strokeLinecap="butt"
          strokeDasharray={RING_CIRCUMFERENCE.toFixed(2)}
          transform="rotate(-90 50 50)"
          className={critical ? "mvg-ring-anim-critical" : "mvg-ring-anim"}
          style={{
            "--mvg-ring-circumference": `${RING_CIRCUMFERENCE.toFixed(2)}`,
            "--mvg-ring-offset": `${offset.toFixed(2)}`,
          }}
        />
      </svg>
      <div className="mvg-ring-num" style={{ color }}>
        {level ?? "—"}
      </div>
    </div>
  );
}

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
      return value < 92
        ? { alert: true, text: "Low — should be 92% or higher" }
        : { alert: false, text: "Normal — 92% or higher is healthy" };
    case "heart_rate":
      if (value < 60) return { alert: true, text: "Slow — usual range is 60 to 100" };
      if (value > 100) return { alert: true, text: "Fast — usual range is 60 to 100" };
      return { alert: false, text: "Normal — usual range is 60 to 100" };
    case "systolic_bp":
      if (value < 90) return { alert: true, text: "Low — should be 90 or higher" };
      if (value > 130) return { alert: true, text: "High — should be 130 or under" };
      return { alert: false, text: "Normal — 90 to 130 is healthy" };
    default:
      return { alert: false, text: "" };
  }
}

export default function App() {
  const [healthy, setHealthy] = useState(false);
  const [result, setResult] = useState(null);
  const [tab, setTab] = useState("criticality");
  const [analyzedAt, setAnalyzedAt] = useState(null);

  useEffect(() => {
    let cancelled = false;
    checkHealth()
      .then(() => !cancelled && setHealthy(true))
      .catch(() => !cancelled && setHealthy(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const vitals = result?.parsed_vitals;
  const severityLevel = result?.triage_severity_level ?? null;
  const [severityLabel, severityColor] = SEVERITY_MAP[severityLevel] || ["Unknown", "#888"];
  const risk = result?.risk_assessment;
  const riskColor = risk && risk.risk_score >= 70 ? "#ff3b30" : risk && risk.risk_score >= 40 ? "#b8bec7" : "#8a92a0";
  const nlpDiagnosis = result?.nlp_diagnosis;

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
          <span
            className={`mvg-dot${healthy ? " mvg-dot-online" : ""}`}
            style={{ background: healthy ? "#3fb950" : "#ff3b30" }}
          />
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

      <div className="mvg-tab-panel" style={{ display: tab === "criticality" ? undefined : "none" }}>
        <TriageForm
          onAnalyzed={(data) => {
            setResult(data);
            setAnalyzedAt(new Date());
          }}
          onReset={() => {
            setResult(null);
            setAnalyzedAt(null);
          }}
        />
      </div>

      {tab === "criticality" && (
        <div className="mvg-tab-panel">
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

                <div className="mvg-card mvg-diagnosis-hero">
                  <div className="mvg-card-label">Predicted Diagnosis</div>
                  {nlpDiagnosis ? (
                    <>
                      <div className="mvg-hero-disease" style={{ color: severityColor }}>
                        {nlpDiagnosis.predicted_condition}
                      </div>
                      <div className="mvg-hero-confidence">
                        {(nlpDiagnosis.confidence * 100).toFixed(1)}% model confidence · {nlpDiagnosis.subsystem}
                      </div>
                    </>
                  ) : (
                    <div className="mvg-hero-disease" style={{ color: severityColor }}>—</div>
                  )}
                  <p className="mvg-plain-text">
                    {nlpDiagnosis
                      ? "This diagnosis is based on the clinical findings you entered, analyzed by the NLP model."
                      : "Enter clinical findings on the History & findings step to get a predicted diagnosis."}
                  </p>
                  <p className="mvg-plain-text">
                    This reading comes only from what you entered — a clinician needs to confirm with an exam
                    and further tests.
                  </p>
                </div>

                {risk && (
                  <div className="mvg-card mvg-risk-card">
                    <div className="mvg-report-match-head">
                      <div className="mvg-card-label">AI Risk Assessment</div>
                      <div className="mvg-muted-text">From the trained risk model, not a clinician.</div>
                    </div>
                    <div className="mvg-risk-row">
                      <div className="mvg-risk-score" style={{ color: riskColor }}>
                        {risk.risk_score.toFixed(1)}
                        <span className="mvg-risk-score-unit">%</span>
                      </div>
                      <div className="mvg-risk-track">
                        <div
                          className="mvg-risk-fill"
                          style={{
                            "--mvg-bar-target": `${risk.risk_score}%`,
                            width: `${risk.risk_score}%`,
                            background: riskColor,
                          }}
                        />
                      </div>
                    </div>
                    <div className="mvg-risk-meta">
                      <div className="mvg-risk-meta-item">
                        <div className="mvg-vital-name">Disposition</div>
                        <div className="mvg-vital-value">{risk.disposition}</div>
                      </div>
                      <div className="mvg-risk-meta-item">
                        <div className="mvg-vital-name">Monitoring</div>
                        <div className="mvg-vital-value">{risk.monitoring}</div>
                      </div>
                      <div className="mvg-risk-meta-item">
                        <div className="mvg-vital-name">Estimated stay</div>
                        <div className="mvg-vital-value">{risk.estimated_stay}</div>
                      </div>
                    </div>
                    <ul className="mvg-risk-recommendation">
                      {risk.recommendation.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}

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

                  <div className="mvg-card mvg-stay-card">
                    <div className="mvg-card-label">Recommended Hospital Stay</div>
                    {risk ? (
                      <>
                        <div className="mvg-stay-duration">{risk.estimated_stay}</div>
                        <div className="mvg-vital-row mvg-vital-row-inline">
                          <div className="mvg-vital-name">Disposition</div>
                          <div className="mvg-vital-value-inline">{risk.disposition}</div>
                        </div>
                        <div className="mvg-vital-row mvg-vital-row-inline">
                          <div className="mvg-vital-name">Monitoring frequency</div>
                          <div className="mvg-vital-value-inline">{risk.monitoring}</div>
                        </div>
                        <p className="mvg-lock-note">
                          From the trained risk model, based on age and vitals — a clinician makes the final call.
                        </p>
                      </>
                    ) : (
                      <p className="mvg-muted-text">Risk model unavailable — no stay estimate to show.</p>
                    )}
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
