"""后端配置常量：环境变量 + 语言映射 + 日志。"""
import logging
import os
import secrets
from pathlib import Path

# ==================== 配置常量（UPPER_CASE）====================
JUDGE0_API_BASE = os.environ.get("JUDGE0_API_BASE", "https://ce.judge0.com")
SANDBOX_API_TOKEN = os.environ.get("SANDBOX_API_TOKEN", "")
JUDGE0_SUBMIT_TIMEOUT = float(os.environ.get("JUDGE0_SUBMIT_TIMEOUT", "30"))
JUDGE0_POLL_TIMEOUT = float(os.environ.get("JUDGE0_POLL_TIMEOUT", "30"))
JUDGE0_POLL_INTERVAL = float(os.environ.get("JUDGE0_POLL_INTERVAL", "0.3"))
MAX_STDIN_BYTES = int(os.environ.get("MAX_STDIN_BYTES", str(64 * 1024)))
MAX_SOURCE_BYTES = int(os.environ.get("MAX_SOURCE_BYTES", str(256 * 1024)))

# 安全配置
API_TOKEN = os.environ.get("API_TOKEN", "")
# SCIM 2.0 入站同步专用令牌（企业 IdP 推送用户/组）。留空则仅接受管理员 API Token。
SCIM_TOKEN = os.environ.get("SCIM_TOKEN", "")
# 应用层 IP 白/黑名单（逗号分隔的 IP 或 CIDR）。白名单非空时仅放行命中项；黑名单优先拒绝。
IP_ALLOWLIST = [s.strip() for s in os.environ.get("IP_ALLOWLIST", "").split(",") if s.strip()]
IP_BLOCKLIST = [s.strip() for s in os.environ.get("IP_BLOCKLIST", "").split(",") if s.strip()]
# 健康探针路径始终豁免 IP 过滤（容器编排需要）
IP_FILTER_EXEMPT_PATHS = ("/health", "/ready", "/metrics")
CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "")
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "30"))
RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"
# D5：多实例部署下 Redis 必需开关。设 1 表示"我跑多实例，限流必须经 Redis 共享计数"，
# 此时若未配 REDIS_URL，限流会退化为进程内计数并显式告警（而非静默放大为 N×实例）。
REDIS_REQUIRED = os.environ.get("REDIS_REQUIRED", "0") == "1"

# PlantUML 代理配置
PLANTUML_SERVER_URL = os.environ.get("PLANTUML_SERVER_URL", "https://www.plantuml.com/plantuml")
PLANTUML_PROXY_ENABLED = os.environ.get("PLANTUML_PROXY_ENABLED", "true").lower() == "true"
PLANTUML_LOCAL_ENABLED = os.environ.get("PLANTUML_LOCAL_ENABLED", "true").lower() == "true"
PLANTUML_JAR_PATH = os.environ.get("PLANTUML_JAR_PATH", "")
PLANTUML_COMMAND = os.environ.get("PLANTUML_COMMAND", "")

# 导出/静态站点的图表与数学渲染
# Mermaid CLI（mmdc）可选：配置后服务端预渲染 mermaid→内联 SVG（离线友好）；未配置则注入客户端 mermaid.js 运行时渲染
MERMAID_MMDC_COMMAND = os.environ.get("MERMAID_MMDC_COMMAND", "")  # 例: "npx -y @mermaid-js/mermaid-cli"
MERMAID_CDN = os.environ.get("MERMAID_CDN", "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js")
# KaTeX：数学公式客户端自动渲染（$...$ 行内、$$...$$ 块级）；CDN 可替换为本地静态
KATEX_CSS_CDN = os.environ.get("KATEX_CSS_CDN", "https://cdn.jsdelivr.net/npm/katex@0.16/dist/katex.min.css")
KATEX_JS_CDN = os.environ.get("KATEX_JS_CDN", "https://cdn.jsdelivr.net/npm/katex@0.16/dist/katex.min.js")
KATEX_AUTORENDER_CDN = os.environ.get("KATEX_AUTORENDER_CDN", "https://cdn.jsdelivr.net/npm/katex@0.16/dist/contrib/auto-render.min.js")

