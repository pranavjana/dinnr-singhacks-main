import json
from pathlib import Path

payment = json.loads(Path("payment_payload.json").read_text())
analysis = json.loads(Path("analysis.json").read_text())

payload = {
    "payment": payment,
    "analysis": analysis
}

Path("triage_request.json").write_text(json.dumps(payload, indent=2))
print("Created triage_request.json")
