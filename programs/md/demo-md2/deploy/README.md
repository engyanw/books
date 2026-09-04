# 部署与迁移 Runbook（企业生产）

本文档覆盖：迁移流水线、容器编排（docker-compose / k8s Helm）、蓝绿与金丝雀策略、多实例一致性约束。

## 1. 迁移流水线（alembic）

schema 由应用启动时的幂等 DDL 维护（`_init_registry_db` / `_apply_documents_schema`），alembic 负责**版本化增量变更**。基线已 stamp（`0003_registry_schema`）。

```bash
# 应用所有迁移（PG 生产）
DATABASE_URL=postgresql://user:pass@pg:5432/md2 alembic upgrade head

# SQLite（开发/单机）
REGISTRY_DB_PATH=./data/registry.db alembic upgrade head

# 现有部署首次接入：标记当前库已到最新，不实际执行
alembic stamp head

# 回滚一版（生产务必先备份）
alembic downgrade -1
```

CI 已在 `ci.yml` 的 `backend` job（SQLite）与 `pg` job（真实 PG）各跑一次 `alembic upgrade head`，迁移不可应用即阻断。

## 2. 容器编排

### docker-compose（单机/小规模多实例）
`docker-compose.yml`：backend + redis，`/ready` 健康检查，`stop_grace_period: 30s` 优雅关闭，`depends_on: redis(service_healthy)`。多实例：`docker-compose up --scale backend=2`（需配 Redis + PG，见下约束）。

### k8s Helm chart（`deploy/helm/md-docs``）
```bash
helm install md-docs ./deploy/helm/md-docs \
  --set backend.replicaCount=3 \
  --set backend.env.DATABASE_URL='postgresql://md2:$(SECRET)@pg:5432/md2' \
  --set backend.env.REDIS_URL='redis://md-docs-redis:6379/0'
```
- `backend.strategy.rollingUpdate.maxUnavailable=0`：新实例 `/ready` 通过后才下旧实例（近似蓝绿）。
- `postgres.enabled=false`：默认不内置 PG，建议用云托管 PG（RDS/Cloud SQL）。

## 3. 蓝绿 / 金丝雀
- **蓝绿**：Helm `--set backend.strategy.rollingUpdate.maxSurge=1,maxUnavailable=0` + readiness gate；或部署两套 release（`md-docs-blue`/`md-docs-green`）切 Service selector/Ingress 权重。
- **金丝雀**：内置 RollingUpdate 可逐步替换（`maxSurge=1`）；精细化流量切分接入 Argo Rollouts / Flagger（不内置以避免耦合），用 `canary` 步骤按 10%→50%→100% 切流，每步观测 `/metrics` 错误率与 `/ready`。

## 4. 多实例一致性约束（关键）
SQLite per-user 模式下请求路径写本地文件，多实例 active/active 无共享 FS 则同一用户 `docs.db` 会被并发写损坏。**leader 选举只守护后台循环，不协调请求路径。**

| 部署形态 | 请求路径一致？ | 说明 |
|---|---|---|
| 单实例 SQLite | ✓ | 默认 |
| 多实例 SQLite + 共享 FS | △ 降级 | `DOC_DATA_DIR_SHARED=true`；非并发安全，仅过渡 |
| 多实例 PG 单库 | ✓ | 推荐：`DATABASE_URL` + `LEADER_ELECTION_ENABLED=true` |

运行时观测：`GET /api/admin/storage-mode` 返回 `unsafe/recommendation`；启动时 `MULTI_INSTANCE_STRICT=true` 可在不安全时直接拒绝启动。

## 5. 备份与 PITR
- 备份：`POST /api/admin/backup`（仅管理员），含定时循环 `_backup_loop` 与恢复演练 `_backup_drill_loop`。
- PG PITR：用 wal-g/pgBackRest 连续归档 WAL（外部工具职责，见 `DEPLOY_MULTI_TEAM.md` 的 PITR 章节）。
