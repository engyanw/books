# md-docs 后端

FastAPI 单体，承载 **259 路由** + 全部业务逻辑 + 后台循环。工作目录 `backend/`。架构总览见 [../ARCHITECTURE.md](../ARCHITECTURE.md)。

## 模块

| 模块 | 行数 | 职责 |
|------|------|------|
| `main.py` | 12622 | 路由、业务、数据库、后台循环、鉴权、协同（259 路由） |
| `config.py` | 402 | 全部配置常量（env 读取 + 默认值 + 语言映射） |
| `pg_adapter.py` | 325 | PostgreSQL 连接池适配，封装 SQLite/PG 双方言 |
| `taskqueue.py` | 245 | 后台任务队列 |
| `seed_examples.py` | 357 | 内置示例文档与场景模板种子 |
| `scripts/backup.py` | 253 | 备份/恢复/PITR 工具 |
| `depscan.py` | 144 | 依赖扫描与 SBOM |
| `attach_index.py` | 135 | 附件文本抽取（docx/xlsx/pptx/pdf/txt）+ FTS 索引 |
| `kms.py` | 134 | 主密钥提供者（env/vault/http），5 分钟 TTL + 轮换 |
| `observability.py` | 129 | OTel span（无 SDK no-op）+ Prometheus 渲染 |
| `email_templates.py` | 128 | 通知邮件模板（Jinja2） |
| `compliance_controls.py` | 109 | SOC2/ISO27001/GDPR 控制 → 证据映射 |
| `scripts/git_sync.py` | 69 | docs-as-code git 同步（git 二进制） |
| `scripts/quality_gate.py` | 148 | 质量门禁 |
| `search_tokenizer.py` | 87 | CJK 分词（jieba/bigram），注册为 SQLite FTS 函数 |
| `i18n.py` | 70 | 后端 i18n |
| `storage.py` | 162 | 存储抽象（本地/对象） |
| `security.py` | 40 | SSRF 防护 |

测试：`test_*.py` 共 **127 个**文件，统一 `subprocess + env-at-top + 断言 ALL PASSED` 约定，每能力域至少一个。

## 运行

```bash
pip install -r requirements.txt
./dev.sh             # WSL/Windows 挂载强制轮询，避免 --reload 卡死
# 或：uvicorn main:app --host 0.0.0.0 --port 8000 --reload --timeout-graceful-shutdown 25
```

## 测试与质量门禁

```bash
bash scripts/run_tests.sh          # 后端全量套件（127 测试）
python scripts/quality_gate.py     # 质量门禁（lint + 测试 + 覆盖）
python scripts/quality_gate.py --skip-tests   # 仅 lint + 静态检查
```

## 数据库

### SQLite（默认，三层分库）
| 层 | 内容 | 库 |
|----|------|----|
| registry | 身份/组织/团队/审计/leader/refresh token/SCIM/webhook/quota | `registry.db` |
| per-user | 用户全部文档/版本/分支/评论/附件 | `<uid>.docs.db` |
| per-team | 团队文档与团队级数据 | `team_<tid>.docs.db` |

连接池 LRU 全局上限：`MAX_USER_POOLS=256`/`MAX_TEAM_POOLS=128`/`MAX_TOTAL_IDLE_CONNECTIONS=2048`，淘汰整池逐条 close。

### PostgreSQL（共享单库 + RLS）
设 `DATABASE_URL` 启用，`is_pg()` 切换全部代码路径。`org_id` Row Level Security 强制隔离（`FORCE ROW LEVEL SECURITY`）。PG 模式下不进 SQLite 连接池路径，走 `pg_adapter` 连接池。

## 多实例与 leader

- `LEADER_ELECTION_ENABLED=true` 开启；Redis `SET NX`（`REDIS_URL` 配置时）或 registry `leader_lease` CAS。
- 仅 leader 运行备份/合并/SLA/摘要等后台循环。
- `MULTI_INSTANCE_STRICT=true`：拓扑不一致（选举开 + sqlite + 非共享 FS）**抛 RuntimeError 拒绝启动**；`MULTI_INSTANCE_HA=true` 仅告警。
- `REDIS_REQUIRED=true` 但无 `REDIS_URL`：限流退化为进程内计数（不抛、不静默放大）。
- `_storage_mode_info()` 返回 `{backend, multi_instance, unsafe, recommendation}`。

