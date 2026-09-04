#!/usr/bin/env python3
"""团队文档库 → Git 仓库同步。

将团队文档导出为 .md 文件并 git commit/push。单向同步（库→Git），不做双向。
适用于 code review 文档变更、备份、CI 集成场景。

用法：
    python scripts/git_sync.py --team <team_id> --repo /repos/myteam-docs [--base-url http://localhost:8000] [--token <api_token>]

cron 示例（每小时同步）：
    0 * * * * cd /app/backend && python scripts/git_sync.py --team team-xxx --repo /repos/myteam-docs --token pat_xxx
"""
import argparse, os, sys, json, subprocess
from pathlib import Path
from urllib.request import urlopen, Request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True, help="团队 ID")
    ap.add_argument("--repo", required=True, help="Git 仓库本地路径")
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--token", required=True, help="API Token（pat_...）")
    ap.add_argument("--author", default="doc-sync-bot <noreply@localhost>")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").exists():
        subprocess.run(["git", "init"], cwd=str(repo), check=True)

    headers = {"Authorization": f"Bearer {args.token}"}
    # 拉取团队文档列表
    req = Request(f"{args.base_url}/api/teams/{args.team}/docs", headers=headers)
    items = json.loads(urlopen(req).read())["items"]

    written = 0
    for item in items:
        # 获取文档内容
        req2 = Request(f"{args.base_url}/api/teams/{args.team}/docs/{item['doc_id']}", headers=headers)
        doc = json.loads(urlopen(req2).read())
        # 文件路径：path + title
        rel_path = item.get("path", "")
        fname = item["title"]
        if not fname.endswith((".md", ".markdown", ".txt")):
            fname += ".md"
        fpath = repo / rel_path / fname if rel_path else repo / fname
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(doc.get("content", ""), encoding="utf-8")
        written += 1

    # git add + commit + push
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    diff = subprocess.run(["git", "diff", "--cached", "--stat"], cwd=str(repo), capture_output=True, text=True)
    if not diff.stdout.strip():
        print(f"无变更（{written} 篇文档已同步，仓库已是最新）")
        return
    subprocess.run(["git", "commit", "-m", f"sync {written} docs from team {args.team}", "--author", args.author],
                   cwd=str(repo), check=True)
    # push（需配置 remote；失败仅告警）
    try:
        subprocess.run(["git", "push"], cwd=str(repo), check=True, capture_output=True)
        print(f"已同步 {written} 篇文档并推送到远程")
    except subprocess.CalledProcessError as e:
        print(f"已提交 {written} 篇但推送失败（需配置 remote）：{e}", file=sys.stderr)


if __name__ == "__main__":
    main()
