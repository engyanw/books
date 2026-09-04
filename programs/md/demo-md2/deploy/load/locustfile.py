# -*- coding: utf-8 -*-
"""Locust 负载基线 —— 企业团队文档开发平台核心链路。

模拟真实用户会话：注册/登录 → 列文档 → 新建文档 → 读取 → 搜索 → 偶发退出。
后端须以 AUTH_ALLOW_REGISTER=true 启动（nightly job 已设）。

用法（手工）：
  locust -f deploy/load/locustfile.py --host http://127.0.0.1:8000 \
         --headless -u 20 -r 2 -t 30s --json | python deploy/load/check_slo.py
"""
import random
import string

from locust import HttpUser, between, task


def _rand_user():
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"load_{suffix}", "p@ssw0rd"


class DocUser(HttpUser):
    # 思考时间：1.5–4s，贴近真实阅读/编辑节奏（而非压垮式无间隔轰炸）
    wait_time = between(1.5, 4.0)

    def on_start(self):
        self.token = None
        self.username, self.password = _rand_user()
        # 注册（已存在则退回登录）；拿到 Bearer token 后注入后续请求
        r = self.client.post("/api/auth/register",
                             json={"username": self.username, "password": self.password},
                             name="POST /api/auth/register", catch_response=True)
        if r.status_code >= 400:
            r = self.client.post("/api/auth/login",
                                 json={"username": self.username, "password": self.password},
                                 name="POST /api/auth/login", catch_response=True)
        try:
            tok = r.json().get("token")
        except Exception:
            tok = None
        if not tok:
            r.failure("未获取 token")
            return
        r.success()
        self.token = tok
        self.h = {"Authorization": f"Bearer {tok}"}
        # 预置一篇文档供读取/搜索
        d = self.client.post("/api/docs", headers=self.h,
                             json={"title": "seed", "content": "# seed\n架构设计 基线"},
                             name="POST /api/docs (seed)").json()
        self.doc_id = d.get("doc_id")

    def on_stop(self):
        if self.token:
            self.client.post("/api/auth/logout", headers=self.h, name="POST /api/auth/logout")

    @task(5)
    def list_docs(self):
        self.client.get("/api/docs", headers=self.h, name="GET /api/docs")

    @task(4)
    def get_doc(self):
        if self.doc_id:
            self.client.get(f"/api/docs/{self.doc_id}", headers=self.h, name="GET /api/docs/{id}")

    @task(3)
    def create_doc(self):
        self.client.post("/api/docs", headers=self.h,
                         json={"title": "load", "content": f"# load {random.randint(0, 10**6)}"},
                         name="POST /api/docs")

    @task(2)
    def search(self):
        self.client.get("/api/search", headers=self.h,
                        params={"q": random.choice(["架构", "seed", "load", "design"])},
                        name="GET /api/search")

    @task(1)
    def ready(self):
        # 探针：未鉴权，验证 /ready 在负载下仍 200
        self.client.get("/ready", name="GET /ready")
