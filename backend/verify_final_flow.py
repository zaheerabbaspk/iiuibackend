import requests
import json

BASE_URL = "http://192.168.1.28:8000"

def test_full_flow():
    try:
        print("--- 1. Admin: Pushing a Token ---")
        push_data = {
            "token": "FINAL-TEST-1",
            "electionId": "ELEC-001"
        }
        r = requests.post(f"{BASE_URL}/admin/save-token", json=push_data)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            print(f"Response: {r.json()}")
        else:
            print(f"Error: {r.text}")
            return

        print("\n--- 2. Admin: Getting all tokens ---")
        r = requests.get(f"{BASE_URL}/admin/get-tokens")
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            tokens = r.json()
            print(f"Tokens count: {len(tokens)}")
        else:
            print(f"Error: {r.text}")
            return
        
        print("\n--- 3. User: Login with Token ---")
        login_data = {"token": "FINAL-TEST-1"}
        r = requests.post(f"{BASE_URL}/access-token", json=login_data)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            login_resp = r.json()
            print(f"Login Success: {login_resp['status']}")
            
            candidates = login_resp.get('candidates', [])
            if candidates:
                cand_id = candidates[0]['id']
                print(f"\n--- 4. User: Voting for candidate {candidates[0]['name']} (ID: {cand_id}) ---")
                vote_data = {
                    "token": "FINAL-TEST-1",
                    "candidateId": cand_id
                }
                r = requests.post(f"{BASE_URL}/vote", json=vote_data)
                print(f"Status: {r.status_code}, Response: {r.json()}")
                
                print("\n--- 5. User: Voting AGAIN with same token (Should Fail) ---")
                r = requests.post(f"{BASE_URL}/vote", json=vote_data)
                print(f"Status: {r.status_code}, Expected Error: {r.json().get('detail')}")

                print("\n--- 6. User: Login AGAIN with same token (Should Fail) ---")
                r = requests.post(f"{BASE_URL}/access-token", json=login_data)
                print(f"Status: {r.status_code}, Expected Error: {r.json().get('detail')}")
        else:
            print(f"Error: {r.text}")

    except Exception as e:
        print(f"CRITICAL SCRIPT ERROR: {e}")

if __name__ == "__main__":
    test_full_flow()
