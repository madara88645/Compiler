import re

with open("app/integrations/jules_client.py", "r") as f:
    content = f.read()

# Fix __init__
init_search = """        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport
        # Bolt Optimization: Persist httpx.Client to reuse connection pool and avoid instantiation overhead on every request
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)"""

init_replace = """        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport
        # Bolt Optimization: Persist httpx.Client to reuse connection pool and avoid instantiation overhead on every request
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout, transport=self._transport)"""

content = content.replace(init_search, init_replace)

# Modify _request
request_search = """        if self._transport is not None:
            response = self._transport.request(
                method,
                path,
                headers=headers,
                json=json,
                params=params,
            )
        else:
            response = self._client.request(
                method,
                path,
                headers=headers,
                json=json,
                params=params,
            )"""

request_replace = """        response = self._client.request(
            method,
            path,
            headers=headers,
            json=json,
            params=params,
        )"""

content = content.replace(request_search, request_replace)

with open("app/integrations/jules_client.py", "w") as f:
    f.write(content)

print("Patch 2 applied")
