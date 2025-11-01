import pandas as pd
import requests
import json
from datetime import datetime

# Path to the transactions CSV
TRANSACTIONS_CSV = "/Users/I758002/dinnr-singhacks/transactions_mock_1000_for_participants.csv"

def analyze_transaction(transaction):
    """Submit a single transaction for analysis"""
    url = "http://localhost:8000/api/v1/payments/analyze"

    # Transform transaction to match the expected API schema
    payload = {
        "originator_name": transaction['originator_name'],
        "originator_account": transaction['originator_account'],
        "originator_country": transaction['originator_country'],
        "beneficiary_name": transaction['beneficiary_name'],
        "beneficiary_account": transaction['beneficiary_account'],
        "beneficiary_country": transaction['beneficiary_country'],
        "amount": float(transaction['amount']),
        "currency": transaction['currency'],
        "transaction_date": transaction['booking_datetime'] if pd.notna(transaction['booking_datetime']) else datetime.now().isoformat() + "Z",
        "value_date": transaction['value_date'] if pd.notna(transaction['value_date']) else datetime.now().isoformat() + "Z",
        "swift_message_type": transaction['swift_mt'] if pd.notna(transaction['swift_mt']) else "MT103",
        "sanctions_screening_result": transaction['sanctions_screening'] if pd.notna(transaction['sanctions_screening']) else "PASS",
        "ordering_institution": transaction['ordering_institution_bic'] if pd.notna(transaction['ordering_institution_bic']) else None,
        "beneficiary_institution": transaction['beneficiary_institution_bic'] if pd.notna(transaction['beneficiary_institution_bic']) else None,
        "pep_screening_result": "PASS" if not transaction.get('customer_is_pep', False) else "REVIEW"
    }

    try:
        response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error analyzing transaction: {e}")
        return None

def main():
    # Read the CSV
    df = pd.read_csv(TRANSACTIONS_CSV)

    # Analyze each transaction
    results = []
    for _, transaction in df.iterrows():
        result = analyze_transaction(transaction)
        if result:
            results.append(result)

        # Optional: Add a small delay or limit to avoid overwhelming the service
        # time.sleep(0.1)

    # Save results to a JSON file for further analysis
    with open('transaction_analysis_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    # Print summary
    print(f"Analyzed {len(results)} transactions")
    verdict_counts = {}
    for result in results:
        verdict = result.get('verdict', 'unknown')
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

    print("\nVerdict Summary:")
    for verdict, count in verdict_counts.items():
        print(f"{verdict}: {count}")

if __name__ == "__main__":
    main()