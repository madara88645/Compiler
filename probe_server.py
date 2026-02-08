import requests
import time

# Test BOTH ports
for port in [8080, 8888]:
    BASE_URL = f"http://127.0.0.1:{port}"
    print(f"\n--- Testing PORT {port} ---")

    try:
        print(f"Checking {BASE_URL}...")
        r = requests.get(BASE_URL, timeout=3)
        print(f"ROOT STATUS: {r.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"PORT {port}: Connection REFUSED (server not running)")
        continue
    except requests.exceptions.Timeout:
        print(f"PORT {port}: TIMEOUT (server frozen)")
        continue
    except Exception as e:
        print(f"PORT {port}: FAILED: {e}")
        continue

    try:
        print(f"Checking {BASE_URL}/compile (V1)...")
        payload = {"text": "test", "v2": False}
        start = time.time()
        r = requests.post(f"{BASE_URL}/compile", json=payload, timeout=5)
        elapsed = time.time() - start
        print(f"COMPILE STATUS: {r.status_code} ({elapsed:.2f}s)")
    except Exception as e:
        print(f"COMPILE FAILED: {e}")

print("\n--- DONE ---")
