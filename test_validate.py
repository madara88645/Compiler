import requests

# Test bad prompt
bad_prompt = "merhaba"
r = requests.post("http://127.0.0.1:8080/validate", json={"text": bad_prompt}, timeout=30)
print(f"Response: {r.status_code}")
print(f"Full JSON: {r.json()}")
