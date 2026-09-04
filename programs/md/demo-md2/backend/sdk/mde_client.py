# -*- coding: utf-8 -*-
"""MDE Open API Python SDK（OAuth2 客户端 + REST 调用）。

用法：
    client = MDEClient(base_url="https://mde.example.com",
                       client_id="c-...", client_secret="cs_...",
                       redirect_uri="http://localhost:8080/cb")
    # （服务端授权后拿到 code）
    token = client.exchange_code(code)            # 授权码换 access_token
    docs = client.list_docs()                     # 用该 token 调开放 API
    doc = client.create_doc(title="hi", content="# hello")
依赖：httpx（已在后端依赖中）。可通过 http= 注入测试用 httpx.Client。
"""
from __future__ import annotations
import httpx
from urllib.parse import urlencode


class MDEOAuthError(Exception):
    pass


class MDEClient:
    def __init__(self, base_url: str, client_id: str, client_secret: str,
                 redirect_uri: str, *, http: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token: str | None = None
        self._http = http  # 注入用（如 ASGITransport）；None 时用模块级 httpx

    def _client(self):
        return self._http if self._http is not None else httpx

    def authorize_url(self, scope: str = "docs:read docs:write", state: str = "") -> str:
        params = {"response_type": "code", "client_id": self.client_id,
                  "redirect_uri": self.redirect_uri, "scope": scope}
        if state:
            params["state"] = state
        return f"{self.base_url}/oauth/authorize?{urlencode(params)}"

    def exchange_code(self, code: str) -> str:
        r = self._client().post(f"{self.base_url}/oauth/token", data={
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }, timeout=15.0)
        if r.status_code != 200:
            raise MDEOAuthError(f"token 交换失败 {r.status_code}: {r.text}")
        self.access_token = r.json()["access_token"]
        return self.access_token

    def set_token(self, token: str):
        self.access_token = token

    def _h(self):
        if not self.access_token:
            raise MDEOAuthError("未设置 access_token")
        return {"Authorization": f"Bearer {self.access_token}"}

    def list_docs(self) -> list[dict]:
        return self._client().get(f"{self.base_url}/api/docs", headers=self._h(), timeout=15.0).json().get("items", [])

    def create_doc(self, title: str, content: str = "") -> dict:
        return self._client().post(f"{self.base_url}/api/docs", headers=self._h(),
                                   json={"title": title, "content": content}, timeout=15.0).json()

    def get_doc(self, doc_id: str) -> dict:
        return self._client().get(f"{self.base_url}/api/docs/{doc_id}", headers=self._h(), timeout=15.0).json()

    def update_doc(self, doc_id: str, title: str | None = None, content: str | None = None) -> dict:
        payload = {}
        if title is not None:
            payload["title"] = title
        if content is not None:
            payload["content"] = content
        return self._client().put(f"{self.base_url}/api/docs/{doc_id}", headers=self._h(),
                                  json=payload, timeout=15.0).json()

    def search(self, q: str) -> list[dict]:
        return self._client().get(f"{self.base_url}/api/search", headers=self._h(),
                                  params={"q": q}, timeout=15.0).json().get("items", [])
