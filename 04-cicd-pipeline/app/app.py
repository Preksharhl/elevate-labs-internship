import os
import socket
from flask import Flask, jsonify, request

app = Flask(__name__)
ITEMS = []  # in-memory store, enough for a pipeline demo

VERSION = os.getenv("APP_VERSION", "1.0.0")
GIT_SHA = os.getenv("GIT_SHA", "local")

PAGE = """<!doctype html><title>CI/CD Demo</title>
<body style="font-family:system-ui;background:#0f172a;color:#e2e8f0;
display:grid;place-items:center;height:100vh;margin:0">
<div style="background:#1e293b;padding:40px 56px;border-radius:16px;box-shadow:0 10px 40px #0008">
<h1 style="margin-top:0">🚀 CI/CD Pipeline Demo</h1>
<p>Version: <b>{v}</b></p><p>Commit: <code>{sha}</code></p>
<p>Served by pod/host: <code>{host}</code></p>
<p style="color:#94a3b8">Deployed via GitHub Actions → Docker Hub → Minikube</p></div></body>"""


@app.get("/")
def home():
    return PAGE.format(v=VERSION, sha=GIT_SHA[:7], host=socket.gethostname())


@app.get("/health")
def health():
    return jsonify(status="ok", version=VERSION)


@app.get("/api/items")
def list_items():
    return jsonify(ITEMS)


@app.post("/api/items")
def add_item():
    name = ((request.get_json(silent=True) or {}).get("name") or "").strip()
    if not name:
        return jsonify(error="name is required"), 400
    item = {"id": len(ITEMS) + 1, "name": name}
    ITEMS.append(item)
    return jsonify(item), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
