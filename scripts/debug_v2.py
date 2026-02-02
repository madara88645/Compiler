
import urllib.request
import json
import time

url = "http://localhost:8080/compile"
data = {
    "text": "Explain quantum computing to a 5 year old",
    "diagnostics": False,
    "v2": True,
    "render_v2_prompts": True
}
headers = {'Content-Type': 'application/json'}

print(f"Sending request to {url}...")
t0 = time.time()
try:
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers)
    with urllib.request.urlopen(req) as response:
        elapsed = time.time() - t0
        print(f"Time: {elapsed:.2f}s")
        res_data = json.load(response)
        
        # Check keys
        v2_system = res_data.get("system_prompt_v2")
        v2_ir = res_data.get("ir_v2")
        
        print(f"Has system_prompt_v2: {bool(v2_system)}")
        if v2_system:
            print(f"V2 Length: {len(v2_system)}")
            print(f"V2 Preview: {v2_system[:50]}...")
        else:
            print("❌ V2 System Prompt MISSING")

        if v2_ir:
            print("✅ V2 IR Present")
        else:
            print("❌ V2 IR MISSING (Fallback triggered?)")

except Exception as e:
    print(f"Error: {e}")
