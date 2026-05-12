# DPMBG — Operations Runbook

Cara deploy, restart, debug, backup, restore. Untuk ops/admin server.

---

## Server Layout

- **Host:** `72.60.196.21` (Aureonforge VPS)
- **Domain:** `https://dapurpintarmbg.aureonforge.com`
- **Project root:** `/root/projects/dpmbg/` (sesuaikan kalau beda)
- **DB:** Supabase PostgreSQL (eu-west-1 pooler), URL di `.env` `DATABASE_URL`
- **Frontend:** Vite static build di `frontend/dist/`, served by FastAPI
- **Backend:** Uvicorn FastAPI, port 8001 (di-proxy oleh nginx)

---

## Deploy

### Option A — via Claude deployer agent
```
/dpmbg-deployer
```
(Slash command — autoconfigured, baca `.claude/agents/dpmbg-deployer.md`)

### Option B — manual deploy
```bash
ssh root@72.60.196.21
cd /root/projects/dpmbg/
git pull
cd frontend && npm ci && npm run build && cd ..
pip install -r requirements.txt
sudo systemctl restart dpmbg-backend  # atau equivalent
```

### Verify deploy
```bash
curl https://dapurpintarmbg.aureonforge.com/health/deep
# expect: {"status":"ok","app":"ok","db":"ok","db_latency_ms": <number>}
```

---

## Start / Stop / Restart

### Local dev (Windows)
```bash
# Backend
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8001
# Frontend (separate terminal)
cd frontend && npm run dev
```

### Production (systemd — recommended)

Create `/etc/systemd/system/dpmbg-backend.service`:
```ini
[Unit]
Description=DPMBG FastAPI Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/projects/dpmbg
EnvironmentFile=/root/projects/dpmbg/.env
ExecStart=/usr/bin/python3 -m uvicorn backend.app:app --host 0.0.0.0 --port 8001 --workers 2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable dpmbg-backend
systemctl start dpmbg-backend
systemctl status dpmbg-backend
```

### Nginx reverse proxy (snippet)

`/etc/nginx/sites-available/dpmbg`:
```nginx
server {
    listen 443 ssl http2;
    server_name dapurpintarmbg.aureonforge.com;

    ssl_certificate     /etc/letsencrypt/live/dapurpintarmbg.aureonforge.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dapurpintarmbg.aureonforge.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name dapurpintarmbg.aureonforge.com;
    return 301 https://$host$request_uri;
}
```

---

## Backup

### Manual backup
```bash
# Dump full Supabase DB (set DATABASE_URL first)
pg_dump "$DATABASE_URL" > /backups/dpmbg-$(date +%Y%m%d-%H%M).sql
gzip /backups/dpmbg-$(date +%Y%m%d-%H%M).sql
```

### Daily auto-backup (cron)
```bash
crontab -e
# Add:
0 2 * * * pg_dump "$DATABASE_URL" | gzip > /backups/dpmbg-$(date +\%Y\%m\%d).sql.gz
0 3 * * 0 find /backups -name "dpmbg-*.sql.gz" -mtime +30 -delete
```

### Upload backup to S3 / Google Drive
```bash
# rclone option (configure once: rclone config)
rclone copy /backups/dpmbg-$(date +%Y%m%d).sql.gz drive:dpmbg-backups/
```

---

## Restore

```bash
# Test restore di staging (NOT production)
gunzip -c /backups/dpmbg-20260425.sql.gz | psql "$STAGING_DATABASE_URL"

# Verify
psql "$STAGING_DATABASE_URL" -c "SELECT count(*) FROM users;"
```

**WARNING:** Restore ke production = DESTRUCTIVE. Backup dulu sebelum restore.

---

## Debug

### Backend not responding
```bash
# Check process alive
systemctl status dpmbg-backend

# Check port listening
ss -tlnp | grep :8001

# Check recent logs
journalctl -u dpmbg-backend -n 100 --no-pager
tail -f /root/projects/dpmbg/logs/dpmbg.log
```

