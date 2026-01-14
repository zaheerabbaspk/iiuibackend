import requests
import json

BASE_URL = "http://192.168.1.28:8000"

def test_batch_flow():
    print("--- 1. Admin: Creating Two Elections ---")
    e1 = requests.post(f"{BASE_URL}/elections", json={"name": "Election Alpha", "description": "Test 1", "startDate": "2026-01-13T10:00:00", "endDate": "2026-12-31T10:00:00", "status": "Active"}).json()
    e2 = requests.post(f"{BASE_URL}/elections", json={"name": "Election Beta", "description": "Test 2", "startDate": "2026-01-13T10:00:00", "endDate": "2026-12-31T10:00:00", "status": "Active"}).json()
    
    eid1, eid2 = str(e1['id']), str(e2['id'])
    print(f"Created Elections: {eid1}, {eid2}")

    print("\n--- 2. Admin: Generating Batch of 3 Tokens for BOTH Elections ---")
    gen_data = {
        "electionIds": [eid1, eid2],
        "count": 3
    }
    r = requests.post(f"{BASE_URL}/tokens/generate", json=gen_data)
    batch = r.json()
    print(f"Batch Generated: {batch['batchId']}, Tokens: {[t['token'] for t in batch['tokens']]}")

    print("\n--- 3. Admin: GET All Tokens (Check Grouping) ---")
    r = requests.get(f"{BASE_URL}/admin/get-tokens")
    groups = r.json()
    for g in groups:
        if g['batchId'] == batch['batchId']:
            print(f"Found Group: {g['batchId']}")
            print(f"Associated Elections: {[e['name'] for e in g['elections']]}")
            print(f"Tokens in Batch: {len(g['tokens'])}")

    print("\n--- 4. User: Login with Token ---")
    test_token = batch['tokens'][0]['token']
    r = requests.post(f"{BASE_URL}/access-token", json={"token": test_token})
    login_data = r.json()
    print(f"Login Success: {login_data['status']}")
    print(f"Authorized Elections: {[e['name'] for e in login_data['authorizedElections']]}")
    
    print("\n--- 5. User: Voting test soon ---")

if __name__ == "__main__":
    test_batch_flow()
