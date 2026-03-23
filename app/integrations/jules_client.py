from __future__ import annotations

import os
from typing import Any, Optional

import httpx


class JulesClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = "https://jules.googleapis.com",
        timeout: float = 30.0,
        transport: Any | None = None,
    ) -> None:
        self.api_key = (api_key or os.getenv("JULES_API_KEY", "")).strip()
        if not self.api_key:
            raise RuntimeError("JULES_API_KEY is not configured.")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"X-Goog-Api-Key": self.api_key}

        if self._transport is not None:
            response = self._transport.request(
                method,
                path,
                headers=headers,
                json=json,
                params=params,
            )
        else:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                response = client.request(
                    method,
                    path,
                    headers=headers,
                    json=json,
                    params=params,
                )

        response.raise_for_status()
        if not getattr(response, "content", None):
            return {}
        return response.json()

    def list_sources(self) -> dict[str, Any]:
        return self._request("GET", "/v1alpha/sources")

    def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1alpha/sessions", json=payload)

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1alpha/sessions/{session_id}")

    def list_activities(self, session_id: str, page_size: int = 30) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/v1alpha/sessions/{session_id}/activities",
            params={"pageSize": page_size},
        )

    def approve_plan(self, session_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v1alpha/sessions/{session_id}:approvePlan", json={})

    def send_message(self, session_id: str, prompt: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1alpha/sessions/{session_id}:sendMessage",
            json={"prompt": prompt},
        )