## 环境变量（按关注点分组）

### 基础
| 变量 | 默认 | 说明 |
|------|------|------|
| `DATABASE_URL` | 空 | 设置启用 PostgreSQL 共享单库 + RLS |
| `REDIS_URL` | 空 | 限流跨实例 + leader 选举 |
| `DOC_DATA_DIR` | `backend` | SQLite 三层库根目录 |
| `REGISTRY_DB_PATH` | `<DOC_DATA_DIR>/registry.db` | registry 库路径 |
| `MAX_USER_POOLS` / `MAX_TEAM_POOLS` / `MAX_TOTAL_IDLE_CONNECTIONS` | 256 / 128 / 2048 | 连接池上限 |
| `APP_ENV` | 空 | `production` 启用安全收紧（CORS 等） |
| `CORS_ALLOWED_ORIGINS` | `*` | CORS 白名单 |
| `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_ENABLED` | 30 / true | 限流 |
| `IP_ALLOWLIST` / `IP_BLOCKLIST` | 空 | CIDR 白/黑名单 |

### 鉴权
| 变量 | 默认 | 说明 |
|------|------|------|
| `AUTH_SECRET` | 随机 | 令牌签名密钥 |
| `AUTH_ACCESS_TTL` / `AUTH_REFRESH_TTL` / `AUTH_TOKEN_TTL` | 15min / 30d / 30d | 令牌 TTL |
| `AUTH_ALLOW_REGISTER` | false | 是否开放注册 |
| `API_TOKEN` | 空 | 后端管理令牌 |
| `SCIM_TOKEN` | 空 | SCIM 专用令牌 |
| `OIDC_ISSUER` / `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` / `OIDC_REDIRECT_URI` / `OIDC_SCOPES` | — | OIDC SSO |
| `OIDC_AUTHORIZATION_ENDPOINT` / `OIDC_TOKEN_ENDPOINT` / `OIDC_USERINFO_ENDPOINT` / `OIDC_FRONTEND_URL` / `OIDC_POST_LOGOUT_URL` | — | OIDC 端点 |
| `SAML_SP_ENTITY_ID` / `SAML_ACS_URL` / `SAML_IDP_SSO_URL` / `SAML_IDP_ENTITY_ID` / `SAML_IDP_CERT` / `SAML_XMLSEC1` / `SAML_VERIFY_SIGNATURE` / `SAML_IDP_SLO_URL` | — | SAML 2.0 |

### 加密与 KMS
| 变量 | 默认 | 说明 |
|------|------|------|
| `DOC_ATREST_ENCRYPTION` | 空 | `1` 启用文档静态加密 |
| `DOC_ATREST_KEY` | — | 静态加密主密钥 |
| `AI_ENC_KEY` / `AI_ENC_KEY_PREVIOUS` | (`AUTH_SECRET`) | AI 密钥 Fernet 密钥 + 轮换 |
| `KMS_PROVIDER` | `env` | `env`/`vault`/`http`/`cloud` |
| `VAULT_ADDR` / `VAULT_TOKEN` / `VAULT_SECRET_PATH` / `VAULT_PREVIOUS_PATHS` | — | Vault KV v2 |
| `KMS_URL` / `KMS_TOKEN` / `KMS_JSON_KEY` / `KMS_FIELD` | — | HTTP KMS |

### 审计与合规
| 变量 | 默认 | 说明 |
|------|------|------|
| `AUDIT_IMMUTABLE` | 空 | `true` WORM 触发器 |
| `AUDIT_RETENTION_DAYS` | 空 | 审计保留天数（WORM 模式跳过） |

### 配额
| 变量 | 默认 | 说明 |
|------|------|------|
| `AI_USER_DAILY_QUOTA` / `AI_TEAM_DAILY_QUOTA` / `AI_ALLOWED_MODELS` | 0 / 0 / — | AI 配额（0=不限） |
| `USER_MAX_DOCS` / `USER_MAX_STORAGE_BYTES` / `USER_MAX_TEAMS` | 0 | 用户配额 |
| `TEAM_MAX_DOCS` / `TEAM_MAX_STORAGE_BYTES` / `TEAM_MAX_MEMBERS` | 0 | 团队配额 |
| `MAX_VERSIONS_PER_DOC` | 50 | 版本快照轮转上限 |

