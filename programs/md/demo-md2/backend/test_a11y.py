# -*- coding: utf-8 -*-
"""无障碍 a11y：前端跳转链接/ARIA live 区/sr-only/减少动态偏好/焦点环。"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INDEX = os.path.join(ROOT, "index.html")
STYLES = os.path.join(ROOT, "styles.css")
APPJS = os.path.join(ROOT, "app.js")

idx = open(INDEX, encoding="utf-8").read()
css = open(STYLES, encoding="utf-8").read()
appjs = open(APPJS, encoding="utf-8").read()

# 1) 跳转主编辑区链接（Tab 可聚焦）
assert 'class="skip-link"' in idx and 'href="#editor"' in idx, "缺 skip-link"

# 2) ARIA live 播报区
assert 'id="ariaLive"' in idx and 'aria-live="polite"' in idx, "缺 aria-live 区"

# 3) sr-only 视觉隐藏类（供辅助技术读取）
assert ".sr-only" in css, "缺 .sr-only 类"

# 4) 尊重 prefers-reduced-motion
assert "@media (prefers-reduced-motion: reduce)" in css, "缺 prefers-reduced-motion"

# 5) :focus-visible 焦点环兜底
assert ":focus-visible" in css, "缺 :focus-visible"

# 6) announceA11y 全局播报助手
assert "announceA11y" in appjs, "缺 announceA11y 助手"

# 7) 图标按钮带 aria-label（抽样校验）
assert "data-i18n-attr" in idx and "aria-label" in idx, "图标按钮缺 aria-label"

print("ALL PASSED")
