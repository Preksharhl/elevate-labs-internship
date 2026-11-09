import os, sqlite3, secrets, smtplib, logging
from datetime import datetime
from email.message import EmailMessage
from functools import wraps
from flask import (Flask, g, request, session, redirect, url_for,
                   render_template, flash, jsonify, abort)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-change-me")
DB = os.getenv("DATABASE", "incidents.db")
ROLES = ("admin", "engineer", "reporter")
STATUSES = ("open", "investigating", "resolved")
SEVERITIES = ("low", "medium", "high", "critical")
CATEGORIES = ("infrastructure", "application", "network", "security", "database")
log = logging.getLogger("incidents")
logging.basicConfig(level=logging.INFO)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, email TEXT NOT NULL,
  password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'reporter', api_token TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS incidents(
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT, category TEXT,
  severity TEXT NOT NULL DEFAULT 'medium', status TEXT NOT NULL DEFAULT 'open',
  reporter_id INTEGER NOT NULL, assignee_id INTEGER, resolution TEXT,
  created_at TEXT, updated_at TEXT, resolved_at TEXT);
CREATE TABLE IF NOT EXISTS comments(
  id INTEGER PRIMARY KEY, incident_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
  body TEXT NOT NULL, is_event INTEGER DEFAULT 0, created_at TEXT);
