# -*- coding: utf-8 -*-
"""#7 Alertmanager 路由配置 回归。

验证 deploy/observability/alertmanager.yml 的路由契约：
  - critical → oncall-pg（PagerDuty，group_wait=0s，立即）
  - warning → slack-mdocs
  - leader 类 warning → slack-ops
  - inhibit：critical 在场抑制同源 warning
  - 占位符密钥未硬编码明文
"""
import pathlib, sys
import yaml

AM = pathlib.Path(__file__).resolve().parent.parent / "deploy" / "observability" / "alertmanager.yml"
assert AM.is_file(), f"alertmanager.yml 缺失：{AM}"
d = yaml.safe_load(AM.read_text(encoding="utf-8"))

# 结构骨架
assert "route" in d and "receivers" in d and "inhibit_rules" in d, d.keys()
r = d["route"]
assert r["receiver"] == "slack-mdocs", r["receiver"]  # 默认接收方
assert "group_by" in r and "group_wait" in r and "repeat_interval" in r

routes = r["routes"]
by_recv = {x["receiver"]: x for x in routes}

# 1) critical → PagerDuty oncall，立即发出
crit = by_recv["oncall-pg"]
assert any('severity="critical"' in m for m in crit["matchers"]), crit
assert crit["group_wait"] == "0s", crit  # critical 不等聚合
assert crit["repeat_interval"] == "1h", crit
assert crit.get("continue") is False, crit

# 2) warning → slack-mdocs
warn = by_recv["slack-mdocs"]
assert any('severity="warning"' in m for m in warn["matchers"]), warn

# 3) leader 类 warning → slack-ops（独立频道）
ops = by_recv["slack-ops"]
assert any('severity="warning"' in m for m in ops["matchers"]), ops
assert any('alertname=~"MdNoLeader|MdLeaderFlap"' in m for m in ops["matchers"]), ops

# 4) receivers 通道类型正确
recv = {x["name"]: x for x in d["receivers"]}
assert "pagerduty_configs" in recv["oncall-pg"][0] if isinstance(recv["oncall-pg"], list) else "pagerduty_configs" in recv["oncall-pg"], "oncall-pg 需 PagerDuty"
# 兼容两种结构（name 顶层 vs list）
def cfg_kind(name, kind):
    obj = recv[name]
    # 对象形态：{name, kind_configs:[...]}
    return kind + "_configs" in obj
assert cfg_kind("oncall-pg", "pagerduty"), "oncall-pg 必须 pagerduty_configs"
assert cfg_kind("slack-mdocs", "slack"), "slack-mdocs 必须 slack_configs"
assert cfg_kind("slack-ops", "slack"), "slack-ops 必须 slack_configs"

# 5) send_resolved=true（恢复通知）
assert recv["oncall-pg"]["pagerduty_configs"][0]["send_resolved"] is True
assert recv["slack-mdocs"]["slack_configs"][0]["send_resolved"] is True

# 6) 抑制规则：critical 抑制同源 warning（equal alertname+team）
inh = d["inhibit_rules"]
assert any(
    any('severity="critical"' in m for m in ir.get("source_matchers", [])) and
    any('severity="warning"' in m for m in ir.get("target_matchers", [])) and
    set(ir.get("equal", [])) >= {"alertname", "team"}
    for ir in inh
), inh

# 7) 密钥占位符化（无明文 webhook/routing key）
raw = AM.read_text(encoding="utf-8")
assert "hooks.slack.com" not in raw, "Slack webhook 明文出现在配置中"
assert "<SECRET:" in raw, "密钥应占位符化"

print("ALL PASSED")
