from dotenv import load_dotenv

load_dotenv()

import os
from openai import OpenAI

print("Model: llama-3.3-70b-versatile")
print(f"Base URL: {os.getenv('OPENAI_BASE_URL')}")

try:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL"))

    import time

    start = time.time()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "Kuantum fiziği nedir? 2 cümle ile açıkla."}],
        max_tokens=100,
    )
    elapsed = time.time() - start

    print(f"\nResponse:\n{response.choices[0].message.content}")
    print(f"\nTime: {elapsed:.2f}s")
except Exception as e:
    print(f"ERROR: {e}")
