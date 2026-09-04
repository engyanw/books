# -*- coding: utf-8 -*-
"""P0-2 文档正文静态加密回归：开启 DOC_ATREST_ENCRYPTION 后，所有客户端可见路径返回明文，
而库内（直查 SQLite 文件）存储 atrestv1: 密文——证明 DBA 直查库无法读取正文。

覆盖：create→get、update→get、版本快照/读取/对比/恢复、transclusion、建议接受(in-place 替换)、
分支 get/put/merge、分享查看/回写、依赖图、lint、密钥扫描、行数统计。
"""
import os, tempfile, glob, sqlite3

TMP = tempfile.mkdtemp(prefix="enc_")
os.environ["DOC_DATA_DIR"] = TMP
os.environ["REGISTRY_DB_PATH"] = os.path.join(TMP, "registry.db")
os.environ["DOC_DB_PATH"] = os.path.join(TMP, "legacy_unused.db")
os.environ["AUTH_ALLOW_REGISTER"] = "true"
os.environ["DOC_ATREST_ENCRYPTION"] = "1"
os.environ["DOC_ATREST_KEY"] = "test-at-rest-key-please-rotate"

from fastapi.testclient import TestClient
import main  # noqa: E402


def _raw_content(doc_id: str) -> str:
    """直查用户 SQLite 库，绕过应用层解密，验证落库形态。"""
    for dbf in glob.glob(os.path.join(TMP, "users", "*", "docs.db")):
        con = sqlite3.connect(dbf)
        try:
            row = con.execute("SELECT content FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
            if row:
                return row[0] or ""
        finally:
            con.close()
    return ""


with TestClient(main.app) as c:
    c.post("/api/auth/register", json={"username": "enc", "password": "p@ssw0rd"})
    t = c.post("/api/auth/login", json={"username": "enc", "password": "p@ssw0rd"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}

    # 创建 → 直查库应为密文，API 返回明文
    did = c.post("/api/docs", headers=h, json={"title": "T", "content": "hello needle world"}).json()["doc_id"]
    raw = _raw_content(did)
    assert raw.startswith("atrestv1:"), f"库内应为密文，实际: {raw[:40]}"
    assert "needle" not in raw, "明文不应出现在库内"
    d = c.get(f"/api/docs/{did}", headers=h).json()
    assert d["content"] == "hello needle world", d

    # 更新 → 新内容明文不落库、API 返回明文
    c.put(f"/api/docs/{did}", headers=h, json={"content": "hello BIGNEEDLE v2", "title": "T"})
    raw2 = _raw_content(did)
    assert "BIGNEEDLE" not in raw2, "更新后明文不应落库"
    d2 = c.get(f"/api/docs/{did}", headers=h).json()
    assert "BIGNEEDLE" in d2["content"], d2

    # 版本快照：列表预览 + 单版本读取均明文
    vers = c.get(f"/api/docs/{did}/versions", headers=h).json()["items"]
    assert vers, vers
    vid = vers[0]["id"]
    vdoc = c.get(f"/api/docs/{did}/versions/{vid}", headers=h).json()
    assert "needle" in vdoc["content"] or "BIGNEEDLE" in vdoc["content"], vdoc

    # 建议接受（in-place 替换，基于明文定位）
    sg = c.post(f"/api/docs/{did}/suggestions", headers=h,
                json={"original_text": "BIGNEEDLE", "proposed_text": "GIANTNEEDLE", "comment": "x"}).json()
    dec = c.put(f"/api/docs/{did}/suggestions/{sg['id']}?status=accepted", headers=h).json()
    assert dec["replaced"], dec
    d3 = c.get(f"/api/docs/{did}", headers=h).json()
    assert "GIANTNEEDLE" in d3["content"], d3

    # transclusion：被包含文档内容明文展开
    src = c.post("/api/docs", headers=h, json={"title": "src", "content": "INCLUDED-BODY"}).json()["doc_id"]
    c.put(f"/api/docs/{did}", headers=h, json={"content": f"!include[[{src}]]", "title": "T"})
    res = c.get(f"/api/docs/{did}/resolved", headers=h).json()
    assert "INCLUDED-BODY" in res["content"], res

    # 分支 get/put/merge（head_content 加密、API 明文、合并结果明文）
    br = c.post(f"/api/docs/{did}/branches", headers=h).json()
    bid = br["branch_id"]
    c.put(f"/api/docs/{did}/branches/{bid}", headers=h, json={"head_content": "BRANCHLINE extra"})
    bg = c.get(f"/api/docs/{did}/branches/{bid}", headers=h).json()
    assert "BRANCHLINE" in bg["head_content"], bg
    mg = c.post(f"/api/docs/{did}/branches/{bid}/merge", headers=h).json()
    assert mg["merged"] and not mg["conflict"], mg
    d4 = c.get(f"/api/docs/{did}", headers=h).json()
    assert "BRANCHLINE" in d4["content"], d4

    # lint / scan-secrets / 行数统计 不报错（基于明文）
    lint = c.post(f"/api/docs/{did}/lint", headers=h).json()
    assert "findings" in lint, lint
    lines = c.get(f"/api/docs/{did}/analytics", headers=h).json()
    assert "total_lines" in lines, lines

    # 分享查看（content 明文）
    c.post(f"/api/docs/{did}/share", headers=h, json={"mode": "readonly"})
    sc = c.get(f"/api/docs/{did}", headers=h).json()
    # 取 share_code（get_doc 返回 share_code）
    code = sc.get("share_code")
    if code:
        sd = c.get(f"/api/share/{code}").json()
        assert "BRANCHLINE" in sd["content"], sd

print("ALL PASSED")
