"""
Test a single transaction to see the exact validation error.
"""
import pandas as pd
import requests
import json

# Read first transaction
csv_path = "/Users/I758002/dinnr-singhacks/transactions_mock_1000_for_participants.csv"
df = pd.read_csv(csv_path)
transaction = df.iloc[1]  # Get second row (first had issues)

print("Transaction from CSV:")
print(transaction.to_dict())
print("\n" + "="*60 + "\n")

# Map sanctions_screening values
sanctions_map = {
    "none": "PASS",
    "potential": "REVIEW",
    "confirmed": "FAIL"
}
sanctions_value = transaction.get('sanctions_screening', 'none')
sanctions_result = sanctions_map.get(str(sanctions_value).lower(), "PASS")

# Ensure swift_mt matches pattern
swift_mt = transaction.get('swift_mt', '')
if pd.isna(swift_mt) or not str(swift_mt).strip():
    swift_mt = "MT103"
else:
    swift_mt = str(swift_mt).strip()
    if not swift_mt.startswith("MT"):
        swift_mt = "MT103"

# Parse value_date
from datetime import datetime
value_date_str = transaction.get('value_date', '')
if pd.notna(value_date_str):
    try:
        value_date_parsed = datetime.strptime(str(value_date_str), '%d/%m/%Y')
        value_date_iso = value_date_parsed.isoformat() + "Z"
    except ValueError:
        value_date_iso = transaction['booking_datetime']
else:
    value_date_iso = transaction['booking_datetime']

payload = {
    "originator_name": str(transaction['originator_name']),
    "originator_account": str(transaction['originator_account']),
    "originator_country": str(transaction['originator_country'])[:2],
    "beneficiary_name": str(transaction['beneficiary_name']),
    "beneficiary_account": str(transaction['beneficiary_account']),
    "beneficiary_country": str(transaction['beneficiary_country'])[:2],
    "amount": float(transaction['amount']),
    "currency": str(transaction['currency'])[:3],
    "transaction_date": transaction['booking_datetime'],
    "value_date": value_date_iso,
    "swift_message_type": swift_mt,
    "sanctions_screening_result": sanctions_result,
    "ordering_institution": str(transaction['ordering_institution_bic']) if pd.notna(transaction['ordering_institution_bic']) else None,
    "beneficiary_institution": str(transaction['beneficiary_institution_bic']) if pd.notna(transaction['beneficiary_institution_bic']) else None,
    "pep_screening_result": "REVIEW" if transaction.get('customer_is_pep', False) else "PASS"
}

print("Payload being sent:")
print(json.dumps(payload, indent=2, default=str))
print("\n" + "="*60 + "\n")

# Send request
url = "http://localhost:8000/api/v1/payments/analyze"
try:
    response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")