### 多实例与 leader
| 变量 | 默认 | 说明 |
|------|------|------|
| `LEADER_ELECTION_ENABLED` | 空 | `true` 开启 |
| `LEADER_LEASE_TTL_SECONDS` / `LEADER_RENEW_INTERVAL_SECONDS` / `LEADER_KEY` | — | 租约参数 |
| `MULTI_INSTANCE_STRICT` / `MULTI_INSTANCE_HA` / `DOC_DATA_DIR_SHARED` / `REDIS_REQUIRED` | 空 | 多实例策略（比较 `=="true"`） |

### 协同
| 变量 | 默认 | 说明 |
|------|------|------|
| `COLLAB_UPDATE_GC_THRESHOLD` / `COLLAB_SNAPSHOT_STALE_SEC` / `COLLAB_MAX_SNAPSHOT_BYTES` / `COLLAB_MAX_UPDATES_PER_ROOM` | — | Yjs 规模护栏 |
| `COLLAB_MAX_PRESENCE_PER_ROOM` / `COLLAB_MAX_AWARENESS_BYTES` | — | 在线状态上限 |

### 备份与 DR
| 变量 | 默认 | 说明 |
|------|------|------|
| `BACKUP_DIR` / `BACKUP_INTERVAL_HOURS` / `BACKUP_KEEP` / `BACKUP_DRILL_INTERVAL_HOURS` | — | 备份 |
| `REPLICA_DIR` / `DR_RPO_ALERT_SECONDS` | — | DR 副本 + RPO 告警 |
| `DATA_RESIDENCY_ENABLED` / `RESIDENCY_REGIONS` / `RESIDENCY_DEFAULT_REGION` / `DEPLOY_REGION` / `PG_REPLICA_ROLE` / `MULTI_REGION_ACTIVE_ACTIVE` | — | 数据驻留 |

### 通知与集成
| 变量 | 默认 | 说明 |
|------|------|------|
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` / `SMTP_USE_TLS` | — | SMTP |
| `EMAIL_DIGEST_ENABLED` / `EMAIL_DIGEST_INTERVAL_SECONDS` / `EMAIL_DIGEST_MAX_ITEMS` / `EMAIL_DIGEST_LOOKBACK_DAYS` | — | 邮件摘要 |
| `INTEGRATION_SLACK_WEBHOOK_URL` / `INTEGRATION_TEAMS_WEBHOOK_URL` / `INTEGRATION_NOTIFY_EVENTS` | — | 集成连接器 |

### 运维与观测
| 变量 | 默认 | 说明 |
|------|------|------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_SERVICE_NAME` / `SENTRY_DSN` | — | OTel / Sentry |
| `SECURITY_HEADERS_ENABLED` / `CSP_DIRECTIVES` / `HSTS_MAX_AGE` | — | 安全响应头 |
| `LINK_CHECK_INTERVAL_HOURS` | — | 断链扫描周期 |
| `LIFECYCLE_REQUIRE_SIGNATURE` | 空 | `true` 强制电子签名发布 |

### 沙箱与代理
| 变量 | 默认 | 说明 |
|------|------|------|
| `JUDGE0_API_BASE` | `https://ce.judge0.com` | 代码沙箱引擎 |
| `SANDBOX_API_TOKEN` | 空 | Judge0 令牌 |

## API 概览

259 路由（258 HTTP + 1 WebSocket），按关注点分组：认证 21、SCIM 10、文档 44、文件夹/上传 6、搜索/链接图 8、团队 24、评审/工作流 6、发布 6、管理 37、AI 19、集成 5、Git 绑定 5、OAuth2 6、令牌 3、回收站 4、分享/访客 15、模板 12、分析 6、通知 3、沙箱/代理 5、协同（WS）1、指标/健康/PWA/i18n/sync 10。完整端点见 `main.py`，OpenAPI 发现 `GET /api/v1/openapi`。

## 多用户数据隔离

SQLite 模式靠物理分库（per-user/per-team docs.db）天然隔离；PG 模式靠 `org_id` RLS 策略。跨用户访问文档须经 ACL 显式授权（`PUT /api/docs/{id}/acl` / `/api/teams/{tid}/docs/{id}/acl`，带过期）。viewer 角色仅见已发布文档。
