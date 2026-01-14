import requests
import base64

# Small red dot as base64
BASE64_IMAGE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg=="

URL = "http://localhost:8000/candidates"

payload = {
    "name": "Test Candidate",
    "position": "Test",
    "party": "Test Party",
    "electionId": 1,
    "imageBase64": BASE64_IMAGE
}

try:
    # First ensure at least one election exists
    requests.post("http://localhost:8000/elections", json={
        "name": "Test Election",
        "startDate": "2026-01-13T00:00:00",
        "endDate": "2026-01-14T00:00:00",
        "status": "active"
    })
    
    print("Testing Candidate Push...")
    response = requests.post(URL, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if "imageUrl" in response.json() and response.json()["imageUrl"]:
        print("SUCCESS: Image URL generated!")
    else:
        print("FAILED: Image URL is empty.")

except Exception as e:
    print(f"Error: {e}")
