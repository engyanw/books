# -*- coding: utf-8 -*-
"""合规框架控制项 → 系统功能映射目录（SOC2 / ISO 27001 / GDPR）。

企业采购常要"控制项 X 由哪条审计/哪个端点满足"的对照。本目录以代码形式固化，
经 GET /api/admin/compliance/framework 导出 JSON / CSV，便于证据包与合规对话。
字段：
  control: 控制项 ID（如 SOC2 CC6.1 / ISO A.9.4.3 / GDPR Art.32）
  title: 控制项标题
  evidence: 系统侧证据点（端点/表/审计事件/配置）
  config: 相关配置开关（可选）
  notes: 说明
"""

# SOC 2（AICPA Trust Services Criteria）
SOC2 = [
    {"control": "CC6.1", "title": "逻辑与物理访问控制",
     "evidence": ["鉴权 _require_user / _api_token_user", "2FA TOTP /api/auth/totp/*", "SAML /api/auth/saml/*", "OIDC /api/auth/oidc/*", "IP 白/黑名单中间件", "per-doc ACL /api/docs/{id}/acl"],
     "config": ["IP_ALLOWLIST", "IP_BLOCKLIST"]},
    {"control": "CC6.2", "title": "传输与认证",
     "evidence": ["Bearer token + refresh 轮换 /api/auth/refresh", "revoked_tokens 吊销", "sessions /api/sessions"],
     "config": ["AUTH_ACCESS_TTL", "AUTH_REFRESH_TTL"]},
    {"control": "CC7.1", "title": "系统监控与异常检测",
     "evidence": ["/metrics RED 指标", "/ready 就绪探针", "audit_log /api/audit", "Sentry 集成"],
     "config": ["SENTRY_DSN", "OTEL_EXPORTER_OTLP_ENDPOINT"]},
    {"control": "CC7.2", "title": "事件响应与变更追踪",
     "evidence": ["审计事件 _audit（全量写）", "/api/admin/audit/export", "版本快照 doc_versions", "行级 diff /diff/{v1}/{v2}"],
     "config": ["AUDIT_RETENTION_DAYS"]},
    {"control": "CC7.3", "title": "数据备份与恢复",
     "evidence": ["/api/admin/backup + restore", "定时备份 _backup_loop", "恢复演练 _backup_drill_loop", "DR 副本 /api/admin/replica/*", "PITR /api/admin/backup/pitr"],
     "config": ["BACKUP_INTERVAL_HOURS", "BACKUP_DRILL_INTERVAL_HOURS"]},
    {"control": "CC9.1", "title": "容量与可用性",
     "evidence": ["连接池 LRU _get_db/_get_team_db", "leader 选举 _leader_loop", "多实例一致性 /api/admin/storage-mode", "leader 选举 /api/admin/leader"],
     "config": ["MAX_USER_POOLS", "LEADER_ELECTION_ENABLED"]},
    {"control": "CC6.7", "title": "数据流转与边界（DLP）",
     "evidence": ["数据分级 documents.classification", "机密禁公开分享", "出口 DLP 守卫 _doc_egress_guard", "密钥扫描 /api/docs/{id}/scan-secrets"],
     "config": ["DLP_BLOCK_EXPORT_CONFIDENTIAL", "DLP_WATERMARK"]},
]

# ISO/IEC 27001:2022 Annex A
ISO27001 = [
    {"control": "A.5.15", "title": "访问分级",
     "evidence": ["角色矩阵 _DEFAULT_ROLE_MATRIX", "团队角色 /api/teams/{tid}/roles", "per-doc ACL"],
     "config": []},
    {"control": "A.5.23", "title": "云服务信息传输",
     "evidence": ["PG/SQLite 双模式", "数据驻留分区 /api/admin/residency", "静态加密 _doc_atrest_encrypt"],
     "config": ["DOC_ATREST_ENCRYPTION", "DATA_RESIDENCY_ENABLED"]},
    {"control": "A.5.30", "title": "ICT 应急与冗余",
     "evidence": ["/api/admin/backup", "DR 副本", "leader 选举"],
     "config": []},
    {"control": "A.7.5", "title": "安全开发生命周期",
     "evidence": ["CI 质量门禁 scripts/quality_gate.py", "依赖扫描 /api/admin/deps/*", "SBOM /api/admin/sbom", "密钥扫描"],
     "config": []},
    {"control": "A.8.5", "title": "安全身份认证",
     "evidence": ["SCIM /api/scim/v2/*", "SAML / OIDC", "refresh token 轮换", "2FA"],
     "config": []},
    {"control": "A.8.12", "title": "数据泄露防护",
     "evidence": ["分级 DLP", "出口守卫 _doc_egress_guard", "水印 DLP_WATERMARK"],
     "config": ["DLP_BLOCK_EXPORT_CONFIDENTIAL"]},
    {"control": "A.8.18", "title": "隐私与 PII 保护",
     "evidence": ["GDPR 注销 /api/account?mode=anonymize", "eDiscovery /api/admin/ediscovery/export", "法务保留 /api/admin/legal-holds"],
     "config": []},
]

# GDPR
GDPR = [
    {"control": "Art.6", "title": "合法性基础与同意",
     "evidence": ["审计 _audit 全量记录操作来源", "访客邀请 /api/guests/* 显式授权"],
     "config": []},
    {"control": "Art.17", "title": "被遗忘权",
     "evidence": ["DELETE /api/account（删除/匿名化）", "回收站 /api/trash"],
     "config": []},
    {"control": "Art.20", "title": "数据可携权",
     "evidence": ["/api/account/export", "bulk-export /api/docs/bulk-export.zip"],
     "config": []},
    {"control": "Art.25", "title": "默认隐私设计",
     "evidence": ["per-user SQLite 物理隔离", "per-doc ACL 默认拒绝", "机密禁公开分享"],
     "config": []},
    {"control": "Art.32", "title": "处理安全",
     "evidence": ["静态加密 Fernet+HKDF", "AI key 加密 _ai_encrypt", "传输 TLS（部署层）"],
     "config": ["DOC_ATREST_ENCRYPTION", "AI_ENC_KEY"]},
    {"control": "Art.33/34", "title": "数据泄露通知",
     "evidence": ["审计 + Sentry + /metrics", "法务保留", "eDiscovery 导出"],
     "config": []},
    {"control": "Art.5(2)", "title": "可追溯与问责",
     "evidence": ["audit_log /api/audit/verify（完整性校验）", "法务保留阻断删除"],
     "config": ["LIFECYCLE_REQUIRE_SIGNATURE"]},
]

FRAMEWORKS = {
    "SOC2": {"name": "SOC 2 (TSC)", "controls": SOC2},
    "ISO27001": {"name": "ISO/IEC 27001:2022 Annex A", "controls": ISO27001},
    "GDPR": {"name": "GDPR", "controls": GDPR},
}


def to_csv() -> str:
    import io, csv
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["framework", "control", "title", "evidence", "config"])
    for fk, fv in FRAMEWORKS.items():
        for c in fv["controls"]:
            w.writerow([fk, c["control"], c["title"], "; ".join(c["evidence"]), "; ".join(c["config"])])
    return buf.getvalue()


if __name__ == "__main__":
    import json, sys
    json.dump(FRAMEWORKS, sys.stdout, ensure_ascii=False, indent=2)
