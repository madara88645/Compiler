import re

with open("api/auth.py", "r") as f:
    content = f.read()

# The code review pointed out that we shouldn't have test logic in production auth.py.
# The previous version used:
old_logic = """
        # Check for pytest bypassing rate limits - but only if we are NOT running an explicit rate limit test
        # We can check if "test_rate_limit" or "test_verify_api_key_rate_limit" is in PYTEST_CURRENT_TEST
        is_test_env = "PYTEST_CURRENT_TEST" in os.environ or (request.client and request.client.host in ("testclient", "unknown_ip"))
        is_rate_limit_test = "test_rate_limit" in os.environ.get("PYTEST_CURRENT_TEST", "") or "test_verify_api_key_rate_limit" in os.environ.get("PYTEST_CURRENT_TEST", "")

        if is_test_env and not is_rate_limit_test:
            pass  # Bypass rate limiting for standard tests
        else:
            history = RATE_LIMIT_STORE.get(store_key, [])
            # Filter out timestamps older than window
            history = [t for t in history if t > now - RATE_LIMIT_WINDOW]

            if len(history) >= max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded"
                )

            history.append(now)
            RATE_LIMIT_STORE[store_key] = history
"""

new_logic = """
        history = RATE_LIMIT_STORE.get(store_key, [])
        # Filter out timestamps older than window
        history = [t for t in history if t > now - RATE_LIMIT_WINDOW]

        if len(history) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded"
            )

        history.append(now)
        RATE_LIMIT_STORE[store_key] = history
"""
content = content.replace(old_logic, new_logic)

with open("api/auth.py", "w") as f:
    f.write(content)
