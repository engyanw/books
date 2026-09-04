# -*- coding: utf-8 -*-
"""PG 双模式回归：在真实 PostgreSQL 上跑核心流程，验证 pg_adapter 包装器 +
统一 schema 建表。覆盖：注册/登录、文档 CRUD、版本快照、批注、建议、分支合并、
release、模板实例化、Git 绑定（不实际 push/pull）、断链、transclusion、
中文检索（PG 走 ILIKE 子串，验证 CJK 不退化）。

前置：先运行 ./setup_pg_test.sh 建库；需 asyncpg 已安装。
CI：.github/workflows/ci.yml 的 pg job 起 postgres 服务跑本文件；
    无 PG 时自动跳过（不阻断 SQLite 通用套件）。
"""
import os, traceback

DATABASE_URL = os.environ.get("MD2_PG_TEST_URL") or "postgresql://demo_md2:md2pass@127.0.0.1:5432/demo_md2_test"


def _pg_available() -> bool:
    """demo_md2 角色与库是否就绪。未就绪则跳过，避免无 PG 环境（如 SQLite-only CI）误报。"""
    try:
        import asyncio, asyncpg
        async def _p():
            c = await asyncpg.connect(DATABASE_URL)
            await c.close()
        asyncio.run(_p())
        return True
    except Exception:
        return False


if __name__ == "__main__" and not _pg_available():
    print("SKIP（PG 不可达：先运行 ./setup_pg_test.sh 建库，或由 CI pg job 提供 postgres 服务）")
    raise SystemExit(0)

os.environ["DATABASE_URL"] = DATABASE_URL
os.environ["AUTH_ALLOW_REGISTER"] = "true"

from fastapi.testclient import TestClient
import main  # noqa: E402


