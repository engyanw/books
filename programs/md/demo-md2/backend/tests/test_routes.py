import sys
sys.path.insert(0, 'backend')
from fastapi.testclient import TestClient
import main

c = TestClient(main.app)

# 验证 search 路由不被 {doc_id} 拦截
r = c.get('/api/docs/search')
print('search status:', r.status_code)
print('search body keys:', list(r.json().keys()) if r.status_code == 200 else r.text[:80])

# 验证 tags 路由
r = c.get('/api/docs/tags')
print('tags status:', r.status_code)
print('tags body:', r.json() if r.status_code == 200 else r.text[:80])

# 验证带参数的 search
r = c.get('/api/docs/search?q=hello&date=7d&sort=opened')
print('search params status:', r.status_code, list(r.json().keys()) if r.status_code == 200 else '')

# 验证 {doc_id} 仍能匹配真实 id（不冲突）
r = c.get('/api/docs/some-fake-id')
print('fake doc status:', r.status_code, '(应 404)')
