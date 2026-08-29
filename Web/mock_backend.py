from http.server import BaseHTTPRequestHandler, HTTPServer
import json

SAMPLE = {
    "status": "success",
    "filename": "patient_report_1082.pdf",
    "parsed_vitals": {
        "patient_id": "PAT-1082",
        "spo2": 88,
        "heart_rate": 115,
        "systolic_bp": 145,
        "age": 62,
        "findings": "Bilateral lower lobe infiltration with ground glass opacities and mild pleural effusion.",
    },
    "triage_severity_level": 4,
    "predicted_disease": "Pneumonia",
    "disease_confidence": 0.89,
    "disease_probabilities": {
        "Pneumonia": 0.89,
        "Bronchitis": 0.06,
        "COVID-19": 0.03,
        "Normal": 0.02,
    },
    "life_expectancy_years": {
        "Pneumonia": 8.4,
        "Bronchitis": 14.1,
        "COVID-19": 12.7,
        "Normal": 22.0,
    },
    "raw_text_snippet": "Patient ID: PAT-1082 Age: 62 SpO2: 88% HR: 115 BPM BP: 145/90...",
}


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self._json({"status": "active", "system": "MedVision Guard Engine"})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/analyze-pdf":
            # drain body
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            self._json(SAMPLE)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
