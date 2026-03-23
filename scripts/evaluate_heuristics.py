from app.compiler import compile_text_v2
from app.emitters import emit_system_prompt_v2, emit_user_prompt_v2

prompts = [
    "Extract user names, emails and phone numbers from the following text into a JSON format. Make it extremely detailed but very short.",
    "Teach me how gradient descent works for beginners in 5 minutes.",
    "I need you to write a Python script that scrapes a website. I'm getting a 403 Forbidden error.",
]

for i, text in enumerate(prompts, 1):
    print(f"\n{'='*50}\nTEST {i}: {text}\n{'='*50}")
    ir2 = compile_text_v2(text)
    system_prompt = emit_system_prompt_v2(ir2)
    user_prompt = emit_user_prompt_v2(ir2)

    print("\n--- SYSTEM PROMPT ---")
    print(system_prompt)
    print("\n--- USER PROMPT ---")
    print(user_prompt)
    print("\n--- CONSTRAINTS IN IR ---")
    for c in ir2.constraints:
        print(f" - {c.text}")
