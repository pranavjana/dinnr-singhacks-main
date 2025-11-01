import json
from pathlib import Path

# Use the full sample as the payment
payment = json.loads(Path("sample.json").read_text())

# Create a simple analysis result
analysis = {
    "verdict": "suspicious",
    "risk_score": 75,
    "justification": "High-risk jurisdiction (Iran) involved",
    "assigned_team": "AML_TEAM_1",
    "narrative_summary": "Large CHF transaction from Iranian originator",
    "rule_references": ["HIGHRISK_001"],
    "triggered_rules": [{"rule_id": "HIGHRISK_001", "rule_type": "high_risk_jurisdiction"}],
    "detected_patterns": [],
    "llm_patterns": [],
    "llm_flagged_transactions": [],
    "notable_transactions": [],
    "recommended_actions": ["manual_review"]
}

payload = {
    "payment": payment,
    "analysis": analysis
}

Path("triage_request.json").write_text(json.dumps(payload, indent=2))
print("Created triage_request.json with full transaction data")
