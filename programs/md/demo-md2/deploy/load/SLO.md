# SLO 与负载门禁（P1-4）

企业团队文档开发平台的服务等级目标与 nightly 基线负载门禁。基线脚本
`deploy/load/run_baseline.sh` 在 CI nightly 与本地均可复现，违反任一阈值即标红阻断。

## SLO 目标

基线场景：`-u 20 -r 2 -t 30s`（20 并发用户、每秒 2 个爬坡、持续 30s）。
该场景为"常规团队协作峰值"标定，非极限压测；极限容量评估另行手工执行。

| 维度 | 目标 | 阈值（门禁） | 说明 |
|------|------|--------------|------|
| 可用性 | 核心链路 5xx = 0 | 失败率 `0.0` | 任一请求 5xx/连接错误即 FAIL |
| 延迟 p99 | 全路由 ≤ 2s | `SLO_MAX_P99_MS=2000` | 与 `alerts.yml` 的 `MdHighP99Latency` 对齐 |
| 探针 | `/ready` 100% 成功 | 失败率 `0.0` | 负载下就绪探针不得退化 |

### 按路由分类的目标（参考，未在门禁中逐路由强制）
| 类别 | 路由 | 目标 p99 |
|------|------|---------|
| 读 | `GET /api/docs`、`GET /api/docs/{id}` | ≤ 800ms |
| 写 | `POST /api/docs` | ≤ 1200ms |
| 搜索 | `GET /api/search` | ≤ 1000ms（PG trgm 索引命中） |
| 探针 | `GET /ready` | ≤ 200ms |

> 门禁脚本当前以"全路由最高 p99 ≤ 2000ms"为硬阈值（保守、与告警对齐）。
> 逐路由更严阈值供容量规划参考，后续可按 `Name` 维度细化门禁。

## 工件

| 文件 | 职责 |
|------|------|
| `deploy/load/locustfile.py` | Locust `DocUser`：注册/登录 → 列/读/建/搜 → 退出，思考时间 1.5–4s |
| `deploy/load/check_slo.py` | 解析 locust `--json`，判定失败率/p99，违规非 0 退出 |
| `deploy/load/run_baseline.sh` | 拉起后端 + 轮询就绪 + 跑 locust + 管道判定 |

## 运行

### 本地
```bash
pip install locust uvicorn
bash deploy/load/run_baseline.sh
# 自定义负载
SLO_USERS=50 SLO_RATE=5 SLO_RUN_TIME=60s bash deploy/load/run_baseline.sh
# 放宽 p99（容量摸底，仅诊断不阻断）
SLO_MAX_P99_MS=5000 bash deploy/load/run_baseline.sh
```

### CI nightly
`.github/workflows/ci.yml` 的 `slo-nightly` job（cron）：
`pip install locust uvicorn` → `bash deploy/load/run_baseline.sh`，违规则 job 标红。

## 与告警的关系
- 门禁是"发布前的阻断闸"（nightly/预发）：基线场景不过则不上线。
- `alerts.yml` 是"运行时的探测"（Prometheus）：线上 p99>2s 持续 10m 或错误率>5% 持续 5m 告警。
- 两者共用 2s/5% 这组数，保证"基线门禁过的版本，线上告警阈值仍合理"。