# 图片代理配置
IMAGE_PROXY_ENABLED = os.environ.get("IMAGE_PROXY_ENABLED", "true").lower() == "true"
IMAGE_PROXY_MAX_BYTES = int(os.environ.get("IMAGE_PROXY_MAX_BYTES", str(20 * 1024 * 1024)))
# 是否允许代理到内网/回环地址（自建内网部署、需渲染内网图片时设为 true；公开服务保持 false 防 SSRF）
IMAGE_PROXY_ALLOW_PRIVATE = os.environ.get("IMAGE_PROXY_ALLOW_PRIVATE", "false").lower() == "true"

# 文档同步/分享配置
DOC_DB_PATH = os.environ.get("DOC_DB_PATH", str(Path(__file__).parent / "docs.db"))
SHARE_CODE_LENGTH = int(os.environ.get("SHARE_CODE_LENGTH", "8"))
SHARE_MAX_AGE_DAYS = int(os.environ.get("SHARE_MAX_AGE_DAYS", "30"))
DOC_MAX_CONTENT_BYTES = int(os.environ.get("DOC_MAX_CONTENT_BYTES", str(20 * 1024 * 1024)))
# C4：每文档版本快照保留上限（超出按 created_at DESC 轮转删除最旧）
MAX_VERSIONS_PER_DOC = int(os.environ.get("MAX_VERSIONS_PER_DOC", "50"))

# 每用户数据目录（每用户库 data/users/<uid>/docs.db、每用户配置 data/configs/<uid>.json 均落此）
DOC_DATA_DIR = os.environ.get("DOC_DATA_DIR", str(Path(__file__).parent / "data"))
# 共享注册库（users 表 + shares 路由表），用于跨用户查找（登录鉴权、分享码路由）
REGISTRY_DB_PATH = os.environ.get("REGISTRY_DB_PATH", str(Path(DOC_DATA_DIR) / "registry.db"))

# 定时备份：内置调度循环（无需外部 cron）。BACKUP_INTERVAL_HOURS=0 关闭。
BACKUP_DIR = os.environ.get("BACKUP_DIR", str(Path(DOC_DATA_DIR) / "_backups"))
BACKUP_INTERVAL_HOURS = float(os.environ.get("BACKUP_INTERVAL_HOURS", "0"))
BACKUP_KEEP = int(os.environ.get("BACKUP_KEEP", "14"))
# 自动恢复演练周期（小时，0=关闭）。演练只校验备份完整性，不覆盖运行数据。
BACKUP_DRILL_INTERVAL_HOURS = float(os.environ.get("BACKUP_DRILL_INTERVAL_HOURS", "0"))
# P2-13 DR 深度：跨区复制目标目录（异步归档副本）。空=不启用本地副本复制。
REPLICA_DIR = os.environ.get("REPLICA_DIR", "")
# RPO 告警阈值（秒）：距上次成功备份超过该值时，/replica/status 标记 stale。
DR_RPO_ALERT_SECONDS = int(os.environ.get("DR_RPO_ALERT_SECONDS", "900"))
# E5：断链检测扫描周期（小时，0=关闭）。后台重建各文档的链接图并标记断链。
LINK_CHECK_INTERVAL_HOURS = float(os.environ.get("LINK_CHECK_INTERVAL_HOURS", "0"))
# 每用户库连接池上限
USER_DB_POOL_SIZE = int(os.environ.get("USER_DB_POOL_SIZE", "10"))
# 连接池 LRU 上限：同时在内存中缓存的不同用户/团队连接池数量（防止用户数膨胀导致连接无界）。
MAX_USER_POOLS = int(os.environ.get("MAX_USER_POOLS", "256"))
MAX_TEAM_POOLS = int(os.environ.get("MAX_TEAM_POOLS", "128"))
# 全局空闲连接总数兜底上限（跨所有用户/团队池）。超出时按 LRU 强制淘汰。
MAX_TOTAL_IDLE_CONNECTIONS = int(os.environ.get("MAX_TOTAL_IDLE_CONNECTIONS", "2048"))
# C1 协同增量持久化：单个 room 累积增量数超此阈值时触发"请求客户端推全量快照"以合并/GC。
# 距上次快照超过 COLLAB_SNAPSHOT_STALE_SEC 秒且有在线连接时同样触发。
COLLAB_UPDATE_GC_THRESHOLD = int(os.environ.get("COLLAB_UPDATE_GC_THRESHOLD", "200"))
COLLAB_SNAPSHOT_STALE_SEC = int(os.environ.get("COLLAB_SNAPSHOT_STALE_SEC", "300"))
# P2-12 协同规模化：大文档/大团队保护性上限。
# 单 room 快照体积上限（字节，默认 8MB）：超限拒绝持久化，防止巨型文档拖垮 DB 与广播。
COLLAB_MAX_SNAPSHOT_BYTES = int(os.environ.get("COLLAB_MAX_SNAPSHOT_BYTES", str(8 * 1024 * 1024)))
# 单 room 增量保留上限（条数）：超限按 seq 删除最旧，限制 collab_updates 无界增长。
COLLAB_MAX_UPDATES_PER_ROOM = int(os.environ.get("COLLAB_MAX_UPDATES_PER_ROOM", "5000"))
# 单 room 在线 awareness/presence 上限：超限淘汰最久未活跃连接，防大团队广播风暴。
COLLAB_MAX_PRESENCE_PER_ROOM = int(os.environ.get("COLLAB_MAX_PRESENCE_PER_ROOM", "256"))
# 单条 awareness/cursor 负载上限（字节）：超限丢弃，防恶意/异常大 payload。
COLLAB_MAX_AWARENESS_BYTES = int(os.environ.get("COLLAB_MAX_AWARENESS_BYTES", str(64 * 1024)))
# 每用户配置文件大小上限
USER_SETTINGS_MAX_BYTES = int(os.environ.get("USER_SETTINGS_MAX_BYTES", str(256 * 1024)))