### DB connection issues
```bash
# Test connectivity
psql "$DATABASE_URL" -c "SELECT 1"

# Check Supabase pooler stats
# https://app.supabase.com → Project → Database → Pooler
```

### High latency
```bash
# Deep health shows DB latency
curl https://dapurpintarmbg.aureonforge.com/health/deep

# If db_latency_ms > 500: check Supabase region (eu-west-1 from VPS Indonesia adds ~200ms)
# Migration plan: move DB ke ap-southeast region
```

### Frontend stuck on loading
```bash
# Clear browser PWA cache (DevTools → Application → Clear storage)
# Or rebuild + clear service worker cache
cd frontend && rm -rf dist/ && npm run build
```

### "Method Not Allowed" on /api/login
This usually means Vite hijacked the backend port. Check:
```bash
ss -tlnp | grep -E ":(5173|8001)"
# Backend should be 8001, frontend 5173. If backend is on a different port, check systemd unit ExecStart.
```

---

## Monitoring

### Manual checks
```bash
# Daily
curl -fsS https://dapurpintarmbg.aureonforge.com/health/deep | jq

# Weekly
psql "$DATABASE_URL" -c "
  SELECT action, count(*)
  FROM audit_log
  WHERE created_at > now() - interval '7 days'
  GROUP BY action ORDER BY count DESC;
"

# Disk usage
df -h /
du -sh /root/projects/dpmbg/logs/
```

### Recommended external monitoring (free tier)
- **UptimeRobot** — ping `/health/deep` every 5 min, email alert kalau 503/timeout
- **Better Stack** — alternative dengan log retention
- **Healthchecks.io** — cron-job heartbeat (kalau pakai cron)

---

## Audit Log Inspection

```sql
-- Recent failed logins (potential brute force)
SELECT created_at, ip_address, details
FROM audit_log
WHERE action = 'login.fail'
  AND created_at > now() - interval '24 hours'
ORDER BY created_at DESC LIMIT 20;

-- All user creations this month
SELECT created_at, user_id, target_id, details
FROM audit_log
WHERE action = 'user.create'
  AND created_at > now() - interval '30 days'
ORDER BY created_at DESC;

-- Per-kitchen activity volume
SELECT kitchen_id, action, count(*)
FROM audit_log
WHERE created_at > now() - interval '7 days'
GROUP BY kitchen_id, action
ORDER BY kitchen_id, count DESC;
```

---

## Common Operations

### Reset user password
```bash
# Via UI: login as admin → /admin/users → Reset pw → input min 8 chars
# Via DB (emergency only):
psql "$DATABASE_URL" -c "
  UPDATE users SET password_hash = '\$2b\$12\$...' WHERE username = 'someuser';
"
# (generate hash via: python -c "import bcrypt; print(bcrypt.hashpw(b'newpass', bcrypt.gensalt()).decode())")
```

### Rotate scanner / printer key
```bash
# Via UI: login as kitchen admin → /admin/kitchens → Edit → Rotate
# Old keys invalidated immediately; update scanner/printer device config
```

### Clear price scrape cache
```bash
# In-memory cache (TKPI). Restart backend to refresh.
systemctl restart dpmbg-backend
```

### Trigger manual price scrape
```bash
# Via UI: login as accountant/admin → /menu-planner → "Scrape All"
# Or curl:
curl -X POST -H "Authorization: Bearer $TOKEN" \
  https://dapurpintarmbg.aureonforge.com/api/menu/prices/scrape
```

---

## Rollback

```bash
# Quick rollback to previous git commit
cd /root/projects/dpmbg
git log --oneline -5  # find previous SHA
git checkout <previous-sha>
cd frontend && npm run build && cd ..
systemctl restart dpmbg-backend

# Verify
curl -fsS https://dapurpintarmbg.aureonforge.com/health/deep
```

If DB schema has changed, may need restore from backup before code rollback.

---

## Emergency Contacts

- **Server admin:** (TODO — add)
- **Database (Supabase):** https://app.supabase.com
- **Domain (Aureonforge):** (TODO — add registrar)
- **Original developer:** owenjacobn@gmail.com
