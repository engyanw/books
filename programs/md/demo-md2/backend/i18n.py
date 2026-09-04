# -*- coding: utf-8 -*-
"""UI 国际化（i18n）字符串表 + 离线移动端支持。

- STRINGS：zh/en 两套 UI 文案（前端按 locale 拉取后渲染）。
- locales()：列出可用语言。
- translate(locale, key)：单键翻译（带 zh 回退）。
离线：前端把 /api/i18n/{locale} 与 /api/sync/bundle 缓存进 Service Worker，
断网时用 IndexedDB 里的文档快照继续编辑，联网后按 cursor 增量同步回写。
"""
STRINGS: dict[str, dict[str, str]] = {
    "zh": {
        "app.title": "Markdown 文档编辑器",
        "doc.save": "保存",
        "doc.saved": "已保存",
        "doc.save_failed": "保存失败",
        "doc.unchanged": "未修改",
        "doc.create": "新建文档",
        "doc.delete": "删除",
        "doc.search": "搜索",
        "doc.title": "标题",
        "auth.login": "登录",
        "auth.logout": "登出",
        "auth.register": "注册",
        "review.submit": "提交评审",
        "review.approve": "通过",
        "review.reject": "驳回",
        "collab.editing": "正在编辑",
        "offline.mode": "离线模式",
        "offline.pending": "待同步",
        "offline.sync": "同步",
    },
    "en": {
        "app.title": "Markdown Document Editor",
        "doc.save": "Save",
        "doc.saved": "Saved",
        "doc.save_failed": "Save failed",
        "doc.unchanged": "No changes",
        "doc.create": "New document",
        "doc.delete": "Delete",
        "doc.search": "Search",
        "doc.title": "Title",
        "auth.login": "Login",
        "auth.logout": "Logout",
        "auth.register": "Register",
        "review.submit": "Submit review",
        "review.approve": "Approve",
        "review.reject": "Reject",
        "collab.editing": "Editing",
        "offline.mode": "Offline mode",
        "offline.pending": "Pending sync",
        "offline.sync": "Sync",
    },
}

DEFAULT_LOCALE = "zh"


def locales() -> list[str]:
    return sorted(STRINGS.keys())


def strings_for(locale: str) -> dict[str, str]:
    loc = (locale or "").lower().split("-")[0]
    if loc in STRINGS:
        return STRINGS[loc]
    return STRINGS[DEFAULT_LOCALE]


def translate(locale: str, key: str) -> str:
    return strings_for(locale).get(key, key)
