import hashlib
import hmac
import html
import math
import os
import re
import sys
import time
import traceback
from urllib.parse import urlparse

import requests
import streamlit as st

MAX_TEXT_CHARS = 4000
_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!<>])")


def esc(value, max_chars=None):
    """HTML-escape any backend/PDF-derived value before it's interpolated into
    unsafe_allow_html markup. Backend responses (and PDF-extracted text within
    them) are untrusted input — without this, a crafted PDF could inject
    script/HTML that runs in the viewer's browser."""
    text = str(value)
    if max_chars and len(text) > max_chars:
        text = text[:max_chars] + "… (truncated)"
    return html.escape(text)


def safe_markdown(value, max_chars=200):
    """Escape Markdown metacharacters in user-controlled text (e.g. an
    uploaded filename) before it's dropped into a plain st.markdown/st.error
    call. Without this, a filename like '[click](javascript:...)' renders as
    a real clickable link even though unsafe_allow_html is off."""
    text = str(value)
    if len(text) > max_chars:
        text = text[:max_chars] + "… (truncated)"
    return _MD_SPECIAL.sub(r"\\\1", text)


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def log_server_error(context, exc):
    """Log full details server-side only — never expose raw exception text
    or backend payloads to the browser (info-disclosure / fingerprinting)."""
    print(f"[MedVision Guard] {context}: {exc!r}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)


BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", "20"))
APP_PASSWORD = os.environ.get("APP_PASSWORD")
ALLOW_INSECURE_BACKEND = os.environ.get("ALLOW_INSECURE_BACKEND", "").lower() in ("1", "true", "yes")
RATE_LIMIT_MAX = int(os.environ.get("RATE_LIMIT_MAX", "10"))
RATE_LIMIT_WINDOW_S = int(os.environ.get("RATE_LIMIT_WINDOW_S", "300"))

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
        --mvg-ink: #f5f6f7;
        --mvg-muted: #8a92a0;
        --mvg-line: rgba(255,255,255,0.09);
        --mvg-surface: #10141c;
        --mvg-alert: #ff3b30;
        --mvg-alert-soft: rgba(255, 59, 48, 0.12);
    }

    [data-testid="stAppViewContainer"] {
        background: #0b0f17;
    }

    .stButton button {
        transition: border-color 0.15s ease;
    }
    .stButton button:hover {
        border-color: rgba(255,255,255,0.4) !important;
    }
    .stButton button:active {
        transform: scale(0.99);
    }
    [data-testid="stFileUploaderDropzone"] {
        transition: border-color 0.15s ease;
    }
    [data-testid="stFileUploaderDropzone"]:hover {
        border-color: rgba(255,255,255,0.35) !important;
    }
    [data-testid="stFileUploaderDropzone"] button:active {
        transform: scale(0.99);
    }

    .block-container {
        padding-top: 1.75rem;
        padding-bottom: 2rem;
        max-width: 1100px;
    }

    #MainMenu, footer, header { visibility: hidden; }

    .mvg-hero {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid var(--mvg-line);
    }
    .mvg-title {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 1.6rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        margin: 0;
        color: var(--mvg-ink);
    }
    .mvg-title svg { flex-shrink: 0; color: var(--mvg-ink); }
    .mvg-subtitle {
        color: var(--mvg-muted);
        font-size: 0.85rem;
        margin-top: 0.15rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-weight: 500;
    }
    .mvg-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.3rem 0.75rem;
        border-radius: 3px;
        font-size: 0.78rem;
        font-weight: 600;
        font-family: 'JetBrains Mono', 'SFMono-Regular', Consolas, monospace;
        border: 1px solid var(--mvg-line);
        background: var(--mvg-surface);
    }
    .mvg-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        animation: mvgBreathe 2.2s ease-in-out infinite;
    }

    @keyframes mvgBreathe {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
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
    @keyframes mvgCriticalPulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.55; }
    }

    .mvg-card {
        border: 1px solid var(--mvg-line);
        border-radius: 4px;
        padding: 1rem 1.1rem;
        background: var(--mvg-surface);
        height: 100%;
        animation: mvgFadeIn 0.2s ease both;
        transition: border-color 0.15s ease;
    }
    .mvg-card:hover {
        border-color: rgba(255,255,255,0.22);
    }

    [data-testid="stTabs"] [role="tablist"] {
        gap: 1.25rem;
        background: transparent;
        border-bottom: 1px solid var(--mvg-line);
    }
    [data-testid="stTabs"] [role="tablist"]::before {
        display: none;
    }
    [data-testid="stTab"] {
        height: auto;
        padding: 0.4rem 0.1rem;
        border-radius: 0;
        font-weight: 600;
        font-size: 0.85rem;
        color: var(--mvg-muted);
        background: transparent;
        border-bottom: 2px solid transparent !important;
        transition: color 0.15s ease, border-color 0.15s ease;
    }
    [data-testid="stTab"] p {
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    [data-testid="stTab"][aria-selected="true"] {
        background: transparent;
        color: var(--mvg-ink);
        border-bottom: 2px solid var(--mvg-ink) !important;
    }
    [data-testid="stTabPanel"] {
        animation: mvgFadeIn 0.2s ease;
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
        margin: 0 0 0.6rem 0;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--mvg-muted);
        font-weight: 700;
    }

    .mvg-metric-row {
        display: flex;
        justify-content: space-between;
        padding: 0.32rem 0;
        border-bottom: 1px solid var(--mvg-line);
        font-size: 0.88rem;
        font-family: 'SFMono-Regular', Consolas, Menlo, monospace;
    }
    .mvg-metric-row:last-child { border-bottom: none; }
    .mvg-metric-label { color: var(--mvg-muted); font-family: 'Outfit', sans-serif; }
    .mvg-metric-value { font-weight: 600; color: var(--mvg-ink); }
    .mvg-metric-value.alert { color: var(--mvg-alert); }
    .mvg-metric-value.ok { color: var(--mvg-ink); }

    .mvg-severity {
        display: flex;
        align-items: baseline;
        gap: 0.6rem;
    }
    .mvg-severity-num {
        font-size: 2.4rem;
        font-weight: 800;
        letter-spacing: -0.04em;
    }
    .mvg-severity-label {
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        padding: 0.2rem 0.6rem;
        border-radius: 3px;
    }

    .mvg-disease {
        font-size: 1.4rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        margin-bottom: 0.3rem;
    }

    .mvg-findings {
        font-size: 0.88rem;
        line-height: 1.5;
        color: #cfd3d9;
    }

    .mvg-snippet {
        font-family: 'SFMono-Regular', Consolas, Menlo, monospace;
        font-size: 0.78rem;
        background: #090c12;
        border: 1px solid var(--mvg-line);
        border-radius: 3px;
        padding: 0.75rem 0.9rem;
        color: #9aa1ac;
        white-space: pre-wrap;
        word-break: break-word;
    }

    div[data-testid="stFileUploaderDropzone"] {
        border-radius: 4px;
    }

    .mvg-prob-row {
        margin-bottom: 0.7rem;
        padding-bottom: 0.7rem;
        border-bottom: 1px solid var(--mvg-line);
    }
    .mvg-prob-row:last-child { margin-bottom: 0; border-bottom: none; padding-bottom: 0; }
    .mvg-prob-head {
        display: flex;
        justify-content: space-between;
        font-size: 0.88rem;
        margin-bottom: 0.35rem;
    }
    .mvg-prob-name { font-weight: 600; color: var(--mvg-ink); }
    .mvg-prob-name.top { font-weight: 700; }
    .mvg-prob-badge {
        display: inline-block;
        margin-left: 0.5rem;
        padding: 0.03rem 0.4rem;
        border-radius: 3px;
        font-size: 0.62rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--mvg-ink);
        border: 1px solid rgba(255,255,255,0.3);
        vertical-align: middle;
    }
    .mvg-prob-pct {
        color: var(--mvg-muted);
        font-variant-numeric: tabular-nums;
        font-family: 'SFMono-Regular', Consolas, Menlo, monospace;
    }
    .mvg-prob-sub {
        font-size: 0.74rem;
        color: var(--mvg-muted);
        margin-top: 0.3rem;
        font-family: 'SFMono-Regular', Consolas, Menlo, monospace;
    }
    .mvg-prob-track {
        width: 100%;
        height: 5px;
        border-radius: 2px;
        background: rgba(255,255,255,0.08);
        overflow: hidden;
    }
    .mvg-prob-fill {
        height: 100%;
        background: var(--mvg-muted);
        width: 0%;
        animation: mvgBarFill 0.5s ease-out both;
    }
    .mvg-prob-fill.top {
        background: var(--mvg-ink);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Clickjacking protection — Streamlit doesn't set X-Frame-Options / CSP
# frame-ancestors itself, so bust out if we're ever loaded inside a frame.
# ---------------------------------------------------------------------------
st.markdown(
    "<script>if (window.top !== window.self) { window.top.location = window.self.location; }</script>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Access control — optional password gate (set APP_PASSWORD to enable).
# ---------------------------------------------------------------------------
if APP_PASSWORD:
    if not st.session_state.get("authenticated"):
        st.markdown("### MedVision Guard — Access Required")
        entered = st.text_input("Access code", type="password")
        if st.button("Unlock"):
            if hmac.compare_digest(entered, APP_PASSWORD):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect access code.")
        st.stop()

# ---------------------------------------------------------------------------
# Transport security — refuse to send clinical data to a non-local backend
# over plaintext HTTP.
# ---------------------------------------------------------------------------
_backend_parsed = urlparse(BACKEND_URL)
if (
    _backend_parsed.scheme == "http"
    and _backend_parsed.hostname not in ("localhost", "127.0.0.1", "::1")
    and not ALLOW_INSECURE_BACKEND
):
    st.error(
        f"BACKEND_URL (`{BACKEND_URL}`) points to a non-local host over plaintext HTTP. "
        f"Refusing to transmit clinical data unencrypted. Use an `https://` BACKEND_URL, "
        f"or set ALLOW_INSECURE_BACKEND=1 to override (not recommended)."
    )
    st.stop()

SEVERITY_MAP = {
    1: ("Non-Urgent", "#6b7280"),
    2: ("Low", "#8a92a0"),
    3: ("Moderate", "#b8bec7"),
    4: ("High", "#ff3b30"),
    5: ("Critical", "#ff3b30"),
}


RING_RADIUS = 42
RING_CIRCUMFERENCE = 2 * math.pi * RING_RADIUS


def severity_style(level):
    return SEVERITY_MAP.get(level, ("Unknown", "#888"))


def severity_ring_html(level, color):
    clamped = max(0, min(5, level or 0)) if isinstance(level, (int, float)) else 0
    ring_offset = RING_CIRCUMFERENCE * (1 - clamped / 5)
    level_display = level if level is not None else "—"
    anim = "mvgRingFill 0.6s ease-out both"
    if level == 5:
        anim += ", mvgCriticalPulse 1.4s ease-in-out infinite"
    return (
        f'<div class="mvg-ring"><svg viewBox="0 0 100 100">'
        f'<circle cx="50" cy="50" r="{RING_RADIUS}" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="7"></circle>'
        f'<circle cx="50" cy="50" r="{RING_RADIUS}" fill="none" stroke="{color}" stroke-width="7" '
        f'stroke-linecap="butt" stroke-dasharray="{RING_CIRCUMFERENCE:.2f}" '
        f'style="--ring-circumference:{RING_CIRCUMFERENCE:.2f}; --ring-offset:{ring_offset:.2f}; '
        f'animation: {anim};" '
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


def analyze_pdf(filename: str, file_bytes: bytes):
    files = {"file": (filename, file_bytes, "application/pdf")}
    response = requests.post(f"{BACKEND_URL}/analyze-pdf", files=files, timeout=60)
    response.raise_for_status()
    return response.json()


# Session-scoped result cache (NOT st.cache_data): st.cache_data is shared
# across every user of this server process, which would mean one patient's
# vitals/findings sit in process-wide memory and are reachable by any other
# session for up to the TTL. Keying this off st.session_state instead means
# results never cross session boundaries.
ANALYSIS_CACHE_TTL_S = 300


def get_cached_analysis(file_hash):
    cache = st.session_state.get("analysis_cache", {})
    entry = cache.get(file_hash)
    if entry and (time.time() - entry[1] < ANALYSIS_CACHE_TTL_S):
        return entry[0]
    return None


def set_cached_analysis(file_hash, result):
    cache = st.session_state.setdefault("analysis_cache", {})
    cache[file_hash] = (result, time.time())


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
healthy, system_name = check_backend_health()
badge_color = "#3fb950" if healthy else "#ff3b30"
badge_text = "SYSTEM ONLINE" if healthy else "SYSTEM UNREACHABLE"

st.markdown(
    f"""
    <div class="mvg-hero">
        <div>
            <p class="mvg-title">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
        # Data minimization: don't keep prior patient data in memory once
        # the user has moved on.
        st.session_state.analysis_cache = {}
        st.rerun()

result = None
if uploaded_file is not None:
    safe_name = safe_markdown(uploaded_file.name)
    file_bytes = uploaded_file.getvalue()
    size_mb = len(file_bytes) / (1024 * 1024)

    if size_mb > MAX_FILE_MB:
        st.error(f"'{safe_name}' is {size_mb:.1f} MB, which exceeds the {MAX_FILE_MB} MB limit.")
    elif not file_bytes.startswith(b"%PDF-"):
        st.error(f"'{safe_name}' does not look like a valid PDF (missing %PDF header) — rejected.")
    else:
        now = time.time()
        recent = [t for t in st.session_state.get("upload_timestamps", []) if now - t < RATE_LIMIT_WINDOW_S]
        if len(recent) >= RATE_LIMIT_MAX:
            st.error(
                f"Rate limit reached: max {RATE_LIMIT_MAX} analyses per "
                f"{RATE_LIMIT_WINDOW_S // 60} min for this session. Try again shortly."
            )
        else:
            file_hash = hashlib.sha256(file_bytes).hexdigest()
            start = time.perf_counter()
            try:
                cached = get_cached_analysis(file_hash)
                if cached is not None:
                    result = cached
                else:
                    with st.spinner(f"Analyzing {safe_name}..."):
                        result = analyze_pdf(uploaded_file.name, file_bytes)
                    set_cached_analysis(file_hash, result)
                    recent.append(now)
                    st.session_state.upload_timestamps = recent
                    elapsed = time.perf_counter() - start
                    st.toast(f"Analysis complete in {elapsed:.1f}s")
            except requests.exceptions.Timeout:
                st.error("Analysis timed out. The backend may be overloaded — try again shortly.")
            except requests.exceptions.ConnectionError:
                st.error(f"Could not connect to the backend at `{BACKEND_URL}`.")
            except requests.exceptions.HTTPError as exc:
                log_server_error("backend HTTP error", exc)
                status = exc.response.status_code if exc.response is not None else "unknown"
                st.error(f"Backend returned an error (status {status}). See server logs for details.")
            except requests.RequestException as exc:
                log_server_error("backend request failed", exc)
                st.error("Analysis failed due to a network error. See server logs for details.")
            except Exception as exc:  # noqa: BLE001 — last resort: never leak a raw traceback to the browser
                log_server_error("unexpected error during analysis", exc)
                st.error("An unexpected error occurred. See server logs for details.")
                result = None

    if result and result.get("status") == "success":
      try:
        vitals = result.get("parsed_vitals") or {}
        severity_level = safe_int(result.get("triage_severity_level"))
        severity_label, severity_color = severity_style(severity_level)
        disease = result.get("predicted_disease") or "Unknown"
        confidence = safe_float(result.get("disease_confidence"))
        findings = vitals.get("findings") or ""
        snippet = result.get("raw_text_snippet") or ""
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
                patient_id = esc(vitals.get("patient_id", "—"))

                spo2_cls = vital_class(safe_float(spo2), 92, 100)
                hr_cls = vital_class(safe_float(hr), 60, 100)
                sbp_cls = vital_class(safe_float(sbp), 90, 130)
                spo2, hr, sbp, age = esc(spo2), esc(hr), esc(sbp), esc(age)

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
                            <span class="mvg-severity-label" style="background:{severity_color}18; color:{severity_color}; border:1px solid {severity_color}55;">
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
                    <div class="mvg-findings">{esc(findings, MAX_TEXT_CHARS) if findings else "No findings text returned."}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
            with st.expander("Raw extracted text snippet"):
                st.markdown(f'<div class="mvg-snippet">{esc(snippet, MAX_TEXT_CHARS)}</div>', unsafe_allow_html=True)

        with tab_diagnosis:
            normalized_probs = {
                name: min(max(safe_float(p), 0.0), 1.0) for name, p in disease_probabilities.items()
            }
            ranked = sorted(normalized_probs.items(), key=lambda kv: kv[1], reverse=True)
            top_name = ranked[0][0] if ranked else None

            rows = []
            for i, (name, prob) in enumerate(ranked):
                prob = min(max(safe_float(prob), 0.0), 1.0)
                is_top = name == top_name
                top_cls = " top" if is_top else ""
                delay_ms = i * 90

                life_years = life_expectancy_years.get(name)
                if life_years is not None and safe_float(life_years, None) is not None:
                    life_text = f"Est. life expectancy: {safe_float(life_years):.1f} yrs"
                else:
                    life_text = "Est. life expectancy: not available"

                safe_name = esc(name, 200)
                badge_html = '<span class="mvg-prob-badge">Top match</span>' if is_top else ""
                rows.append(
                    f'<div class="mvg-prob-row">'
                    f'<div class="mvg-prob-head">'
                    f'<span class="mvg-prob-name{top_cls}">{safe_name}{badge_html}</span>'
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
      except Exception as exc:
          log_server_error("failed to render analysis result", exc)
          st.error("Could not render the analysis result — the backend response may be malformed. See server logs for details.")

    elif result:
        log_server_error("unexpected backend response shape", result)
        st.error("The backend returned a response in an unexpected format. See server logs for details.")
else:
    st.markdown(
        """
        <div class="mvg-card" style="text-align:center; padding:3rem 1.5rem; color:#888;">
            Upload a PDF diagnostic report to run triage analysis.
        </div>
        """,
        unsafe_allow_html=True,
    )
