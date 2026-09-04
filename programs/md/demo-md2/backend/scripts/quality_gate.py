#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI 质量门禁（自包含，仅依赖 stdlib）。
四道门：
  G1 语法编译：py_compile 全部 backend .py
  G2 AST 静态检查：裸 except、生产代码 print()、可变默认参数
  G3 密钥扫描：复用 main._SECRET_PATTERNS 扫描源码（带测试常量白名单）
  G4 测试套件：逐文件子进程跑 test_*.py，断言 ALL PASSED
任一高严重级别发现或测试失败 → 退出码非零（CI 阻断）。
用法：python scripts/quality_gate.py [--skip-tests]
输出：文本摘要 + JSON（stdout 末行 {...}）。
"""
import ast, os, sys, py_compile, subprocess, json, re, pathlib

ROOT = pathlib.Path(os.environ.get("QG_ROOT") or pathlib.Path(__file__).resolve().parent.parent)  # backend/ 或 QG_ROOT
PY_FILES = sorted(p for p in ROOT.glob("*.py") if p.name != "__pycache__")
TEST_FILES = sorted(p for p in PY_FILES if p.name.startswith("test_"))
PROD_FILES = [p for p in PY_FILES if not p.name.startswith("test_")]

# 生产代码允许 print 的白名单（脚本/种子）
PRINT_ALLOWLIST = {"seed_examples.py", "run_app.py", "dev.py", "seed_admin.py"}

# 密钥扫描白名单：测试夹具/模式定义行子串
SECRET_ALLOWLIST_SUBSTR = (
    "test-at-rest-key-please-rotate", "md2pass", "rlspass", "demo_md2",
    "_SECRET_PATTERNS", "please-rotate", "test-only", "p@ssw0rd",
    "test-", "TEST_", "test_", "DOC_ATREST_KEY",
)

SECRET_PATTERNS = [
    ("OpenAI API Key", re.compile(r"sk-[a-zA-Z0-9]{20,}")),
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub Token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36}")),
    ("Private Key", re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")),
    ("Slack Token", re.compile(r"xox[baprs]-[a-zA-Z0-9-]{10,}")),
    ("Google API Key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    # 通用密钥：要求值带引号（字符串字面量），避免匹配 secret=func() 的标识符赋值
    ("Generic Secret", re.compile(r"(?:secret|password|token|passwd|pwd)\s*[:=]\s*['\"]([a-zA-Z0-9_\-]{16,})['\"]", re.IGNORECASE)),
]

# 整文件跳过密钥扫描：扫描器自身的测试文件满是故意写入的密钥
SECRET_SCAN_SKIP_FILES = {"test_secret_scan.py", "test_quality_gate.py", "test_auto_classify.py"}


def g1_compile():
    findings = []
    for p in PY_FILES:
        try:
            py_compile.compile(str(p), doraise=True)
        except py_compile.PyCompileError as e:
            findings.append({"file": p.name, "severity": "error", "msg": str(e).splitlines()[-1] if str(e) else ""})
    return findings


def g2_ast_lint():
    findings = []
    for p in PROD_FILES:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError as e:
            findings.append({"file": p.name, "line": e.lineno or 0, "severity": "error", "rule": "syntax", "msg": str(e)})
            continue
        for node in ast.walk(tree):
            # 裸 except:
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                findings.append({"file": p.name, "line": node.lineno, "severity": "error",
                                 "rule": "bare-except", "msg": "裸 except: 应指定异常类型"})
            # 可变默认参数（list/dict/set 字面量）
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in node.args.defaults:
                    if isinstance(arg, (ast.List, ast.Dict, ast.Set)):
                        findings.append({"file": p.name, "line": node.lineno, "severity": "warn",
                                         "rule": "mutable-default", "msg": "可变默认参数（每次调用共享）"})
            # 生产代码 print（非脚本白名单）
            if p.name not in PRINT_ALLOWLIST and isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print":
                findings.append({"file": p.name, "line": node.lineno, "severity": "warn",
                                 "rule": "print-in-prod", "msg": "生产代码 print() 应改用 logger"})
    return findings


def g3_secret_scan():
    findings = []
    for p in PY_FILES:
        if p.name in SECRET_SCAN_SKIP_FILES:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if any(sub in line for sub in SECRET_ALLOWLIST_SUBSTR):
                continue
            for name, pat in SECRET_PATTERNS:
                m = pat.search(line)
                if m:
                    findings.append({"file": p.name, "line": i, "severity": "error",
                                      "rule": "secret", "type": name,
                                      "snippet": m.group()[:40]})
    return findings


def g4_tests(skip=False):
    if skip:
        return {"skipped": True, "ran": 0, "passed": 0, "failed": 0, "details": []}
    env = dict(os.environ)
    env["APP_ENV"] = "test"
    ran = passed = 0
    details = []
    for t in TEST_FILES:
        ran += 1
        r = subprocess.run([sys.executable, str(t)], capture_output=True, timeout=180, env=env)
        ok = r.returncode == 0 and b"ALL PASSED" in r.stdout
        if ok:
            passed += 1
            details.append({"file": t.name, "ok": True})
        else:
            tail = (r.stdout + r.stderr)[-400:].decode("utf-8", "replace")
            details.append({"file": t.name, "ok": False, "tail": tail})
    return {"skipped": False, "ran": ran, "passed": passed, "failed": ran - passed, "details": details}


def main():
    skip_tests = "--skip-tests" in sys.argv
    g1 = g1_compile()
    g2 = g2_ast_lint()
    g3 = g3_secret_scan()
    g4 = g4_tests(skip=skip_tests)
    errors = [f for f in g1 + g2 + g3 if f.get("severity") == "error"]
    test_failed = g4.get("failed", 0)
    passed = not errors and test_failed == 0
    print("═══ 质量门禁报告 ═══")
    print(f"G1 语法编译: {'PASS' if not g1 else 'FAIL'} ({len(g1)} 错)")
    g2_err = [f for f in g2 if f.get("severity") == "error"]
    print(f"G2 AST 检查: {'PASS' if not g2_err else 'FAIL'} ({len(g2_err)} 错, {len(g2)-len(g2_err)} 警)")
    print(f"G3 密钥扫描: {'PASS' if not g3 else 'FAIL'} ({len(g3)} 命中)")
    if not g4.get("skipped"):
        print(f"G4 测试套件: {'PASS' if not test_failed else 'FAIL'} ({g4['passed']}/{g4['ran']})")
    else:
        print("G4 测试套件: SKIPPED")
    for f in g1 + g2 + g3:
        print(f"  · [{f.get('severity')}] {f.get('file')}:{f.get('line', '')} {f.get('rule','')} {f.get('msg','')}{f.get('snippet','')}")
    for d in g4.get("details", []):
        if not d.get("ok"):
            print(f"  · [test] {d['file']}\n{d.get('tail','')}")
    report = {"passed": passed, "g1_errors": len(g1), "g2_errors": len(g2_err), "g2_warns": len(g2) - len(g2_err),
              "g3_secrets": len(g3), "g4_ran": g4.get("ran", 0), "g4_failed": test_failed}
    print("JSON=" + json.dumps(report, ensure_ascii=False))
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
