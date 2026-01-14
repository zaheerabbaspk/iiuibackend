import requests

def test_generate():
    url = "http://localhost:8000/tokens/generate"
    # Assuming election_id 1 exists or just testing the endpoint presence
    payload = {
        "electionId": 1,
        "count": 2
    }
    try:
        # First check if server is up
        health = requests.get("http://localhost:8000/elections")
        print("Elections status:", health.status_code)
        
        r = requests.post(url, json=payload)
        print("Status Code:", r.status_code)
        print("Response:", r.json())
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_generate()
