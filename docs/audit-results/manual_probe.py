import hashlib
import json
import subprocess
import time
from urllib import request, error
BASE = "http://localhost:8180"

def call(method, path, body=None, token=None):
    data = None if body is None else json.dumps(body).encode()
    req = request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with request.urlopen(req, timeout=10) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else None
    except error.HTTPError as e:
        raw = e.read().decode()
        try:
            parsed = json.loads(raw) if raw else None
        except Exception:
            parsed = raw
        return e.code, parsed

def rexec(*args):
    return subprocess.check_output(["docker", "compose", "-p", "aura_audit_111515", "exec", "-T", *args], text=True)

out = []
def record(name, status, payload):
    out.append({"name": name, "status": status, "payload": payload})

# health / public menu / maps no-key behavior
record("health", *call("GET", "/health"))
record("public_menu", *call("GET", "/api/v1/menu"))
record("maps_suggest_no_key", *call("GET", "/api/v1/maps/suggest?query=Москва"))
# staff auth
for role, login, pwd in [("admin", "admin", "admin123"), ("barista", "barista", "barista123"), ("courier", "courier", "courier123")]:
    st, payload = call("POST", "/api/v1/staff/auth/login", {"login": login, "password": pwd})
    record(f"staff_login_{role}", st, {"keys": sorted(payload.keys()) if isinstance(payload, dict) else payload, "role": payload.get("role") if isinstance(payload, dict) else None})
    globals()[role + "_token"] = payload.get("access_token") if isinstance(payload, dict) else None
# RBAC probes
record("admin_orders_unauth", *call("GET", "/api/v1/admin/orders"))
record("admin_orders_as_courier", *call("GET", "/api/v1/admin/orders", token=globals().get("courier_token")))
record("admin_orders_as_admin", *call("GET", "/api/v1/admin/orders", token=globals().get("admin_token")))
# customer OTP flow via log backend + Redis
phone = "+79991234567"
ph = hashlib.sha256(phone.encode()).hexdigest()
try:
    rexec("redis", "redis-cli", "DEL", f"sms_rate:{ph}:min", f"sms_rate:{ph}:hour", f"sms_rate:{ph}:day", f"otp:{ph}")
except Exception as exc:
    record("redis_rate_reset", 999, str(exc))
st, payload = call("POST", "/api/v1/auth/send-code", {"phone": phone})
record("otp_send", st, payload)
phone_hash = payload.get("phone_hash") if isinstance(payload, dict) else ph
otp_data = None
for _ in range(15):
    raw = rexec("redis", "redis-cli", "GET", f"otp:{phone_hash}").strip()
    if raw and raw != "nil":
        otp_data = json.loads(raw)
        if otp_data.get("status") == "sent":
            break
    time.sleep(1)
record("otp_redis_payload", 200 if otp_data else 404, {k: ("REDACTED" if k == "code" else v) for k, v in (otp_data or {}).items()})
code = otp_data.get("code") if otp_data else "000000"
st, payload = call("POST", "/api/v1/auth/verify-code", {"phone": phone, "code": code})
record("otp_verify", st, {"keys": sorted(payload.keys()) if isinstance(payload, dict) else payload, "role": payload.get("role") if isinstance(payload, dict) else None})
cust_token = payload.get("access_token") if isinstance(payload, dict) else None
# customer profile/cart/order probes
record("profile_me", *call("GET", "/api/v1/profile", token=cust_token))
record("cart_get", *call("GET", "/api/v1/cart", token=cust_token))
record("cart_add_invalid_unauth", *call("POST", "/api/v1/cart/items", {"menu_item_id": 999999, "quantity": 1}))
record("cart_add_invalid_auth", *call("POST", "/api/v1/cart/items", {"menu_item_id": 999999, "quantity": 1}, token=cust_token))
record("orders_history", *call("GET", "/api/v1/orders", token=cust_token))
# barista/courier route surface basic auth checks
record("barista_orders_as_barista", *call("GET", "/api/v1/barista/orders", token=globals().get("barista_token")))
record("courier_orders_as_courier", *call("GET", "/api/v1/courier/orders", token=globals().get("courier_token")))
record("courier_orders_as_customer", *call("GET", "/api/v1/courier/orders", token=cust_token))
print(json.dumps(out, ensure_ascii=False, indent=2))
