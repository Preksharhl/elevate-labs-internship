"""Create demo users + sample incidents (some resolved). Run: python seed.py"""
import secrets
from werkzeug.security import generate_password_hash
import app as A

USERS = [("admin", "admin123", "admin"), ("priya", "engineer123", "engineer"), ("rahul", "reporter123", "reporter")]
SAMPLES = [
    ("Production API returning 502 errors", "Gateway timing out after deploy v2.4.1", "application", "critical", True, "Rolled back to v2.4.0; fixed missing env var."),
    ("Disk usage at 94% on db-server-02", "Log rotation not running.", "infrastructure", "high", True, "Fixed logrotate cron and cleared 40GB of old logs."),
    ("Slow login page (8s load)", "Reported by multiple users.", "application", "medium", True, "Added index on users.email; load time now 300ms."),
    ("VPN drops every 30 minutes", "Remote staff affected.", "network", "high", False, None),
    ("SSL certificate expiring in 5 days", "Wildcard cert for *.example.com", "security", "medium", False, None),
    ("Backup job failing silently", "Nightly DB backup exits 0 but file is empty.", "database", "critical", False, None),
]
A.init_db()
with A.app.test_request_context():
    d = A.db()
    ids = {}
    for name, pw, role in USERS:
        if not d.execute("SELECT 1 FROM users WHERE username=?", (name,)).fetchone():
            d.execute("INSERT INTO users(username,email,password_hash,role,api_token) VALUES(?,?,?,?,?)",
                      (name, f"{name}@example.com", generate_password_hash(pw), role, secrets.token_hex(16)))
    d.commit()
    u = {n: d.execute("SELECT * FROM users WHERE username=?", (n,)).fetchone() for n, _, _ in USERS}
    if not d.execute("SELECT 1 FROM incidents").fetchone():
        for t, desc, cat, sev, done, res in SAMPLES:
            iid = A.create_incident(u["rahul"], dict(title=t, description=desc, category=cat, severity=sev))
            if done:
                A.assign_incident(A.get_incident(iid), u["admin"], u["priya"]["id"])
                A.resolve_incident(A.get_incident(iid), u["priya"], res)
        A.assign_incident(A.get_incident(4), u["admin"], u["priya"]["id"])
print("Seeded. Logins: admin/admin123, priya/engineer123, rahul/reporter123")
