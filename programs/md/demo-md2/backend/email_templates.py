# -*- coding: utf-8 -*-
"""邮件模板系统：Jinja2 渲染 + 退信/重试处理。

模板以字符串内建（避免外部文件依赖），渲染后调用 _send_email 发送。
失败重试 3 次（指数退避），全部失败记录日志但不阻断业务（邮件非强一致）。

对外：send_templated_email(to, template_name, context) -> bool(是否成功投递)
"""
import asyncio
import logging
import os

logger = logging.getLogger("email_templates")

# 退信地址（NDR）接收：简单实现，记录失败的投递便于排查
BOUNCE_LOG = os.environ.get("BOUNCE_LOG", "").strip()

# 内建模板（subject + body，Jinja2 语法）
_TEMPLATES = {
    "guest_invite": {
        "subject": "邀请你加入 {{ product_name }} 文档协作",
        "body": (
            "你好 {{ guest_name }}，\n\n"
            "{{ inviter }} 邀请你加入文档协作。\n"
            "请点击以下链接设置密码完成注册：\n{{ invite_url }}\n\n"
            "（链接 7 天内有效）\n\n"
            "—— {{ product_name }}"
        ),
    },
    "review_request": {
        "subject": "[评审请求] {{ doc_title }} 等待你{{ mode_desc }}",
        "body": (
            "你好 {{ reviewer_name }}，\n\n"
            "{{ requester }} 提交了文档《{{ doc_title }}》的评审请求（{{ mode_desc }}）。\n"
            "{{ step_desc }}\n\n"
            "请在系统中查看并处理：{{ link }}\n\n"
            "—— {{ product_name }}"
        ),
    },
    "share_notify": {
        "subject": "{{ sharer }} 分享了文档《{{ doc_title }}》给你",
        "body": (
            "{{ sharer }} 分享了文档《{{ doc_title }}》。\n"
            "访问链接：{{ link }}\n"
            "{% if expires %}有效期至 {{ expires }}\n{% endif %}"
            "—— {{ product_name }}"
        ),
    },
    "welcome": {
        "subject": "欢迎注册 {{ product_name }}",
        "body": (
            "你好 {{ username }}，\n\n"
            "欢迎注册 {{ product_name }}！你可以开始创建文档、协作与分享了。\n\n"
            "—— {{ product_name }} 团队"
        ),
    },
    "notification_digest": {
        "subject": "[{{ product_name }}] 你有 {{ unread_count }} 条未读通知",
        "body": (
            "你好 {{ username }}，\n\n"
            "你在 {{ product_name }} 有 {{ unread_count }} 条未读通知：\n\n"
            "{% for item in items %}"
            "• {{ item.detail }}{% if item.link %}（{{ item.link }}）{% endif %}\n"
            "{% endfor %}"
            "{% if more %}…还有 {{ more }} 条未读，请登录后查看。\n{% endif %}\n"
            "—— {{ product_name }}"
        ),
    },
}


def _get_env():
    try:
        from jinja2 import Environment
        return Environment(autoescape=False, keep_trailing_newline=True)
    except ImportError:
        logger.warning("jinja2 未安装，邮件模板回退为纯字符串替换")
        return None


_env = _get_env()


def render_template(template_name: str, context: dict) -> tuple[str, str]:
    """渲染邮件模板，返回 (subject, body)。无 jinja2 时做简单 str.format 回退。"""
    tpl = _TEMPLATES.get(template_name)
    if tpl is None:
        raise ValueError(f"未知邮件模板: {template_name}")
    ctx = {"product_name": os.environ.get("PRODUCT_NAME", "Markdown Editor"), **context}
    if _env is not None:
        subject = _env.from_string(tpl["subject"]).render(**ctx)
        body = _env.from_string(tpl["body"]).render(**ctx)
    else:
        # 回退：简单 str.format（忽略 Jinja 控制语句，模板里若有 {% %} 会原样保留）
        subject = tpl["subject"].format(**ctx)
        body = tpl["body"].format(**ctx)
    return subject, body


async def send_templated_email(to: str, template_name: str, context: dict, max_retries: int = 3) -> bool:
    """渲染模板并发送，失败重试（指数退避）。返回是否最终成功。"""
    subject, body = render_template(template_name, context)
    # 延迟导入避免循环依赖
    from main import _send_email
    for attempt in range(1, max_retries + 1):
        try:
            await _send_email(to, subject, body)
            return True
        except Exception as e:
            logger.warning("邮件投递失败 attempt=%d/%d to=%s: %s", attempt, max_retries, to, e)
            if attempt < max_retries:
                await asyncio.sleep(0.5 * attempt)
    # 全部失败 → 记录退信
    _log_bounce(to, subject, "max_retries_exceeded")
    return False


def _log_bounce(to: str, subject: str, reason: str):
    """记录退信（投递失败）便于排查。"""
    msg = f"[bounce] to={to} subject={subject} reason={reason}"
    logger.warning(msg)
    if BOUNCE_LOG:
        try:
            from pathlib import Path
            with open(BOUNCE_LOG, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass
