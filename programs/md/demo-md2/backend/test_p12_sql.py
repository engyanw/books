# -*- coding: utf-8 -*-
"""P1-2 后端 SQL 逻辑验证（直连 sqlite，绕过 HTTP/TestClient）。

复用当前异步 DB 层：在临时目录下建用户库 → 直接用同步 sqlite3 跑 SQL 断言。
覆盖：标签聚合/按标签筛选/收藏/全文搜索/最近打开/软删除。
"""
import os, sys, tempfile, asyncio, sqlite3, secrets
from datetime import datetime, timezone

TMP = tempfile.mkdtemp(prefix="p12sql_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
sys.path.insert(0, os.path.dirname(__file__))

import main  # noqa: E402


async def _setup():
    # 在临时目录下建一个用户文档库 schema（直连 sqlite 验证 SQL 逻辑，绕过 HTTP）
    uid = "u_" + secrets.token_hex(4)
    import aiosqlite
    db = await aiosqlite.connect(main._user_db_path(uid))
    await main._apply_documents_schema(db)
    db.row_factory = sqlite3.Row
    return db


async def main_async():
    db = await _setup()
    results = []

    def check(name, cond):
        results.append((name, "OK" if cond else "FAIL"))

    ids = []
    for title, content in [("标签测试A", "苹果 香蕉"), ("标签测试B", "葡萄 橘子"), ("标签测试C", "苹果 葡萄")]:
        did = secrets.token_urlsafe(16)
        await db.execute(
            "INSERT INTO documents(doc_id,title,content,kind,path,version,created_at,updated_at) "
            "VALUES(?,?,?,?,?,1,datetime('now'),datetime('now'))",
            (did, title, content, "file", ""),
        )
        ids.append(did)
    await db.commit()
    idA, idB, idC = ids
    check("创建文档", (await (await db.execute("SELECT count(*) AS c FROM documents WHERE deleted_at IS NULL")).fetchone())["c"] == 3)

    await db.execute("UPDATE documents SET tags=? WHERE doc_id=?", ("水果,红色", idA))
    await db.execute("UPDATE documents SET tags=? WHERE doc_id=?", ("水果,黄色", idB))
    await db.execute("UPDATE documents SET tags=? WHERE doc_id=?", ("红色", idC))
    await db.execute("UPDATE documents SET starred=1 WHERE doc_id=?", (idA,))
    await db.commit()

    rows = await (await db.execute("SELECT tags FROM documents WHERE deleted_at IS NULL AND tags != ''")).fetchall()
    counter = {}
    for r in rows:
        for t in (r["tags"] or "").split(','):
            t = t.strip()
            if t:
                counter[t] = counter.get(t, 0) + 1
    check("标签聚合", counter.get("水果") == 2 and counter.get("红色") == 2 and counter.get("黄色") == 1)

    rows = await (await db.execute(
        "SELECT title FROM documents WHERE deleted_at IS NULL AND (tags LIKE ? OR tags = ?)",
        ("%红色%", "红色"),
    )).fetchall()
    check("按标签筛选", {r["title"] for r in rows} == {"标签测试A", "标签测试C"})

    rows = await (await db.execute("SELECT title FROM documents WHERE deleted_at IS NULL AND starred=1")).fetchall()
    check("按收藏筛选", {r["title"] for r in rows} == {"标签测试A"})

    rows = await (await db.execute(
        "SELECT title FROM documents WHERE deleted_at IS NULL AND (title LIKE ? OR content LIKE ?)",
        ("%苹果%", "%苹果%"),
    )).fetchall()
    check("全文搜索", {r["title"] for r in rows} == {"标签测试A", "标签测试C"})

    now = datetime.now(timezone.utc).isoformat()
    await db.execute("UPDATE documents SET last_opened_at=? WHERE doc_id=?", (now, idA))
    await db.commit()
    rows = await (await db.execute(
        "SELECT title FROM documents WHERE deleted_at IS NULL AND last_opened_at IS NOT NULL ORDER BY last_opened_at DESC"
    )).fetchall()
    check("最近打开排序", bool(rows) and rows[0]["title"] == "标签测试A")

    await db.execute("UPDATE documents SET deleted_at=? WHERE doc_id=?", (now, idC))
    await db.commit()
    rows = await (await db.execute(
        "SELECT title FROM documents WHERE deleted_at IS NULL AND (title LIKE ? OR content LIKE ?)",
        ("%苹果%", "%苹果%"),
    )).fetchall()
    check("软删除不影响搜索", {r["title"] for r in rows} == {"标签测试A"})

    await db.close()

    print("\n=== P1-2 后端 SQL 逻辑验证 ===")
    for name, status in results:
        print(f"  [{status}] {name}")
    passed = sum(1 for _, s in results if s == "OK")
    print(f"总计 {len(results)} 项，通过 {passed} 项")
    return 0 if passed == len(results) else 1


sys.exit(asyncio.run(main_async()))
