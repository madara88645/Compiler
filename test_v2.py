import requests
import time

BASE_URL = "http://127.0.0.1:8080"

print("--- V2 (DeepSeek) Test ---")

try:
    print(f"Sending V2 request to {BASE_URL}/compile...")
    payload = {"text": "Write hello world", "v2": True, "render_v2_prompts": True}
    start = time.time()
    r = requests.post(f"{BASE_URL}/compile", json=payload, timeout=60)  # 60s timeout
    elapsed = time.time() - start
    print(f"V2 STATUS: {r.status_code} ({elapsed:.2f}s)")
    if r.status_code == 200:
        data = r.json()
        print(f"V2 processing_ms: {data.get('processing_ms', 'N/A')}")
        print(f"V2 ir_v2 present: {data.get('ir_v2') is not None}")
    else:
        print(f"V2 ERROR: {r.text[:500]}")
except requests.exceptions.Timeout:
    print("V2 TIMEOUT after 60 seconds!")
except Exception as e:
    print(f"V2 FAILED: {e}")

print("--- DONE ---")
