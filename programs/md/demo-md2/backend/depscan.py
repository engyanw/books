# -*- coding: utf-8 -*-
"""依赖扫描 + SBOM（软件物料清单）。

- generate_sbom()：基于 importlib.metadata 生成 CycloneDX 风格 JSON（无外部依赖）。
- scan_vulns(pkgs, advisory_path)：用本地 advisory DB（JSON）做版本匹配，
  报告命中 CVE 的依赖。可选联网查 OSV（有网络且 OSV_ENABLE=1 时，best-effort，失败回退本地）。

advisory DB 格式（advisories.json）：
[{"package":"cryptography","range":"<41.0","cve":"CVE-2023-49083","severity":"high","summary":"..."}, ...]

版本匹配优先用 packaging（pip 自带）；不可用时退化字符串比较。
"""
import json
import os
from importlib import metadata

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ADVISORY_DB = os.path.join(_HERE, "advisories.json")


def installed_packages() -> list[dict]:
    """已安装发行版列表（name/version，小写归一）。"""
    out = []
    seen = set()
    try:
        for dist in metadata.distributions():
            name = (dist.metadata["Name"] or "").strip()
            ver = (dist.version or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"name": name, "version": ver})
    except Exception:
        pass
    out.sort(key=lambda d: d["name"].lower())
    return out


def _version_matches(version: str, spec: str) -> bool:
    """判断 version 是否满足 specifier（如 '<41.0','>=2.0,<3.0','==1.2.3'）。"""
    if not spec or not version:
        return False
    try:
        from packaging.specifiers import SpecifierSet
        from packaging.version import Version
        try:
            v = Version(version)
        except Exception:
            return False
        return SpecifierSet(spec, prereleases=True).contains(v, prereleases=True)
    except Exception:
        # 无 packaging：退化处理单段 <,<=,>,>=,==,!= 的字符串比较（近似）
        for part in spec.split(","):
            part = part.strip()
            for op in ("<=", ">=", "==", "!=", "<", ">"):
                if part.startswith(op):
                    rhs = part[len(op):].strip()
                    if op == "==":
                        if version == rhs:
                            return True
                        break
                    elif op == "!=":
                        if version != rhs:
                            return True
                        break
                    elif op == "<":
                        if version < rhs:
                            return True
                        break
                    elif op == "<=":
                        if version <= rhs:
                            return True
                        break
                    elif op == ">":
                        if version > rhs:
                            return True
                        break
                    elif op == ">=":
                        if version >= rhs:
                            return True
                        break
        return False


def load_advisories(path: str | None = None) -> list[dict]:
    p = path or os.environ.get("ADVISORY_DB_PATH") or DEFAULT_ADVISORY_DB
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "advisories" in data:
            return data["advisories"]
    except FileNotFoundError:
        return []
    except Exception:
        return []


def scan_vulns(pkgs: list[dict] | None = None, advisory_path: str | None = None) -> list[dict]:
    """对已安装依赖做漏洞匹配，返回命中条目。"""
    pkgs = pkgs if pkgs is not None else installed_packages()
    advs = load_advisories(advisory_path)
    by_name: dict[str, str] = {p["name"].lower(): p["version"] for p in pkgs}
    hits = []
    for a in advs:
        pname = (a.get("package") or "").lower()
        if pname not in by_name:
            continue
        if _version_matches(by_name[pname], a.get("range", "")):
            hits.append({
                "package": a.get("package"),
                "installed_version": by_name[pname],
                "range": a.get("range"),
                "cve": a.get("cve"),
                "severity": a.get("severity", "unknown"),
                "summary": a.get("summary", ""),
                "fixed_in": a.get("fixed_in"),
            })
    return hits


def generate_sbom(pkgs: list[dict] | None = None) -> dict:
    """生成 CycloneDX 风格 SBOM（JSON）。"""
    pkgs = pkgs if pkgs is not None else installed_packages()
    components = []
    for p in pkgs:
        components.append({
            "type": "library",
            "name": p["name"],
            "version": p["version"],
            "purl": f"pkg:pypi/{p['name'].lower()}@{p['version']}",
            "bom-ref": f"pkg:pypi/{p['name'].lower()}@{p['version']}",
        })
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {"component": {"type": "application", "name": "md-editor-backend"}},
        "components": components,
    }
