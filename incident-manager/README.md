# Open-Source Incident Management System

A lightweight portal to **log, track, assign and resolve** infrastructure/application incidents, with role-based access, a REST API, SMTP email notifications and Docker support.

**Stack:** Python 3.12 · Flask · SQLite · Bootstrap 5 · Docker · Git

## Roles
| Role | Can do |
|---|---|
| reporter | log incidents, comment, view all |
| engineer | + update, assign, resolve |
| admin | + manage user roles (first registered user is admin) |

## Run locally
```bash
pip install -r requirements.txt
python seed.py        # optional demo data
python app.py         # http://localhost:5000
```
Demo logins: `admin/admin123`, `priya/engineer123`, `rahul/reporter123`

## Run with Docker
```bash
docker compose up --build        # or: docker build -t ims . && docker run -p 5000:5000 ims
docker compose exec ims python seed.py
```

## Email (SMTP)
Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `MAIL_FROM` in `.env`. Emails are sent on new incident (staff), assignment (assignee) and resolution (reporter). Without `SMTP_HOST`, emails are logged to the console.

## REST API
Auth: session cookie or header `X-API-Token: <token>` (get yours from `GET /api/token` while logged in).

| Method | Endpoint | Role |
|---|---|---|
| GET | `/api/incidents?status=&severity=&category=&q=` | any |
| POST | `/api/incidents` `{title, description, severity, category}` | any |
| GET | `/api/incidents/<id>` (with timeline) | any |
| PUT | `/api/incidents/<id>` | engineer/admin |
| POST | `/api/incidents/<id>/assign` `{assignee_id}` | engineer/admin |
| POST | `/api/incidents/<id>/resolve` `{resolution}` | engineer/admin |
| POST | `/api/incidents/<id>/comments` `{body}` | any |

```bash
curl -X POST localhost:5000/api/incidents -H "X-API-Token: TOKEN" \
  -H "Content-Type: application/json" -d '{"title":"DB down","severity":"critical"}'
```
