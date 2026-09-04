FROM python:3.12-slim

WORKDIR /app

# 安装依赖（利用缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 数据库文件目录（挂载卷持久化）：registry.db + users/<uid>/docs.db + configs/<uid>.json
VOLUME ["/app/data"]
ENV DOC_DATA_DIR=/app/data
ENV REGISTRY_DB_PATH=/app/data/registry.db

# 暴露端口
EXPOSE 8000

# 优雅停止：SIGTERM 触发 lifespan shutdown（drain 后台任务 + 关连接池）
STOPSIGNAL SIGTERM

# 容器健康检查：/ready 校验 DB/Redis 真正可达（不只是进程存活）
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=3).status==200 else 1)"

# 启动
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "25"]