"""
BASE_Q = ("SELECT i.*, r.username AS reporter, a.username AS assignee FROM incidents i "
          "JOIN users r ON r.id=i.reporter_id LEFT JOIN users a ON a.id=i.assignee_id ")


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


def init_db():
    with app.app_context():
        db().executescript(SCHEMA)
        db().commit()


def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M")


# ---------- auth ----------
def current_user():
    if "user" not in g:
        u = None
        token = request.headers.get("X-API-Token")
        if token:
            u = db().execute("SELECT * FROM users WHERE api_token=?", (token,)).fetchone()
        elif session.get("uid"):
            u = db().execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()
        g.user = u
    return g.user


def login_required(*roles):
    def deco(f):
        @wraps(f)
        def wrapper(*a, **kw):
            u = current_user()
            is_api = request.path.startswith("/api/")
            if not u:
                return (jsonify(error="authentication required"), 401) if is_api else redirect(url_for("login"))
            if roles and u["role"] not in roles:
                return (jsonify(error="forbidden for your role"), 403) if is_api else abort(403)
            return f(*a, **kw)
        return wrapper
    return deco


@app.context_processor
def inject():
    return dict(me=current_user(), SEVERITIES=SEVERITIES, STATUSES=STATUSES,
                CATEGORIES=CATEGORIES, ROLES=ROLES)


# ---------- email ----------
def notify(subject, body, user_ids):
    rows = [db().execute("SELECT email FROM users WHERE id=?", (i,)).fetchone() for i in set(user_ids) if i]
    to = [r["email"] for r in rows if r]
    if not to:
        return
    host = os.getenv("SMTP_HOST")
    if not host:
        log.info("[email disabled] To=%s | %s", to, subject)
        return
    try:
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = f"[IMS] {subject}", os.getenv("MAIL_FROM", "ims@example.com"), ", ".join(to)
        msg.set_content(body)
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", 587)), timeout=10) as s:
            s.starttls()
            if os.getenv("SMTP_USER"):
                s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS", ""))
            s.send_message(msg)
    except Exception as e:  # never break a request because of email
        log.error("email failed: %s", e)


# ---------- domain logic (shared by UI + API) ----------
def get_incident(iid):
    row = db().execute(BASE_Q + "WHERE i.id=?", (iid,)).fetchone()
    if not row:
        abort(404)
    return row


def event(iid, uid, text, is_event=1):
    db().execute("INSERT INTO comments(incident_id,user_id,body,is_event,created_at) VALUES(?,?,?,?,?)",
                 (iid, uid, text, is_event, now()))


def create_incident(u, d):
    title = (d.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")
    sev = d.get("severity", "medium")
    if sev not in SEVERITIES:
        raise ValueError(f"severity must be one of {SEVERITIES}")
    cur = db().execute(
        "INSERT INTO incidents(title,description,category,severity,reporter_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        (title, d.get("description", ""), d.get("category", "application"), sev, u["id"], now(), now()))
    iid = cur.lastrowid
    event(iid, u["id"], f"Incident reported with severity {sev}")
    db().commit()
    staff = [r["id"] for r in db().execute("SELECT id FROM users WHERE role IN ('admin','engineer')")]
    notify(f"New {sev} incident #{iid}: {title}", f"{u['username']} reported: {title}\n\n{d.get('description','')}", staff)
    return iid


def update_incident(inc, u, d):
    sets, vals = [], []
    for f, allowed in (("severity", SEVERITIES), ("status", STATUSES[:2]), ("category", CATEGORIES)):
        if f in d and d[f] != inc[f]:
            if d[f] not in allowed:
                raise ValueError(f"invalid {f}; use {allowed}")
            sets.append(f"{f}=?"); vals.append(d[f])
            event(inc["id"], u["id"], f"{f} changed: {inc[f]} → {d[f]}")
    for f in ("title", "description"):
        if f in d and d[f]:
            sets.append(f"{f}=?"); vals.append(d[f])
    if sets:
        db().execute(f"UPDATE incidents SET {','.join(sets)}, updated_at=? WHERE id=?", (*vals, now(), inc["id"]))
        db().commit()


def assign_incident(inc, u, assignee_id):
    a = db().execute("SELECT * FROM users WHERE id=? AND role IN ('admin','engineer')", (assignee_id,)).fetchone()
    if not a:
        raise ValueError("assignee must be an existing engineer/admin")
    status = "investigating" if inc["status"] == "open" else inc["status"]
    db().execute("UPDATE incidents SET assignee_id=?, status=?, updated_at=? WHERE id=?", (a["id"], status, now(), inc["id"]))
    event(inc["id"], u["id"], f"Assigned to {a['username']}")
    db().commit()
    notify(f"Incident #{inc['id']} assigned to you", f"{inc['title']} ({inc['severity']})", [a["id"]])


def resolve_incident(inc, u, resolution):
    if not (resolution or "").strip():
        raise ValueError("resolution notes are required")
    db().execute("UPDATE incidents SET status='resolved', resolution=?, resolved_at=?, updated_at=? WHERE id=?",
                 (resolution.strip(), now(), now(), inc["id"]))
    event(inc["id"], u["id"], "Resolved: " + resolution.strip())
    db().commit()
    notify(f"Incident #{inc['id']} resolved", f"{inc['title']}\n\nResolution: {resolution}", [inc["reporter_id"]])


def list_incidents(args):
    q, vals = BASE_Q + "WHERE 1=1", []
    for f in ("status", "severity", "category"):
        if args.get(f):
            q += f" AND i.{f}=?"; vals.append(args[f])
    if args.get("q"):
        q += " AND i.title LIKE ?"; vals.append(f"%{args['q']}%")
    return db().execute(q + " ORDER BY i.id DESC", vals).fetchall()


# ---------- REST API ----------
def can_manage(u):
    return u["role"] in ("admin", "engineer")


def api(fn):
    @wraps(fn)
    def w(*a, **kw):
        try:
            return fn(*a, **kw)
        except ValueError as e:
            return jsonify(error=str(e)), 400
    return w


@app.get("/api/incidents")
@login_required()
def api_list():
    return jsonify([dict(r) for r in list_incidents(request.args)])


@app.post("/api/incidents")
@login_required()
@api
def api_create():
    iid = create_incident(current_user(), request.get_json(force=True, silent=True) or {})
    return jsonify(dict(get_incident(iid))), 201


@app.get("/api/incidents/<int:iid>")
@login_required()
def api_get(iid):
    out = dict(get_incident(iid))
    out["timeline"] = [dict(c) for c in db().execute(
        "SELECT c.*, u.username FROM comments c JOIN users u ON u.id=c.user_id WHERE incident_id=? ORDER BY c.id", (iid,))]
    return jsonify(out)


@app.put("/api/incidents/<int:iid>")
@login_required("admin", "engineer")
@api
def api_update(iid):
    update_incident(get_incident(iid), current_user(), request.get_json(force=True, silent=True) or {})
    return jsonify(dict(get_incident(iid)))


@app.post("/api/incidents/<int:iid>/assign")
@login_required("admin", "engineer")
@api
def api_assign(iid):
    assign_incident(get_incident(iid), current_user(), (request.get_json(silent=True) or {}).get("assignee_id"))
    return jsonify(dict(get_incident(iid)))


@app.post("/api/incidents/<int:iid>/resolve")
@login_required("admin", "engineer")
@api
def api_resolve(iid):
    resolve_incident(get_incident(iid), current_user(), (request.get_json(silent=True) or {}).get("resolution"))
    return jsonify(dict(get_incident(iid)))


@app.post("/api/incidents/<int:iid>/comments")
@login_required()
@api
def api_comment(iid):
    get_incident(iid)
    body = ((request.get_json(silent=True) or {}).get("body") or "").strip()
    if not body:
        raise ValueError("body is required")
    event(iid, current_user()["id"], body, 0)
    db().commit()
    return jsonify(ok=True), 201


@app.get("/api/token")
@login_required()
def api_token():
    return jsonify(api_token=current_user()["api_token"])


# ---------- web UI ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        if len(f["password"]) < 6:
            flash("Password must be at least 6 characters.", "danger")
        else:
            first = db().execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
            try:
                db().execute("INSERT INTO users(username,email,password_hash,role,api_token) VALUES(?,?,?,?,?)",
                             (f["username"].strip(), f["email"].strip(), generate_password_hash(f["password"]),
                              "admin" if first else "reporter", secrets.token_hex(16)))
                db().commit()
                flash("Account created. Please sign in." + (" You are the admin." if first else ""), "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Username already taken.", "danger")
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db().execute("SELECT * FROM users WHERE username=?", (request.form["username"],)).fetchone()
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session["uid"] = u["id"]
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.", "danger")
    return render_template("auth.html", mode="login")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@login_required()
def dashboard():
    stats = {s: db().execute("SELECT COUNT(*) FROM incidents WHERE status=?", (s,)).fetchone()[0] for s in STATUSES}
    stats["critical"] = db().execute("SELECT COUNT(*) FROM incidents WHERE severity='critical' AND status!='resolved'").fetchone()[0]
    return render_template("dashboard.html", incidents=list_incidents(request.args), stats=stats, f=request.args)


@app.route("/incidents/new", methods=["GET", "POST"])
@login_required()
def new_incident():
    if request.method == "POST":
        try:
            iid = create_incident(current_user(), request.form)
            flash("Incident logged.", "success")
            return redirect(url_for("detail", iid=iid))
        except ValueError as e:
            flash(str(e), "danger")
    return render_template("new.html")


@app.get("/incidents/<int:iid>")
@login_required()
def detail(iid):
    timeline = db().execute("SELECT c.*, u.username FROM comments c JOIN users u ON u.id=c.user_id "
                            "WHERE incident_id=? ORDER BY c.id", (iid,)).fetchall()
    staff = db().execute("SELECT id, username FROM users WHERE role IN ('admin','engineer')").fetchall()
    return render_template("detail.html", i=get_incident(iid), timeline=timeline, staff=staff,
                           manage=can_manage(current_user()))


@app.post("/incidents/<int:iid>/<action>")
@login_required()
def incident_action(iid, action):
    u, inc = current_user(), get_incident(iid)
    try:
        if action == "comment":
            if request.form["body"].strip():
                event(iid, u["id"], request.form["body"].strip(), 0); db().commit()
        elif not can_manage(u):
            abort(403)
        elif action == "update":
            update_incident(inc, u, request.form)
        elif action == "assign":
            assign_incident(inc, u, request.form.get("assignee_id"))
        elif action == "resolve":
            resolve_incident(inc, u, request.form.get("resolution"))
        else:
            abort(404)
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("detail", iid=iid))


@app.route("/admin/users", methods=["GET", "POST"])
@login_required("admin")
def users():
    if request.method == "POST" and request.form["role"] in ROLES:
        db().execute("UPDATE users SET role=? WHERE id=?", (request.form["role"], request.form["user_id"]))
        db().commit()
        flash("Role updated.", "success")
    return render_template("users.html", users=db().execute("SELECT * FROM users").fetchall())


@app.errorhandler(403)
def forbidden(_):
    return render_template("auth.html", mode="forbidden"), 403


init_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=os.getenv("FLASK_DEBUG") == "1")
