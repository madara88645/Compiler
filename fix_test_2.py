import re

with open("tests/test_auth_fast_path.py", "r") as f:
    content = f.read()

# Fix test_rate_limit. The endpoint /compile/fast has a limit of 2 now.
old_rate_test = """
    # Send 10 requests (allowed)
    for _ in range(10):
        with patch("api.main.hybrid_compiler") as mock:
            mock.cache = {}
            mock.worker.process.return_value = MagicMock(
                ir=MagicMock(model_dump=lambda: {}),
                system_prompt="",
                user_prompt="",
                plan="",
                optimized_content="",
            )
            client.post("/compile/fast", json={"text": "h"}, headers={"x-api-key": test_key})

    # 11th request should fail
    with patch("api.main.hybrid_compiler") as mock:
        mock.cache = {}
        resp = client.post("/compile/fast", json={"text": "h"}, headers={"x-api-key": test_key})
        assert resp.status_code == 429
"""

new_rate_test = """
    from api.auth import HEAVY_RATE_LIMIT_MAX_REQUESTS

    # Send allowed requests
    for _ in range(HEAVY_RATE_LIMIT_MAX_REQUESTS):
        with patch("api.main.hybrid_compiler") as mock:
            mock.cache = {}
            mock.worker.process.return_value = MagicMock(
                ir=MagicMock(model_dump=lambda: {}),
                system_prompt="",
                user_prompt="",
                plan="",
                optimized_content="",
            )
            resp = client.post("/compile/fast", json={"text": "h"}, headers={"x-api-key": test_key})
            assert resp.status_code == 200

    # Next request should fail
    with patch("api.main.hybrid_compiler") as mock:
        mock.cache = {}
        resp = client.post("/compile/fast", json={"text": "h"}, headers={"x-api-key": test_key})
        assert resp.status_code == 429
"""

content = content.replace(old_rate_test, new_rate_test)

with open("tests/test_auth_fast_path.py", "w") as f:
    f.write(content)