# AI 助手：后端代理转发到大模型 API 的超时（秒）。慢/本地模型可调大或设环境变量。
AI_PROXY_TIMEOUT = int(os.environ.get("AI_PROXY_TIMEOUT", "180"))
# AI 代理请求体字节上限（messages 等可能较大）
AI_PROXY_MAX_BYTES = int(os.environ.get("AI_PROXY_MAX_BYTES", str(512 * 1024)))

# AI 用量与配额（治理）：每日调用上限，0=不限。按 用户/团队 分别计。
AI_USER_DAILY_QUOTA = int(os.environ.get("AI_USER_DAILY_QUOTA", "0"))
AI_TEAM_DAILY_QUOTA = int(os.environ.get("AI_TEAM_DAILY_QUOTA", "0"))
# 模型白名单（逗号分隔），空=不限制。例：gpt-4o-mini,qwen-plus
AI_ALLOWED_MODELS = [m.strip() for m in os.environ.get("AI_ALLOWED_MODELS", "").split(",") if m.strip()]

# 文档/存储/团队配额（计量治理）：0=不限。
USER_MAX_DOCS = int(os.environ.get("USER_MAX_DOCS", "0"))
USER_MAX_STORAGE_BYTES = int(os.environ.get("USER_MAX_STORAGE_BYTES", "0"))
USER_MAX_TEAMS = int(os.environ.get("USER_MAX_TEAMS", "0"))  # 用户可创建/拥有的团队数上限
TEAM_MAX_DOCS = int(os.environ.get("TEAM_MAX_DOCS", "0"))
TEAM_MAX_STORAGE_BYTES = int(os.environ.get("TEAM_MAX_STORAGE_BYTES", "0"))
TEAM_MAX_MEMBERS = int(os.environ.get("TEAM_MAX_MEMBERS", "0"))

# 数据驻留分区：按 region 把用户/团队的文档库落到不同磁盘目录（满足数据主权/合规）。
# DATA_RESIDENCY_ENABLED=true 时启用；RESIDENCY_REGIONS=JSON {region: {"dir": "/data/eu"}}。
# 用户/团队按 RESIDENCY_DEFAULT_REGION 或显式分配落到某 region（记录于 users/teams.residency_region）。
import json as _json_mod
DATA_RESIDENCY_ENABLED = os.environ.get("DATA_RESIDENCY_ENABLED", "false").lower() == "true"
try:
    RESIDENCY_REGIONS = _json_mod.loads(os.environ.get("RESIDENCY_REGIONS", "{}"))
except Exception:
    RESIDENCY_REGIONS = {}
RESIDENCY_DEFAULT_REGION = os.environ.get("RESIDENCY_DEFAULT_REGION", "")

