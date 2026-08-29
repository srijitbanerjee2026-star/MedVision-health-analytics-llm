import hashlib
import math
import os
import time

import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", "20"))

st.set_page_config(
    page_title="MedVision Guard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Vercel-style minimal theming
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    :root {
        --mvg-accent: #30a46c;
        --mvg-accent-bright: #7fe0ac;
        --mvg-accent-soft: rgba(48, 164, 108, 0.14);
    }

    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(circle at 12% 18%, rgba(48,164,108,0.22) 0%, rgba(48,164,108,0) 42%),
            radial-gradient(circle at 88% 12%, rgba(94,129,244,0.16) 0%, rgba(94,129,244,0) 42%),
            radial-gradient(circle at 75% 88%, rgba(232,114,12,0.12) 0%, rgba(232,114,12,0) 45%),
            #0e1117;
        background-size: 200% 200%;
        animation: mvgAuroraShift 20s ease-in-out infinite alternate;
    }
    @keyframes mvgAuroraShift {
        0% { background-position: 0% 0%, 100% 0%, 50% 100%, 0 0; }
        100% { background-position: 12% 14%, 88% 22%, 58% 88%, 0 0; }
    }

    .stButton button {
        transition: transform 0.12s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }
    .stButton button:hover {
        box-shadow: 0 0 18px rgba(48, 164, 108, 0.35);
        border-color: var(--mvg-accent) !important;
    }
    .stButton button:active {
        transform: scale(0.98);
    }
    [data-testid="stFileUploaderDropzone"] {
        transition: box-shadow 0.2s ease, border-color 0.2s ease;
    }
    [data-testid="stFileUploaderDropzone"]:hover {
        box-shadow: 0 0 24px rgba(48, 164, 108, 0.2);
        border-color: var(--mvg-accent) !important;
    }
    [data-testid="stFileUploaderDropzone"] button {
        transition: transform 0.12s ease;
    }
    [data-testid="stFileUploaderDropzone"] button:active {
        transform: scale(0.98);
    }

    .block-container {
        padding-top: 2.5rem;
        padding-bottom: 3rem;
        max-width: 1100px;
    }

    #MainMenu, footer, header { visibility: hidden; }

    .mvg-hero {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 2rem;
    }
    .mvg-title {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 1.9rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin: 0;
    }
    .mvg-title svg { flex-shrink: 0; }
    .mvg-subtitle {
        color: #888;
        font-size: 0.95rem;
        margin-top: 0.2rem;
    }
    .mvg-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.3rem 0.75rem;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid rgba(128,128,128,0.25);
    }
    .mvg-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--mvg-accent);
        animation: mvgBreathe 2.2s ease-in-out infinite;
    }

    @keyframes mvgBreathe {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.35; }
    }
    @keyframes mvgFadeUp {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes mvgFadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    @keyframes mvgRingFill {
        from { stroke-dashoffset: var(--ring-circumference); }
        to { stroke-dashoffset: var(--ring-offset); }
    }
    @keyframes mvgBarFill {
        from { width: 0%; }
        to { width: var(--bar-target); }
    }

    .mvg-card {
        border: 1px solid rgba(128,128,128,0.18);
        border-radius: 14px;
        padding: 1.25rem 1.4rem;
        background: rgba(128,128,128,0.04);
        height: 100%;
        animation: mvgFadeUp 0.35s cubic-bezier(0.16,1,0.3,1) both;
        transition: transform 0.18s cubic-bezier(0.16,1,0.3,1), border-color 0.18s ease;
    }
    .mvg-card:hover {
        transform: translateY(-2px);
        border-color: rgba(48, 164, 108, 0.4);
    }

    [data-testid="stTabs"] [role="tablist"] {
        gap: 0.25rem;
        background: transparent;
        border-bottom: none;
    }
    [data-testid="stTabs"] [role="tablist"]::before {
        display: none;
    }
    [data-testid="stTab"] {
        height: auto;
        padding: 0.45rem 1.1rem;
        border-radius: 999px;
        font-weight: 600;
        font-size: 0.88rem;
        color: #999;
        background: transparent;
        border-bottom: none !important;
        transition: background 0.2s ease, color 0.2s ease;
    }
    [data-testid="stTab"] p {
        font-size: 0.88rem;
        font-weight: 600;
    }
    [data-testid="stTab"][aria-selected="true"] {
        background: var(--mvg-accent-soft);
        color: var(--mvg-accent);
    }
    [data-testid="stTabPanel"] {
        animation: mvgFadeIn 0.25s ease;
    }

    .mvg-ring-wrap {
        display: flex;
        align-items: center;
        gap: 1.5rem;
    }
    .mvg-ring {
        position: relative;
        width: 96px;
        height: 96px;
        flex-shrink: 0;
    }
    .mvg-ring svg { width: 100%; height: 100%; }
    .mvg-ring-num {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.8rem;
        font-weight: 800;
        letter-spacing: -0.03em;
    }
    .mvg-card h4 {
        margin: 0 0 0.75rem 0;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #999;
        font-weight: 700;
    }

    .mvg-metric-row {
        display: flex;
        justify-content: space-between;
        padding: 0.4rem 0;
        border-bottom: 1px solid rgba(128,128,128,0.12);
        font-size: 0.92rem;
    }
    .mvg-metric-row:last-child { border-bottom: none; }
    .mvg-metric-label { color: #999; }
    .mvg-metric-value { font-weight: 600; }
    .mvg-metric-value.alert { color: #e5484d; }
    .mvg-metric-value.warn { color: #f5a623; }
    .mvg-metric-value.ok { color: #30a46c; }

    .mvg-severity {
        display: flex;
        align-items: baseline;
        gap: 0.6rem;
    }
    .mvg-severity-num {
        font-size: 2.6rem;
        font-weight: 800;
        letter-spacing: -0.04em;
    }
    .mvg-severity-label {
        font-size: 1rem;
        font-weight: 600;
        padding: 0.2rem 0.7rem;
        border-radius: 999px;
    }

    .mvg-disease {
        font-size: 1.5rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        margin-bottom: 0.3rem;
    }

    .mvg-findings {
        font-size: 0.92rem;
        line-height: 1.55;
        color: #ccc;
    }

    .mvg-snippet {
        font-family: 'SFMono-Regular', Consolas, Menlo, monospace;
        font-size: 0.8rem;
        background: rgba(128,128,128,0.08);
        border: 1px solid rgba(128,128,128,0.15);
        border-radius: 10px;
        padding: 0.9rem 1rem;
        color: #aaa;
        white-space: pre-wrap;
        word-break: break-word;
    }

    div[data-testid="stFileUploaderDropzone"] {
        border-radius: 14px;
    }

    .mvg-prob-row {
        margin-bottom: 0.85rem;
    }
    .mvg-prob-row:last-child { margin-bottom: 0; }
    .mvg-prob-head {
        display: flex;
        justify-content: space-between;
        font-size: 0.9rem;
        margin-bottom: 0.35rem;
    }
    .mvg-prob-name { font-weight: 600; }
    .mvg-prob-name.top { color: var(--mvg-accent); }
    .mvg-prob-badge {
        display: inline-block;
        margin-left: 0.5rem;
        padding: 0.05rem 0.5rem;
        border-radius: 999px;
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: var(--mvg-accent);
        background: var(--mvg-accent-soft);
        vertical-align: middle;
    }
    .mvg-prob-pct { color: #999; font-variant-numeric: tabular-nums; }
    .mvg-prob-sub {
        font-size: 0.78rem;
        color: #777;
        margin-top: 0.35rem;
    }
    .mvg-prob-track {
        width: 100%;
        height: 8px;
        border-radius: 999px;
        background: rgba(128,128,128,0.15);
        overflow: hidden;
    }
    .mvg-prob-fill {
        height: 100%;
        border-radius: 999px;
        background: rgba(128,128,128,0.4);
        width: 0%;
        animation: mvgBarFill 0.9s cubic-bezier(0.16,1,0.3,1) both;
    }
    .mvg-prob-fill.top {
        background: var(--mvg-accent);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

SEVERITY_MAP = {
    1: ("Non-Urgent", "#30a46c"),
    2: ("Low", "#5b9bd5"),
    3: ("Moderate", "#f5a623"),
    4: ("High", "#e8720c"),
    5: ("Critical", "#e5484d"),
}


RING_RADIUS = 42
RING_CIRCUMFERENCE = 2 * math.pi * RING_RADIUS


def severity_style(level: int):
    return SEVERITY_MAP.get(level, ("Unknown", "#888"))


def severity_ring_html(level, color):
    clamped = max(0, min(5, level or 0))
    ring_offset = RING_CIRCUMFERENCE * (1 - clamped / 5)
    level_display = level if level is not None else "—"
    return (
        f'<div class="mvg-ring"><svg viewBox="0 0 100 100">'
        f'<circle cx="50" cy="50" r="{RING_RADIUS}" fill="none" stroke="rgba(128,128,128,0.15)" stroke-width="8"></circle>'
        f'<circle cx="50" cy="50" r="{RING_RADIUS}" fill="none" stroke="{color}" stroke-width="8" '
        f'stroke-linecap="round" stroke-dasharray="{RING_CIRCUMFERENCE:.2f}" '
        f'style="--ring-circumference:{RING_CIRCUMFERENCE:.2f}; --ring-offset:{ring_offset:.2f}; '
        f'animation: mvgRingFill 1s cubic-bezier(0.16,1,0.3,1) both;" '
        f'transform="rotate(-90 50 50)"></circle></svg>'
        f'<div class="mvg-ring-num" style="color:{color};">{level_display}</div></div>'
    )


def vital_class(value, low, high):
    if value < low or value > high:
        return "alert"
    return "ok"


@st.cache_data(ttl=20, show_spinner=False)
def check_backend_health():
    try:
        r = requests.get(f"{BACKEND_URL}/", timeout=3)
        if r.ok:
            return True, r.json().get("system", "Backend")
    except requests.RequestException:
        pass
    return False, None


@st.cache_data(ttl=600, show_spinner=False, max_entries=20)
def analyze_pdf(file_hash: str, filename: str, file_bytes: bytes):
    """Cached on file content hash so re-running the app (e.g. expanding a
    section) doesn't re-upload and re-analyze the same report."""
    files = {"file": (filename, file_bytes, "application/pdf")}
    response = requests.post(f"{BACKEND_URL}/analyze-pdf", files=files, timeout=60)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
healthy, system_name = check_backend_health()
badge_color = "#30a46c" if healthy else "#e5484d"
badge_text = "Backend online" if healthy else "Backend unreachable"

st.markdown(
    f"""
    <div class="mvg-hero">
        <div>
            <p class="mvg-title">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M2 12h4l2 7 4-14 2 7h8" />
                </svg>
                MedVision Guard
            </p>
            <p class="mvg-subtitle">AI-powered clinical decision support &amp; ER triage</p>
        </div>
        <div class="mvg-badge">
            <span class="mvg-dot" style="background:{badge_color};"></span>
            {badge_text}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not healthy:
    st.warning(
        f"Could not reach the backend at `{BACKEND_URL}`. "
        f"Set the `BACKEND_URL` environment variable if it runs elsewhere, "
        f"then refresh this page."
    )

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

upload_col, reset_col = st.columns([5, 1])
with upload_col:
    uploaded_file = st.file_uploader(
        "Upload a diagnostic report (PDF)",
        type=["pdf"],
        help="The report is sent to the analysis backend for triage scoring.",
        key=f"uploader_{st.session_state.uploader_key}",
    )
with reset_col:
    st.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
    if st.button("New analysis", use_container_width=True):
        st.session_state.uploader_key += 1
        st.rerun()

result = None
if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    size_mb = len(file_bytes) / (1024 * 1024)

    if size_mb > MAX_FILE_MB:
        st.error(f"'{uploaded_file.name}' is {size_mb:.1f} MB, which exceeds the {MAX_FILE_MB} MB limit.")
    else:
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        start = time.perf_counter()
        try:
            with st.spinner(f"Analyzing {uploaded_file.name}..."):
                result = analyze_pdf(file_hash, uploaded_file.name, file_bytes)
            elapsed = time.perf_counter() - start
            # Only show timing/toast for a fresh call, not a cache hit from a rerun.
            if elapsed > 0.05:
                st.toast(f"Analysis complete in {elapsed:.1f}s", icon="✓")
        except requests.exceptions.Timeout:
            st.error("Analysis timed out. The backend may be overloaded — try again shortly.")
        except requests.exceptions.ConnectionError:
            st.error(f"Could not connect to the backend at `{BACKEND_URL}`.")
        except requests.exceptions.HTTPError as exc:
            st.error(f"Backend returned an error: {exc.response.status_code} {exc.response.reason}")
        except requests.RequestException as exc:
            st.error(f"Analysis failed: {exc}")

    if result and result.get("status") == "success":
        vitals = result.get("parsed_vitals", {})
        severity_level = result.get("triage_severity_level")
        severity_label, severity_color = severity_style(severity_level)
        disease = result.get("predicted_disease", "Unknown")
        confidence = result.get("disease_confidence", 0)
        findings = vitals.get("findings", "")
        snippet = result.get("raw_text_snippet", "")
        disease_probabilities = result.get("disease_probabilities") or {disease: confidence}
        life_expectancy_years = result.get("life_expectancy_years") or {}

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        tab_criticality, tab_diagnosis = st.tabs(["Criticality", "Diagnosis"])

        with tab_criticality:
            col1, col2 = st.columns([1, 1], gap="medium")

            with col1:
                spo2 = vitals.get("spo2", 0)
                hr = vitals.get("heart_rate", 0)
                sbp = vitals.get("systolic_bp", 0)
                age = vitals.get("age", "—")
                patient_id = vitals.get("patient_id", "—")

                spo2_cls = vital_class(spo2, 92, 100)
                hr_cls = vital_class(hr, 60, 100)
                sbp_cls = vital_class(sbp, 90, 130)

                st.markdown(
                    f"""
                    <div class="mvg-card">
                        <h4>Patient Vitals — {patient_id}</h4>
                        <div class="mvg-metric-row">
                            <span class="mvg-metric-label">Age</span>
                            <span class="mvg-metric-value">{age}</span>
                        </div>
                        <div class="mvg-metric-row">
                            <span class="mvg-metric-label">SpO2</span>
                            <span class="mvg-metric-value {spo2_cls}">{spo2}%</span>
                        </div>
                        <div class="mvg-metric-row">
                            <span class="mvg-metric-label">Heart Rate</span>
                            <span class="mvg-metric-value {hr_cls}">{hr} bpm</span>
                        </div>
                        <div class="mvg-metric-row">
                            <span class="mvg-metric-label">Systolic BP</span>
                            <span class="mvg-metric-value {sbp_cls}">{sbp} mmHg</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with col2:
                st.markdown(
                    f"""
                    <div class="mvg-card">
                        <h4>Triage Severity</h4>
                        <div class="mvg-ring-wrap">
                            {severity_ring_html(severity_level, severity_color)}
                            <span class="mvg-severity-label" style="background:{severity_color}22; color:{severity_color};">
                                {severity_label}
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
            st.markdown(
                f"""
                <div class="mvg-card">
                    <h4>Clinical Findings</h4>
                    <div class="mvg-findings">{findings or "No findings text returned."}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
            with st.expander("Raw extracted text snippet"):
                st.markdown(f'<div class="mvg-snippet">{snippet}</div>', unsafe_allow_html=True)

        with tab_diagnosis:
            ranked = sorted(disease_probabilities.items(), key=lambda kv: kv[1], reverse=True)
            top_name = ranked[0][0] if ranked else None

            rows = []
            for i, (name, prob) in enumerate(ranked):
                prob = min(max(float(prob), 0.0), 1.0)
                is_top = name == top_name
                top_cls = " top" if is_top else ""
                delay_ms = i * 90

                life_years = life_expectancy_years.get(name)
                if life_years is not None:
                    life_text = f"Est. life expectancy: {float(life_years):.1f} yrs"
                else:
                    life_text = "Est. life expectancy: not available"

                badge_html = '<span class="mvg-prob-badge">Top match</span>' if is_top else ""
                rows.append(
                    f'<div class="mvg-prob-row">'
                    f'<div class="mvg-prob-head">'
                    f'<span class="mvg-prob-name{top_cls}">{name}{badge_html}</span>'
                    f'<span class="mvg-prob-pct">{prob * 100:.1f}%</span>'
                    f'</div>'
                    f'<div class="mvg-prob-track">'
                    f'<div class="mvg-prob-fill{top_cls}" style="--bar-target:{prob * 100:.1f}%; animation-delay:{delay_ms}ms;"></div>'
                    f'</div>'
                    f'<div class="mvg-prob-sub">{life_text}</div>'
                    f'</div>'
                )

            st.markdown(
                f"""
                <div class="mvg-card">
                    <h4>Disease Probability Breakdown</h4>
                    {"".join(rows) if rows else "<p style='color:#888;'>No probability data returned.</p>"}
                </div>
                """,
                unsafe_allow_html=True,
            )

    elif result:
        st.error(f"Backend returned an unexpected response: {result}")
else:
    st.markdown(
        """
        <div class="mvg-card" style="text-align:center; padding:3rem 1.5rem; color:#888;">
            Upload a PDF diagnostic report to run triage analysis.
        </div>
        """,
        unsafe_allow_html=True,
    )
