import urllib.request
import json

base = "http://localhost:8080"

def check(path, method="GET", data=None):
    url = f"{base}{path}"
    print(f"\nChecking {method} {url}...")
    try:
        if data:
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'}, method=method)
        else:
            req = urllib.request.Request(url, method=method)
        
        with urllib.request.urlopen(req) as response:
            print(f"✅ Status: {response.status}")
            print(response.read().decode()[:200])
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error: {e.code}")
        print(e.read().decode()[:200])
    except Exception as e:
        print(f"❌ Connection Error: {e}")

check("/health")
check("/docs")
check("/compile", "POST", {"text": "test", "diagnostics": False})