# P1-6 多区域边界：当前部署所在 region（仅标识，不启用 active-active 写路径）。
# 单区域（standalone/primary/replica）受支持；多区域 active-active 写路径不在此版本支持：
#   - SQLite per-user：本地文件无跨区复制，active-active 写必损坏；
#   - PG 模式：可经流式复制做读副本（读水平扩展），写仍走单一主区。
# PG_REPLICA_ROLE 标识本实例角色（""=standalone / "primary" / "replica"），仅观测，不改变写路径。
DEPLOY_REGION = os.environ.get("DEPLOY_REGION", RESIDENCY_DEFAULT_REGION or "default")
PG_REPLICA_ROLE = os.environ.get("PG_REPLICA_ROLE", "")
MULTI_REGION_ACTIVE_ACTIVE = os.environ.get("MULTI_REGION_ACTIVE_ACTIVE", "false").lower() == "true"

# 后台任务 leader 选举（多实例水平扩展时，备份/合并/SLA 等后台循环只在 leader 上运行）。
# 默认关闭（单实例：所有循环本地执行）；启用后用 Redis 或注册库行租约选主。
LEADER_ELECTION_ENABLED = os.environ.get("LEADER_ELECTION_ENABLED", "false").lower() == "true"
LEADER_LEASE_TTL_SECONDS = int(os.environ.get("LEADER_LEASE_TTL_SECONDS", "15"))
LEADER_RENEW_INTERVAL_SECONDS = int(os.environ.get("LEADER_RENEW_INTERVAL_SECONDS", "5"))
LEADER_KEY = os.environ.get("LEADER_KEY", "md2:leader")

# ── 多实例一致性约束（P1-3）──────────────────────────────────────
# SQLite per-user/per-team 模式下，请求路径写本地文件；多实例 active/active
# 若无共享文件系统则同一用户的 docs.db 会被并发写损坏。leader 选举只守护后台
# 循环，不协调请求路径。故多实例部署须满足下列任一条件，否则启动告警 + admin 标红：
#   (a) PG 单库模式（DATABASE_URL 已设，is_pg()=True）—— 推荐
#   (b) DOC_DATA_DIR_SHARED=true，声明 data 目录在网络/共享 FS 上（仍非并发安全，
#       仅作降级可用，须配文件锁；企业生产建议用 PG）
MULTI_INSTANCE_HA = os.environ.get("MULTI_INSTANCE_HA", "false").lower() == "true"  # 声明本部署是多实例 HA
DOC_DATA_DIR_SHARED = os.environ.get("DOC_DATA_DIR_SHARED", "false").lower() == "true"  # data 目录共享 FS
# 强约束：多实例 + SQLite + 非共享 → 启动即拒绝（默认 false=仅告警，不阻断，向后兼容）
MULTI_INSTANCE_STRICT = os.environ.get("MULTI_INSTANCE_STRICT", "false").lower() == "true"


# 安全响应头（CSP/HSTS/X-Frame 等）。生产环境默认启用。
SECURITY_HEADERS_ENABLED = os.environ.get("SECURITY_HEADERS_ENABLED", "true").lower() == "true"
# CSP 白名单：默认允许 self + 必要 CDN（monaco/mermaid/highlight/echarts/codemirror）。
# 生产环境应通过 CSP_DIRECTIVES 显式收紧到实际使用的 CDN。
CSP_DIRECTIVES = os.environ.get(
    "CSP_DIRECTIVES",
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://unpkg.com https://cdn.bootcdn.net; "
    "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://unpkg.com; "
    "img-src 'self' data: blob: https: http:; "
    "font-src 'self' data: https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
    "connect-src 'self' ws: wss: https: http:; "
    "media-src 'self' blob: data: https:; "
    "frame-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self';",
)
# HSTS：仅在 HTTPS 且生产环境生效（开发环境 http 不下发 HSTS）
HSTS_MAX_AGE = int(os.environ.get("HSTS_MAX_AGE", str(31536000)))

# 多用户鉴权配置
def _load_or_create_auth_secret() -> str:
    """加载或生成持久化的 HMAC 签名密钥（未显式配置 AUTH_SECRET 时落盘，避免重启失效）。"""
    secret_file = Path(DOC_DB_PATH).parent / ".auth_secret"
    try:
        if secret_file.exists():
            v = secret_file.read_text().strip()
            if v:
                return v
    except Exception:
        pass
    v = secrets.token_hex(32)
    try:
        secret_file.write_text(v)
        # 限制文件权限（仅当前用户可读写）
        try:
            os.chmod(secret_file, 0o600)
        except Exception:
            pass
    except Exception:
        pass
    return v

