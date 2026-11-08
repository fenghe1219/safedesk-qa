from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from qa.sse import SSEFrame, parse_sse


@dataclass(frozen=True, slots=True)
class SSEResponse:
    status_code: int
    headers: dict[str, str]
    frames: list[SSEFrame]
    text: str

    @property
    def request_id(self) -> str | None:
        return self.headers.get("x-request-id")

    def data(self, event: str) -> list[Any]:
        return [frame.data for frame in self.frames if frame.event == event]

    def first(self, event: str) -> Any | None:
        return next((frame.data for frame in self.frames if frame.event == event), None)

    @property
    def names(self) -> list[str]:
        return [frame.event for frame in self.frames]


class SafeDeskClient:
    """Small, explicit HTTP client used by black-box tests and the evaluator."""

    def __init__(self, base_url: str, *, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.http = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
            follow_redirects=False,
            headers={"User-Agent": "safedesk-qa/0.1"},
        )
        self.csrf_token: str | None = None
        self.me: dict[str, Any] | None = None

    def __enter__(self) -> SafeDeskClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self.http.close()

    @property
    def user(self) -> dict[str, Any]:
        if not self.me:
            raise RuntimeError("Client is not authenticated")
        return self.me["user"]

    def login(self, email: str, password: str) -> httpx.Response:
        response = self.http.post(
            "/api/auth/login",
            json={"email": email, "password": password},
            timeout=self.timeout,
        )
        if response.status_code == 200:
            self.csrf_token = (
                self.http.cookies.get("sd_csrf") or response.cookies.get("sd_csrf")
            )
            self.me = response.json()
        return response

    def login_ok(self, email: str, password: str) -> dict[str, Any]:
        response = self.login(email, password)
        assert response.status_code == 200, response.text
        assert self.csrf_token, "Login succeeded without a CSRF cookie"
        assert self.me is not None
        return self.me

    def request(
        self,
        method: str,
        path: str,
        *,
        csrf: bool = False,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        request_headers = dict(headers or {})
        if csrf:
            if not self.csrf_token:
                raise RuntimeError("CSRF token missing; login first")
            request_headers.setdefault("X-CSRF-Token", self.csrf_token)
        if "json" in kwargs:
            request_headers.setdefault("Content-Type", "application/json")
        timeout = kwargs.pop("timeout", self.timeout)
        return self.http.request(
            method,
            path,
            headers=request_headers,
            timeout=timeout,
            **kwargs,
        )

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, *, csrf: bool = False, **kwargs: Any) -> httpx.Response:
        return self.request("POST", path, csrf=csrf, **kwargs)

    def patch(self, path: str, *, csrf: bool = False, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", path, csrf=csrf, **kwargs)

    def put(self, path: str, *, csrf: bool = False, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", path, csrf=csrf, **kwargs)

    def delete(self, path: str, *, csrf: bool = False, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", path, csrf=csrf, **kwargs)

    def create_case(self, title: str) -> dict[str, Any]:
        response = self.post("/api/cases", csrf=True, json={"title": title})
        assert response.status_code == 201, response.text
        return response.json()

    def send_message(
        self,
        case_id: str,
        content: str,
        *,
        client_message_id: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> SSEResponse:
        headers = dict(extra_headers or {})
        headers.setdefault("X-CSRF-Token", self.csrf_token or "")
        headers.setdefault("Content-Type", "application/json")
        payload: dict[str, Any] = {"content": content}
        if client_message_id:
            payload["client_message_id"] = client_message_id
        with self.http.stream(
            "POST",
            f"/api/cases/{case_id}/messages",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        ) as response:
            body = b"".join(response.iter_bytes()).decode("utf-8", errors="replace")
            return SSEResponse(
                status_code=response.status_code,
                headers={key.lower(): value for key, value in response.headers.items()},
                frames=parse_sse(body),
                text=body,
            )

    def get_json(self, path: str, **kwargs: Any) -> Any:
        response = self.get(path, **kwargs)
        assert response.status_code == 200, f"{path}: {response.status_code} {response.text}"
        return response.json()

    def audit_events(self, **params: Any) -> dict[str, Any]:
        response = self.get("/api/audit/events", params={"limit": 200, **params})
        assert response.status_code == 200, response.text
        return response.json()

    def cases_by_prefix(self, prefix: str, limit: int = 50) -> list[dict[str, Any]]:
        data = self.get_json("/api/cases", params={"limit": limit})
        return [item for item in data["items"] if item["title"].startswith(prefix)]

    def health(self) -> bool:
        try:
            response = self.get("/api/health", timeout=5)
            return response.status_code == 200 and response.json().get("database") == "ok"
        except httpx.HTTPError:
            return False