def run():
    with TestClient(main.app) as c:
        # 管理员（本测试流程不依赖管理员权限，此处仅注册普通属主；已存在则直接登录）
        c.post("/api/auth/register", json={"username": "owner", "password": "p@ssw0rd"})
        t = c.post("/api/auth/login", json={"username": "owner", "password": "p@ssw0rd"}).json()["token"]
        h = {"Authorization": f"Bearer {t}"}

        # 文档 CRUD
        r = c.post("/api/docs", headers=h, json={"title": "hello", "content": "# hi\nworld"}).json()
        did = r["doc_id"]
        d = c.get(f"/api/docs/{did}", headers=h).json()
        assert d["title"] == "hello" and "world" in d["content"], d

        # 更新 + 版本快照
        c.put(f"/api/docs/{did}", headers=h, json={"content": "# hi\nworld v2", "title": "hello"})
        vers = c.get(f"/api/docs/{did}/versions", headers=h).json()["items"]
        assert len(vers) >= 1, vers

        # 批注
        cm = c.post(f"/api/docs/{did}/comments", headers=h,
                    json={"doc_version": d["version"], "anchor_type": "line",
                          "anchor_start": 1, "anchor_end": 1, "body": "看这里"}).json()
        assert cm["id"], cm
        cl = c.get(f"/api/docs/{did}/comments", headers=h).json()["items"]
        assert any(x["body"] == "看这里" for x in cl), cl

        # 建议 + 接受（in-place 替换）
        sg = c.post(f"/api/docs/{did}/suggestions", headers=h,
                    json={"original_text": "world v2", "proposed_text": "WORLD V2",
                          "comment": "大写"}).json()
        assert sg["id"], sg
        dec = c.put(f"/api/docs/{did}/suggestions/{sg['id']}?status=accepted", headers=h).json()
        assert dec["replaced"], dec
        d2 = c.get(f"/api/docs/{did}", headers=h).json()
        assert "WORLD V2" in d2["content"], d2

        # 分支合并（无冲突快进）
        br = c.post(f"/api/docs/{did}/branches", headers=h).json()
        bid = br["branch_id"]
        c.put(f"/api/docs/{did}/branches/{bid}", headers=h, json={"head_content": "# hi\nWORLD V2\nbranch line"}).json()
        mg = c.post(f"/api/docs/{did}/branches/{bid}/merge", headers=h).json()
        assert mg["merged"] and not mg["conflict"], mg
        d3 = c.get(f"/api/docs/{did}", headers=h).json()
        assert "branch line" in d3["content"], d3

        # release
        rel = c.post("/api/releases", headers=h, json={"name": "r1", "version": "1.0", "doc_ids": [did]}).json()
        assert rel["release_id"], rel
        rdet = c.get(f"/api/releases/{rel['release_id']}", headers=h).json()
        assert any(m["doc_id"] == did for m in rdet["manifest"]), rdet

        # 模板实例化（内置）
        bl = c.get("/api/templates/builtin", headers=h).json()["items"]
        assert {"rfc", "design-doc", "runbook", "adr"} <= {i["name"] for i in bl}, bl
        inst = c.post("/api/templates/builtin/rfc/instantiate", headers=h,
                      json={"variables": {"title": "T", "author": "a", "date": "2026-08-15",
                                           "status": "草案", "summary": "s", "motivation": "m",
                                           "design": "d", "risks": "r"}, "title": "RFC-T"}).json()
        di = c.get(f"/api/docs/{inst['doc_id']}", headers=h).json()
        assert "a" in di["content"] and "d" in di["content"], di

        # Git 绑定（仅建绑定，不 push/pull）
        gb = c.post(f"/api/docs/{did}/git", headers=h, json={
            "repo_url": "https://example.com/r.git", "branch": "main",
            "file_path": "d.md", "token": "tok123", "auto_publish": False}).json()
        assert gb["bound"] if "bound" in gb else gb["id"], gb
        gq = c.get(f"/api/docs/{did}/git", headers=h).json()
        assert gq["bound"] and gq["repo_url"].endswith("r.git") and gq["token_bound"], gq

        # 断链：源文档含有效 + 失效链接
        src = c.post("/api/docs", headers=h, json={"title": "src", "content": f"see [[{did}]] and [[NOPE]]"}).json()["doc_id"]
        lk = c.get(f"/api/docs/{src}/links", headers=h).json()["items"]
        items = {i["target_ref"]: i for i in lk}
        assert items.get(did, {}).get("broken") is False, lk
        assert items.get("NOPE", {}).get("broken") is True, lk

        # transclusion
        c.put(f"/api/docs/{did}", headers=h, json={"content": f"!include[[{src}]]", "title": "hello"})
        res = c.get(f"/api/docs/{did}/resolved", headers=h).json()
        assert "see" in res["content"], res  # 内联了 src 内容

        # 全文搜索：PG 走 pg_trgm ILIKE（应命中，大小写不敏感）
        c.post("/api/docs", headers=h, json={"title": "SearchProbeEN", "content": "UniqueNeedleToken here"}).json()
        sr = c.get("/api/search?q=UniqueNeedleToken", headers=h).json()
        assert any("SearchProbeEN" == i["title"] for i in sr["items"]), sr
        # 大小写不敏感：小写查询也应命中
        sr2 = c.get("/api/search?q=uniqueneedletoken", headers=h).json()
        assert any(i["title"] == "SearchProbeEN" for i in sr2["items"]), sr2

        # 中文检索：PG 走 ILIKE 子串匹配（pg_trgm 不可用时不影响子串命中），验证 CJK 不退化
        c.post("/api/docs", headers=h, json={"title": "项目周报", "content": "本周完成需求评审与架构设计"}).json()
        sr_zh = c.get("/api/search?q=架构设计", headers=h).json()
        assert any(i["title"] == "项目周报" for i in sr_zh["items"]), sr_zh
        sr_zh2 = c.get("/api/search?q=周报", headers=h).json()
        assert any(i["title"] == "项目周报" for i in sr_zh2["items"]), sr_zh2

        # 相关性排序：标题精确命中应排在仅内容命中的前面（pg_trgm similarity）
        c.post("/api/docs", headers=h, json={"title": "架构设计专题", "content": "无关内容 xyz"}).json()
        sr_rel = c.get("/api/search?q=架构设计", headers=h).json()
        titles = [i["title"] for i in sr_rel["items"]]
        assert "架构设计专题" in titles, sr_rel
        # 标题命中者应排在内容命中者（项目周报）之前
        assert titles.index("架构设计专题") < titles.index("项目周报"), titles

        # /ready 应 200
        assert c.get("/ready").status_code == 200

    print("ALL PASSED")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