AUTH_SECRET = os.environ.get("AUTH_SECRET") or _load_or_create_auth_secret()
AUTH_TOKEN_TTL = int(os.environ.get("AUTH_TOKEN_TTL", str(30 * 24 * 3600)))  # 默认 30 天（兼容旧无 typ token）
# Refresh Token：access 短 TTL + refresh 长 TTL，支持轮换。未显式配置 AUTH_ACCESS_TTL 时，
# 回退到 AUTH_TOKEN_TTL 以保持旧前端向后兼容（一次性降级为长 access）。
AUTH_ACCESS_TTL = int(os.environ.get("AUTH_ACCESS_TTL", str(AUTH_TOKEN_TTL)))  # 默认随 AUTH_TOKEN_TTL（兼容）
AUTH_REFRESH_TTL = int(os.environ.get("AUTH_REFRESH_TTL", str(30 * 24 * 3600)))  # 默认 30 天
AUTH_ALLOW_REGISTER = os.environ.get("AUTH_ALLOW_REGISTER", "true").lower() == "true"

# 企业 SSO：OIDC（授权码流程）。未配置 OIDC_ISSUER 时 SSO 端点不可用。
# 前端跳 /api/auth/oidc/login → 重定向到 IdP → 回调 /api/auth/oidc/callback 换 token+userinfo → 本地签发 token。
OIDC_ISSUER = os.environ.get("OIDC_ISSUER", "").strip()          # 如 https://idp.example.com
OIDC_CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "").strip()
OIDC_CLIENT_SECRET = os.environ.get("OIDC_CLIENT_SECRET", "").strip()
OIDC_REDIRECT_URI = os.environ.get("OIDC_REDIRECT_URI", "").strip()  # 如 https://app.example.com/api/auth/oidc/callback
OIDC_SCOPES = os.environ.get("OIDC_SCOPES", "openid profile email").strip()
# IdP 发现文档（discovery）按需获取；若 IdP 不支持 discovery，可显式覆盖：
OIDC_AUTHORIZATION_ENDPOINT = os.environ.get("OIDC_AUTHORIZATION_ENDPOINT", "").strip()
OIDC_TOKEN_ENDPOINT = os.environ.get("OIDC_TOKEN_ENDPOINT", "").strip()
OIDC_USERINFO_ENDPOINT = os.environ.get("OIDC_USERINFO_ENDPOINT", "").strip()
# 前端登录后落地页（回调成功后带 token 跳转到这里）
OIDC_FRONTEND_URL = os.environ.get("OIDC_FRONTEND_URL", "/").strip()

# 企业 SSO：SAML 2.0 SP。未配置 SAML_SP_ENTITY_ID 时端点返回 503。
# 流程：前端 GET /api/auth/saml/login → 重定向到 IdP SSO URL（带 AuthnRequest）→
# IdP POST SAMLResponse 到 /api/auth/saml/acs → 解析 NameID/属性 → 关联/创建本地用户。
SAML_SP_ENTITY_ID = os.environ.get("SAML_SP_ENTITY_ID", "").strip()       # https://app.example.com/saml/metadata
SAML_ACS_URL = os.environ.get("SAML_ACS_URL", "").strip()                   # https://app.example.com/api/auth/saml/acs
SAML_IDP_SSO_URL = os.environ.get("SAML_IDP_SSO_URL", "").strip()           # IdP 单点登录端点
SAML_IDP_ENTITY_ID = os.environ.get("SAML_IDP_ENTITY_ID", "").strip()
SAML_IDP_CERT = os.environ.get("SAML_IDP_CERT", "").strip()                 # IdP 签名证书 PEM（验签用）
# xmlsec1 二进制路径（用于签名/验签）。留空且 SAML_VERIFY_SIGNATURE=true 时无法验签。
SAML_XMLSEC1 = os.environ.get("SAML_XMLSEC1", "xmlsec1").strip()
# 是否验签。生产必须 true；测试/内网受信可设 false（dev 模式，接受未签名断言）。
SAML_VERIFY_SIGNATURE = os.environ.get("SAML_VERIFY_SIGNATURE", "true").lower() == "true"
# SAML SLO（单点登出）：IdP SingleLogoutService 端点。配置后登出会跳转到 IdP 做全局登出。
SAML_IDP_SLO_URL = os.environ.get("SAML_IDP_SLO_URL", "").strip()
# OIDC 登出后回跳页（传给 IdP end_session_endpoint 的 post_logout_redirect_uri）
OIDC_POST_LOGOUT_URL = os.environ.get("OIDC_POST_LOGOUT_URL", "").strip()

