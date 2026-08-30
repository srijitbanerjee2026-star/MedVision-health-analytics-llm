import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./index.css";

// If the browser restores this page from its back/forward cache, it resumes
// the frozen JS state (e.g. a stale triage result) instead of truly
// re-running from scratch. Force a real reload so every page view starts
// from a clean slate.
window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    window.location.reload();
  }
});

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
