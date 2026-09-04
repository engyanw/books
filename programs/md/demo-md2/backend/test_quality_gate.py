# -*- coding: utf-8 -*-
"""⑧CI 质量门禁。
- 坏代码（裸 except + 硬编码密钥）→ G2/G3 命中，退出码 1，JSON passed=false。
- 干净代码 → 全 PASS，退出码 0，passed=true。
"""
import os, tempfile, subprocess, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))

BAD_SRC = '''
def f():
    try:
        x = 1
    except:           # 裸 except → G2 error
        pass
pw = "password = 'hardcodedsupersecret123'"  # G3 命中
exec(pw)
'''
GOOD_SRC = '''
import logging
log = logging.getLogger(__name__)
def g(a=1):
    try:
        return a + 1
    except ValueError:
        log.exception("bad")
'''

CLEAN_TEST_SRC = 'print("ALL PASSED")\n'


def run_gate(root):
    env = dict(os.environ); env["QG_ROOT"] = root
    r = subprocess.run([sys.executable, os.path.join(HERE, "scripts", "quality_gate.py"), "--skip-tests"],
                       capture_output=True, env=env, timeout=120)
    out = (r.stdout + r.stderr).decode("utf-8", "replace")
    m = out.rsplit("JSON=", 1)
    rep = json.loads(m[1].strip()) if len(m) == 2 else {}
    return r.returncode, rep, out


# 1) 坏代码 → 阻断
tmp = tempfile.mkdtemp(prefix="qg_bad_")
with open(os.path.join(tmp, "bad.py"), "w") as f:
    f.write(BAD_SRC)
with open(os.path.join(tmp, "good.py"), "w") as f:
    f.write(GOOD_SRC)
rc, rep, out = run_gate(tmp)
assert rc != 0, ("坏代码应阻断", rc, out)
assert rep.get("passed") is False, rep
assert rep.get("g2_errors", 0) >= 1, ("应检出裸 except", rep)
assert rep.get("g3_secrets", 0) >= 1, ("应检出硬编码密钥", rep)
print(f"  坏代码阻断 OK: {rep}")

# 2) 干净代码 → 通过
tmp2 = tempfile.mkdtemp(prefix="qg_good_")
with open(os.path.join(tmp2, "good.py"), "w") as f:
    f.write(GOOD_SRC)
with open(os.path.join(tmp2, "test_clean.py"), "w") as f:
    f.write(CLEAN_TEST_SRC)
rc2, rep2, out2 = run_gate(tmp2)
assert rc2 == 0, ("干净代码应通过", rc2, out2)
assert rep2.get("passed") is True, rep2
assert rep2.get("g2_errors", 0) == 0 and rep2.get("g3_secrets", 0) == 0, rep2
print(f"  干净代码通过 OK: {rep2}")

# 3) 真实 backend 目录 G1-G3 通过（回归保护）
rc3, rep3, out3 = run_gate(os.path.dirname(HERE))
assert rc3 == 0, ("真实 backend G1-G3 应通过", rc3, out3)
print(f"  backend 回归通过 OK: {rep3}")

print("ALL PASSED")
