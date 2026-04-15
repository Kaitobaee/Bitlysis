from app.config import get_settings
import httpx

s = get_settings()
headers = {
    "Authorization": f"Bearer {s.openai_api_key}",
    "Content-Type": "application/json",
}
body = {
    "model": s.openai_model,
    "input": "Reply JSON only: {\"ok\": true}",
}
r = httpx.post(s.openai_base_url.rstrip("/") + "/responses", headers=headers, json=body, timeout=45)
print("status", r.status_code)
try:
    j = r.json()
except Exception:
    j = {}
e = j.get("error") or {}
print("err_type", e.get("type"))
print("err_code", e.get("code"))
