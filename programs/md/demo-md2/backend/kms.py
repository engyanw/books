# -*- coding: utf-8 -*-
"""密钥管理服务（KMS）/ Vault 密钥提供者。

目标：把 AI 主密钥（用于 HKDF 派生 Fernet）的来源抽象化，支持：
- env  : 直接从环境变量读（默认，向后兼容现有 AI_ENC_KEY/AI_ENC_KEY_PREVIOUS）
- vault: HashiCorp Vault KV v2（VAULT_ADDR/VAULT_TOKEN/VAULT_SECRET_PATH）
- http : 任意 HTTP 端点返回 JSON（KMS_URL/KMS_TOKEN/KMS_JSON_KEY），便于接云厂商

主密钥明文只活在进程内（带 TTL 缓存），永不落盘、永不回传前端。
轮换：current = 主路径；previous = 历史路径列表（逗号分隔），用于解密旧密文。
"""
import os
import time

_cache: dict[str, tuple[float, str]] = {}  # key -> (expires_at, value)
_TTL = 300.0  # 5 分钟缓存，避免高频请求 KMS


def _provider() -> str:
    return (os.environ.get("KMS_PROVIDER") or "env").lower()


def _cached(key: str, fetch):
    now = time.time()
    ent = _cache.get(key)
    if ent and ent[0] > now:
        return ent[1]
    val = fetch()
    _cache[key] = (now + _TTL, val)
    return val


def _fetch_env_current() -> str:
    v = os.environ.get("AI_ENC_KEY")
    if v:
        return v
    # 回退到 config 常量（含 AUTH_SECRET 默认），与历史 _ai_build_ciphers 行为一致
    try:
        from config import AI_ENC_KEY
        if AI_ENC_KEY:
            return AI_ENC_KEY
    except Exception:
        pass
    return os.environ.get("AUTH_SECRET") or ""


def _fetch_env_previous() -> list[str]:
    return [m.strip() for m in os.environ.get("AI_ENC_KEY_PREVIOUS", "").split(",") if m.strip()]


def _http_get(url: str, token: str, json_key: str) -> str:
    import httpx
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = httpx.get(url, headers=headers, timeout=10.0)
    r.raise_for_status()
    data = r.json()
    # 支持 a.b.c 路径
    cur = data
    for seg in (json_key or "").split("."):
        if seg:
            cur = cur.get(seg) if isinstance(cur, dict) else None
    return str(cur or "")


def _fetch_vault(path: str) -> str:
    addr = os.environ.get("VAULT_ADDR", "").rstrip("/")
    token = os.environ.get("VAULT_TOKEN", "")
    # KV v2：/v1/secret/data/<path> → .data.data.<key>
    url = f"{addr}/v1/secret/data/{path}"
    import httpx
    headers = {"X-Vault-Token": token} if token else {}
    r = httpx.get(url, headers=headers, timeout=10.0)
    r.raise_for_status()
    payload = r.json().get("data", {}).get("data", {})
    # 取第一个非元数据字段，或显式 KMS_FIELD
    field = os.environ.get("KMS_FIELD")
    if field:
        return str(payload.get(field, ""))
    for k in ("key", "master_key", "ai_enc_key", "value"):
        if k in payload:
            return str(payload[k])
    # 单值：取第一个 str
    for v in payload.values():
        if isinstance(v, str):
            return v
    return ""


def resolve_current() -> str:
    """当前主密钥材料（明文 str，进程内缓存）。"""
    p = _provider()
    if p == "vault":
        path = os.environ.get("VAULT_SECRET_PATH") or ""
        if not path:
            return _fetch_env_current()
        return _cached("kms:current", lambda: _fetch_vault(path))
    if p in ("http", "cloud"):
        url = os.environ.get("KMS_URL") or ""
        if not url:
            return _fetch_env_current()
        return _cached("kms:current", lambda: _http_get(url, os.environ.get("KMS_TOKEN", ""), os.environ.get("KMS_JSON_KEY", "")))
    return _fetch_env_current()  # env


def resolve_previous() -> list[str]:
    """历史主密钥材料列表（用于解密旧密文，按声明顺序）。"""
    p = _provider()
    if p == "vault":
        paths = [x.strip() for x in os.environ.get("VAULT_PREVIOUS_PATHS", "").split(",") if x.strip()]
        out = []
        for i, path in enumerate(paths):
            out.append(_cached(f"kms:prev{i}", lambda path=path: _fetch_vault(path)))
        return out
    if p in ("http", "cloud"):
        urls = [x.strip() for x in os.environ.get("KMS_PREVIOUS_URLS", "").split(",") if x.strip()]
        out = []
        for i, url in enumerate(urls):
            out.append(_cached(f"kms:prev{i}", lambda url=url: _http_get(url, os.environ.get("KMS_TOKEN", ""), os.environ.get("KMS_JSON_KEY", ""))))
        return out
    return _fetch_env_previous()


def status() -> dict:
    """供运维诊断：当前提供者与是否成功解析（不泄露密钥明文）。"""
    try:
        cur = resolve_current()
        prev = resolve_previous()
        return {"provider": _provider(), "has_current": bool(cur), "previous_count": len(prev)}
    except Exception as e:
        return {"provider": _provider(), "has_current": False, "previous_count": 0, "error": f"{type(e).__name__}: {e}"}


def clear_cache():
    _cache.clear()
