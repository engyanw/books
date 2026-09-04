# -*- coding: utf-8 -*-
"""Locust 负载压测脚本：覆盖企业团队文档平台核心场景。

用法（先启动后端 uvicorn main:app --port 8000）：
    pip install locust
    locust -f locustfile.py --host http://localhost:8000

然后浏览器打开 http://localhost:8089 设置并发用户数与加压速率。
也可无界面跑：
    locust -f locustfile.py --host http://localhost:8000 \
           --headless -u 100 -r 10 --run-time 60s
"""
import os
import re
from locust import HttpUser, task, between

# 压测用账号（运行前预先注册，或用 AUTH_ALLOW_REGISTER=true 自动注册）
USERNAME = os.environ.get("LOAD_USER", "loadtest")
PASSWORD = os.environ.get("LOAD_PASS", "loadpass123")


class DocUser(HttpUser):
    """模拟一个团队文档用户：登录 → 列文档 → 读文档 → AI 聊天 → 协同 WS 握手。"""
    wait_time = between(0.5, 2.0)
    token = None

    def on_start(self):
        # 注册（已存在则忽略）→ 登录拿 token
        self.client.post("/api/auth/register", json={"username": USERNAME, "password": PASSWORD})
        r = self.client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
        if r.status_code == 200:
            self.token = r.json().get("token")
            self.h = {"Authorization": f"Bearer {self.token}"}
        else:
            self.h = {}

    @task(5)
    def list_and_read_docs(self):
        """列出个人文档并读取第一个。"""
        if not self.token:
            return
        r = self.client.get("/api/docs", headers=self.h)
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                doc_id = items[0]["doc_id"]
                self.client.get(f"/api/docs/{doc_id}", headers=self.h, name="/api/docs/{id}")

    @task(2)
    def create_doc(self):
        """创建文档（验证写路径吞吐）。"""
        if not self.token:
            return
        self.client.post("/api/docs", json={"title": "load-test", "content": "# 压测\n"}, headers=self.h, name="/api/docs (create)")

    @task(3)
    def search(self):
        """全局搜索（FTS5 路径）。"""
        if not self.token:
            return
        self.client.get("/api/search?q=load", headers=self.h, name="/api/search")

    @task(1)
    def ai_chat(self):
        """AI 聊天（若无可用配置会 404/400，仅压连接路径）。"""
        if not self.token:
            return
        self.client.post("/api/ai/chat",
                         json={"config_id": "", "messages": [{"role": "user", "content": "hi"}]},
                         headers=self.h, name="/api/ai/chat")

    @task(1)
    def settings_roundtrip(self):
        """配置读写（无 DB 负载基准）。"""
        if not self.token:
            return
        self.client.get("/api/settings", headers=self.h, name="/api/settings")
