from app.config import get_settings
import httpx

s = get_settings()
print("has_key", bool(s.openai_api_key))
print("model", s.openai_model)

url = s.openai_base_url.rstrip("/") + "/chat/completions"
headers = {
    "Authorization": f"Bearer {s.openai_api_key}",
    "Content-Type": "application/json",
}
body = {
    "model": s.openai_model,
    "messages": [{"role": "user", "content": "Tra ve JSON: {\"ok\": true}"}],
    "temperature": 0,
    "max_tokens": 50,
    "response_format": {"type": "json_object"},
}

resp = httpx.post(url, headers=headers, json=body, timeout=45)
print("status", resp.status_code)

try:
    payload = resp.json()
except Exception:
    payload = {}
err = payload.get("error") or {}
print("err_type", err.get("type"))
print("err_code", err.get("code"))