# AI 助手：每用户大模型 api_key 加密落库的主密钥。
# 优先用环境变量 AI_ENC_KEY；未设置则从 AUTH_SECRET（已持久化）派生，避免新增运维密钥。
AI_ENC_KEY = os.environ.get("AI_ENC_KEY") or AUTH_SECRET

# 文档正文静态加密（受监管多租户场景：DBA 直查库也无法读取正文）。
# 默认关闭以保持向后兼容；受监管租户置 DOC_ATREST_ENCRYPTION=1 开启。
# 密钥：优先 DOC_ATREST_KEY（Fernet 兼容 base64 或任意口令经 HKDF 派生）；
# 未设置则从 AI_ENC_KEY 派生（专用 salt/info 域隔离，不复用 AI 密文域）。
# 加密内容以 "atrestv1:" 前缀标记，支持明文/密文混合行共存与开关切换。
DOC_ATREST_ENCRYPTION = os.environ.get("DOC_ATREST_ENCRYPTION", "0") == "1"
DOC_ATREST_KEY = os.environ.get("DOC_ATREST_KEY", "")

# ── 出口 DLP（机密文档防泄露）─────────────────────────────────
# 机密（confidential）文档禁止非属主/非管理员导出、批量导出、站点构建；
# 属主/管理员导出时注入水印（用户名+时间戳）便于溯源。
DLP_BLOCK_EXPORT_CONFIDENTIAL = os.environ.get("DLP_BLOCK_EXPORT_CONFIDENTIAL", "1") == "1"
DLP_WATERMARK = os.environ.get("DLP_WATERMARK", "1") == "1"

# ── 一等公民集成连接器（Slack / Microsoft Teams）──────────────
# 配置后，关键事件（评审请求、法务保留、@mention）自动以卡片形式推送到对应渠道。
# Jira/Confluence 走通用 webhooks 表（/api/webhooks）即可，不在此耦合。
INTEGRATION_SLACK_WEBHOOK_URL = os.environ.get("INTEGRATION_SLACK_WEBHOOK_URL", "")
INTEGRATION_TEAMS_WEBHOOK_URL = os.environ.get("INTEGRATION_TEAMS_WEBHOOK_URL", "")
INTEGRATION_NOTIFY_EVENTS = set(filter(None, os.environ.get(
    "INTEGRATION_NOTIFY_EVENTS", "review,legal_hold,mention").split(",")))

# PostgreSQL 迁移（可选）：设 DATABASE_URL 则启用 PG，否则用 SQLite per-user
# 切换需同时设 DOC_DATA_DIR 指向 PG 已有数据的迁移目录（或空让 _startup 建表）
DATABASE_URL = os.environ.get("DATABASE_URL", "")  # postgresql://user:pass@host:5432/db
DB_POOL_MIN = int(os.environ.get("DB_POOL_MIN", "5"))
DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX", "20"))

# SMTP 邮件发送（Guest 邀请等；未配置则跳过发信）
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

# 每日未读通知邮件摘要：后台循环给有未读通知的用户发送汇总邮件。
# EMAIL_DIGEST_INTERVAL_SECONDS 控制扫描间隔（默认 6 小时；测试可调小）。
# 仅当配置了 SMTP_HOST/SMTP_FROM 且用户 email 非空时实际投递；否则仅统计不发。
EMAIL_DIGEST_ENABLED = os.environ.get("EMAIL_DIGEST_ENABLED", "") == "1"
EMAIL_DIGEST_INTERVAL_SECONDS = int(os.environ.get("EMAIL_DIGEST_INTERVAL_SECONDS", str(6 * 3600)))
# 单封摘要最多聚合多少条未读（避免超长邮件）；其余以"…还有 N 条"带过。
EMAIL_DIGEST_MAX_ITEMS = int(os.environ.get("EMAIL_DIGEST_MAX_ITEMS", "20"))
# 仅汇总最近多少天内的未读（防止积压历史一次性轰炸）；0=不限制。
EMAIL_DIGEST_LOOKBACK_DAYS = int(os.environ.get("EMAIL_DIGEST_LOOKBACK_DAYS", "7"))


