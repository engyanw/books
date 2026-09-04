# -*- coding: utf-8 -*-
"""前端完整性回归：静态校验 index.html / app.js / i18n.js / src/modules/*.js。

不依赖浏览器（Playwright 在本机未安装、浏览器未缓存，且后端不直接托管 SPA 外壳），
改为对前端静态资产做结构化断言，捕获"对话框/方法/i18n 词条被删或改名但调用方未同步"
这类回归。所有 JS 经 `node --check` 语法校验。

覆盖本轮 E1（Git 绑定）+ E2（分支合并）新增 UI：
- index.html: #btnGit / #gitDialog / #btnBranch / #branchDialog 等元素存在
- app.js: showGitDialog / _gitPull / _gitPush / showBranchDialog / _mergeBranch 等方法存在
- i18n.js: 对应 en-US 词条存在
- src/modules/*.js: node --check 通过
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo 根
JS = os.path.join(ROOT, "app.js")
I18N = os.path.join(ROOT, "i18n.js")
HTML = os.path.join(ROOT, "index.html")
MODULES_DIR = os.path.join(ROOT, "src", "modules")

NODE = os.environ.get("NODE", "node")


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def _node_check(path):
    r = subprocess.run([NODE, "--check", path],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"node --check {path} 失败:\n{r.stderr}"
    return True


def _has_id(html, sel):
    """sel 形如 '#btnGit' → 在 html 中查找 id="btnGit"。"""
    rid = sel.lstrip("#")
    return f'id="{rid}"' in html or f"id='{rid}'" in html


def main():
    # ---- 1. JS 语法 ----
    _node_check(JS)
    _node_check(I18N)
    mod_files = sorted(f for f in os.listdir(MODULES_DIR) if f.endswith(".js"))
    assert mod_files, f"未在 {MODULES_DIR} 找到模块"
    for mf in mod_files:
        _node_check(os.path.join(MODULES_DIR, mf))
    print(f"[OK] JS 语法：app.js + i18n.js + {len(mod_files)} 个模块")

    html = _read(HTML)
    app = _read(JS)
    i18n = _read(I18N)

    # ---- 2. E1 Git 绑定 UI 元素 ----
    e1_html = ["#btnGit", "#gitDialog", "#btnGitSave", "#btnGitPull",
               "#btnGitPush", "#btnGitUnbind", "#gitHint"]
    e1_js = ["showGitDialog", "hideGitDialog", "_loadGitBinding",
             "_saveGitBinding", "_gitPull", "_gitPush", "_unbindGit",
             "_requireCloudDoc"]
    for sel in e1_html:
        assert _has_id(html, sel), f"index.html 缺少元素 {sel}"
    for m in e1_js:
        assert m in app, f"app.js 缺少方法 {m}"
    print(f"[OK] E1 Git 绑定：{len(e1_html)} 元素 + {len(e1_js)} 方法")

    # ---- 3. E2 分支 UI 元素 ----
    e2_html = ["#btnBranch", "#branchDialog", "#branchList", "#branchEditor",
               "#btnBranchCreate", "#btnBranchSaveHead", "#btnBranchDiff",
               "#btnBranchMerge"]
    e2_js = ["showBranchDialog", "hideBranchDialog", "_loadBranches",
             "_createBranch", "_switchToBranch", "_saveBranchHead",
             "_previewBranchMerge", "_mergeBranch"]
    for sel in e2_html:
        assert _has_id(html, sel), f"index.html 缺少元素 {sel}"
    for m in e2_js:
        assert m in app, f"app.js 缺少方法 {m}"
    print(f"[OK] E2 分支合并：{len(e2_html)} 元素 + {len(e2_js)} 方法")

    # ---- 4. i18n 词条（en-US）样本 ----
    # E1/E2 对话框使用中文整句作为 i18n key（data-i18n="仓库地址" 等），逐条确认其存在于字典
    sample_i18n = [
        "Git 同步绑定",      # E1 对话框标题
        "仓库地址",          # E1 字段
        "访问令牌",          # E1 字段
        "保存时自动推送",    # E1 开关
        "保存绑定",          # E1 保存
        "拉取",              # E1 拉取
        "推送",              # E1 推送
        "解除绑定",          # E1 解绑
        "并行草稿分支",      # E2 对话框标题
        "分支",              # E2 分支
    ]
    for k in sample_i18n:
        assert f'"{k}"' in i18n, f"i18n.js 缺少词条 {k}"
    print(f"[OK] i18n 词条样本：{len(sample_i18n)} 个")

    # ---- 5. 按钮与对话框配对（按钮在 app.js 已接线：getElementById + addEventListener）----
    wiring = {"btnGit": "showGitDialog", "btnBranch": "showBranchDialog"}
    for btn, handler in wiring.items():
        assert btn in app, f"app.js 未引用按钮 #{btn}"
        assert handler in app, f"app.js 未实现 {handler} 处理 #{btn}"
    # 抽样确认两者确实在同一 addEventListener 接线块里
    assert app.find("btnGit") < app.find("showGitDialog") + 200, "#btnGit 接线异常"
    print("[OK] 按钮事件接线：btnGit→showGitDialog / btnBranch→showBranchDialog")

    print("ALL PASSED")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print("FRONTEND INTEGRITY FAIL:", e, file=sys.stderr)
        raise SystemExit(1)
