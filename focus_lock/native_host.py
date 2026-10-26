import json
import os
import struct
import time
import uuid
from pathlib import Path


def read_message(stream):
    header = stream.read(4)
    if not header:
        return None
    if len(header) != 4:
        raise ValueError("Incomplete header")
    length = struct.unpack("<I", header)[0]
    if length > 262144:
        raise ValueError("Message too large")
    body = stream.read(length)
    if len(body) != length:
        raise ValueError("Incomplete body")
    value = json.loads(body.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected object")
    return value


def write_message(stream, value):
    body = json.dumps(value).encode("utf-8")
    stream.write(struct.pack("<I", len(body)) + body); stream.flush()


def respond(root, request, clock=time.time):
    request_tabs = False
    try:
        tab_request = json.loads((root / "browser-tabs-request.json").read_text(encoding="utf-8"))
        request_tabs = tab_request.get("browser") == request.get("browser") and tab_request.get("expires_at", 0) > clock()
    except (OSError, ValueError, TypeError):
        pass
    try:
        policy = json.loads((root / "browser-policy.json").read_text(encoding="utf-8"))
        if not isinstance(policy, dict) or policy.get("expires_at", 0) <= clock():
            policy = {"active": False, "revision": "expired", "urls": []}
    except (OSError, ValueError, TypeError):
        policy = {"active": False, "revision": "offline", "urls": []}
    browser = request.get("browser")
    if browser not in ("chrome", "edge"):
        return {"active": False, "revision": "invalid-client", "urls": []}
    tabs = None
    if request_tabs and isinstance(request.get("tabs"), list):
        tabs = [{"title": str(item.get("title", ""))[:160], "url": item["url"][:2048]} for item in request["tabs"][:100]
                if isinstance(item, dict) and isinstance(item.get("url"), str) and item["url"].startswith(("http://", "https://"))]
    status = {"updated_at": clock(), "revision": request.get("revision", ""),
              "applied": request.get("applied") is True, "error": str(request.get("error", ""))[:300],
              "protocol": 3 if request.get("protocol") == 3 else 0, "tabs": tabs}
    try:
        root.mkdir(parents=True, exist_ok=True)
        temporary = root / f"browser-{browser}-{uuid.uuid4().hex}.tmp"
        temporary.write_text(json.dumps(status), encoding="utf-8")
        temporary.replace(root / f"browser-{browser}.json")
    except OSError:
        pass
    if policy.get("browser") != browser:
        return {**policy, "active": False, "urls": [], "request_tabs": request_tabs}
    return {**policy, "request_tabs": request_tabs}


def serve(source, destination, root=None):
    root = Path(root) if root else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FocusLock"
    try:
        while (message := read_message(source)) is not None:
            write_message(destination, respond(root, message))
    except (ValueError, OSError, TypeError, struct.error):
        return