# 审计日志留存：超过 N 天的记录自动清理（0=永久保留）。合规场景建议 365/2555 天。
AUDIT_RETENTION_DAYS = int(os.environ.get("AUDIT_RETENTION_DAYS", "0"))
# 审计日志物理不可变（WORM）：开启后在 audit_log 上安装 UPDATE/DELETE 拦截触发器，
# 任何修改/删除（含留存期清理与 re-anchor）一律被数据库层拒绝（RAISE）。满足 SOX/
# GDPR/等保/21 CFR Part 11 的"写一次读多次"不可变要求。开启时留存期清理自动跳过，
# 链式哈希链永不断裂（/api/audit/verify 始终可连续校验）。默认关闭以保留清理能力。
AUDIT_IMMUTABLE = os.environ.get("AUDIT_IMMUTABLE", "") == "1"

# 生命周期门禁+电子签名：开启后，文档 approved/published 必须经 /api/docs/{id}/sign
# 电子签名路径流转（绑定内容哈希，防事后篡改）；关闭则保留自由状态转移（向后兼容）。
LIFECYCLE_REQUIRE_SIGNATURE = os.environ.get("LIFECYCLE_REQUIRE_SIGNATURE", "0") == "1"


# 语言别名 → Judge0 language_id（基于 Judge0 CE 1.13.1）
LANGUAGE_ID_MAP = {
    "python": 71, "python3": 71, "py": 71,
    "java": 62,
    "c": 50, "cpp": 54, "c++": 54,
    "csharp": 51, "cs": 51, "c#": 51,
    "go": 60, "golang": 60,
    "ruby": 72, "rb": 72,
    "rust": 73, "rs": 73,
    "php": 68,
    "bash": 46, "sh": 46, "shell": 46,
    "typescript": 74, "ts": 74,
    "kotlin": 78, "kt": 78,
    "swift": 83,
    "scala": 81,
    "sql": 82,
    "r": 80,
    "perl": 85, "pl": 85,
    "lua": 64,
    "haskell": 61, "hs": 61,
    "clojure": 86, "clj": 86,
    "elixir": 87, "ex": 87,
    "erlang": 88, "erl": 88,
    "cobol": 77,
    "d": 84,
    "fsharp": 87, "fs": 87, "f#": 87,
    "groovy": 88,
    "objective-c": 79, "objc": 79, "obj-c": 79,
    "ocaml": 89, "ml": 89,
    "pascal": 67,
    "fortran": 59,
    "ada": 55,
    "vb": 84, "visualbasic": 84, "vb.net": 84,
}

LANGUAGE_DISPLAY_NAME = {
    71: "Python 3", 62: "Java (OpenJDK 13)",
    50: "C (GCC 9.2)", 54: "C++ (GCC 9.2)",
    51: "C# (.NET Core 3.1)", 60: "Go 1.13",
    72: "Ruby 2.7", 73: "Rust 1.40",
    68: "PHP 7.4", 46: "Bash 5.0", 74: "TypeScript 4.2",
    78: "Kotlin 1.3", 83: "Swift 5.1", 81: "Scala 2.13",
    82: "SQL (SQLite)", 80: "R 4.0", 85: "Perl 5.28",
    64: "Lua 5.3", 61: "Haskell GHC 8.6", 86: "Clojure 1.10",
    87: "Elixir 1.9", 88: "Erlang OTP 22", 77: "COBOL",
    84: "D (DMD 2.087) / VB.NET", 59: "Fortran (GFortran 9)",
    67: "Pascal (FPC 3.0)", 55: "Ada (GNAT 9.2)",
    79: "Objective-C (Clang 9)", 89: "OCaml 4.09",
}

# 日志
LOG_JSON = os.environ.get("LOG_JSON", "0") == "1"


class _JsonFormatter(logging.Formatter):
    """D3：结构化 JSON 日志格式器。每条日志一行 JSON，含时间/级别/ logger/消息及附加字段。"""

    def format(self, record: logging.LogRecord) -> str:
        import json as _json
        import time as _time
        payload = {
            "ts": _time.strftime("%Y-%m-%dT%H:%M:%S", _time.gmtime(record.created))
                   + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 合并 LogRecord 上的自定义属性（排除标准属性）
        std = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "asctime", "taskName",
        }
        for k, v in record.__dict__.items():
            if k not in std and not k.startswith("_"):
                try:
                    _json.dumps(v)
                    payload[k] = v
                except Exception:
                    payload[k] = str(v)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return _json.dumps(payload, ensure_ascii=False)


if LOG_JSON:
    _h = logging.StreamHandler()
    _h.setFormatter(_JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[_h])
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
logger = logging.getLogger("sandbox-proxy")
