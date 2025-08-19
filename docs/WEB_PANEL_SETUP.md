# ?? DtownBeats Web Panel & API Deployment Guide

Comprehensive instructions for enabling and deploying the FastAPI-powered web panel (queues, library, metrics, downloads) with and without Nginx.

> Additional documentation: see `docs/METADATA_SYSTEM.md`, `docs/VOICE_CONTROL.md`, `docs/TROUBLESHOOTING.md`, and `docs/COMMANDS_REFERENCE.md` for deeper feature details.

---
## ?? Features Recap
- FastAPI backend (runs inside bot process)
- Discord OAuth2 (optional) for per-guild access control
- Session-based auth (signed cookies)
- Queue / library pages & multi-format export (JSON, XML, YAML, CSV, TOML)
- Secure per?guild track download + owner global download endpoint
- Health & metrics endpoints for monitoring
- Rate limiting (default 60 req/min/IP)
- Security headers + CSP + optional HSTS

---
## ? Prerequisites
| Requirement | Purpose |
|-------------|---------|
| Python 3.10+ (non?Docker) | Running bot manually |
| FFmpeg | Audio processing |
| Discord Bot | API integration |
| (Optional) Discord OAuth credentials | Web login & access control |
| (Optional) Nginx / Caddy / Traefik | Reverse proxy / TLS |

---
## ?? Environment Variables
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| BOT_TOKEN | ? | — | Discord bot token |
| BOT_OWNER_ID | ? | — | Numeric Discord user ID (owner) |
| SESSION_SECRET | ?? | `change_me_secret` | Session signing key (>=32 random chars recommended) |
| DISCORD_CLIENT_ID | ? | — | OAuth2 client id (enables login) |
| DISCORD_CLIENT_SECRET | ? | — | OAuth2 client secret |
| WEB_PORT | ? | 80 | Internal FastAPI listen port |
| RATE_LIMIT_PER_MIN | ? | 60 | Requests per minute per IP |
| ENABLE_HSTS | ? | 1 | Send HSTS header over HTTPS |
| MUSICBRAINZ_USERAGENT | ? | — | MusicBrainz UA |
| MUSICBRAINZ_VERSION | ? | 1.0 | MusicBrainz version string |
| MUSICBRAINZ_CONTACT | ? | — | Contact email |

---
## ?? Directory Layout (Volumes in Docker)
| Host Dir | Container | Purpose |
|----------|-----------|---------|
| ./music | /app/music | Cached audio |
| ./config | /app/config | Server + metadata configs |
| ./albumart | /app/albumart | Album art cache |
| ./metacache | /app/metacache | Metadata cache |
| ./static | /app/static | Guild icons / static assets |
| ./lyrics | /app/lyrics | Lyrics cache |
| ./models | /app/models | STT models |

---
## ?? Quick Docker Deployment (No Nginx)
1. Create directories:
```bash
mkdir -p music config albumart metacache static lyrics models
```
2. Create `docker-compose.yml` (example):
```yaml
version: '3.8'
services:
  dtownbeats:
    image: angablade/dtownbeats:latest
    container_name: dtownbeats
    restart: unless-stopped
    environment:
      - BOT_TOKEN=YOUR_TOKEN
      - BOT_OWNER_ID=123456789012345678
      - SESSION_SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(48))")
      - WEB_PORT=80
      - RATE_LIMIT_PER_MIN=60
      - MUSICBRAINZ_USERAGENT=dtownbeats
      - MUSICBRAINZ_VERSION=1.1
      - MUSICBRAINZ_CONTACT=you@example.com
      # Optional OAuth
      # - DISCORD_CLIENT_ID=xxxxx
      # - DISCORD_CLIENT_SECRET=xxxxx
    volumes:
      - ./music:/app/music
      - ./config:/app/config
      - ./albumart:/app/albumart
      - ./metacache:/app/metacache
      - ./static:/app/static
      - ./lyrics:/app/lyrics
      - ./models:/app/models
    ports:
      - "3333:80"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```
3. Launch:
```bash
docker compose up -d
```
4. Visit:
- Queues: http://localhost:3333/queues
- Library: http://localhost:3333/library
- Health: http://localhost:3333/health
- Metrics (owner + login): http://localhost:3333/metrics

---
## ?? Updating Docker Image
```bash
docker compose pull
docker compose up -d
docker image prune -f
```

---
## ?? Manual (Bare-Metal) Deployment
1. Clone & install:
```bash
git clone https://github.com/Angablade/DtownBeats.git
cd DtownBeats
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```
2. Create `configs.json` or export environment variables.
3. Run:
```bash
python bot3.py
```
4. Access via: `http://localhost:80/queues` (or chosen WEB_PORT if changed in environment).

---
## ?? Running Behind Nginx (Reverse Proxy + HTTPS)
### 1. Adjust Internal Port (Optional)
Set `WEB_PORT=8000` so container listens on 8000 internally.

### 2. Nginx Site Config Example
```nginx
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header Referrer-Policy no-referrer;

    location /static/ { proxy_pass http://127.0.0.1:8000/static/; }
    location /albumart/ { proxy_pass http://127.0.0.1:8000/albumart/; }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
    }
}
```
### 3. Docker Compose (Internal 8000)
```yaml
services:
  dtownbeats:
    image: angablade/dtownbeats:latest
    environment:
      - WEB_PORT=8000
      - BOT_TOKEN=YOUR_TOKEN
      - BOT_OWNER_ID=123456789012345678
      - SESSION_SECRET=YOUR_RANDOM_SECRET
    network_mode: host
```

### 4. Certbot (if using standalone Nginx)
```bash
sudo certbot --nginx -d example.com
```

---
## ?? OAuth2 Setup
1. Discord Developer Portal ? Your Application ? OAuth2 ? General
2. Add Redirect: `https://example.com/auth` (also http://localhost:3333/auth for local dev)
3. Copy Client ID & Secret ? set DISCORD_CLIENT_ID / DISCORD_CLIENT_SECRET
4. Restart container / process
5. Visit `/login` to begin flow

---
## ?? Testing Health & Metrics
```bash
curl -s http://localhost:3333/health | jq
# After login (browser) visit /metrics
```
Expect JSON fields: guilds, active_queues, now_playing, oauth_configured.

---
## ?? Security Hardening Tips
| Control | Action |
|---------|--------|
| Session Secret | Use >= 48 random chars |
| OAuth | Enforce HTTPS before enabling in production |
| Rate Limit | Tune RATE_LIMIT_PER_MIN (e.g., 120 or 30) |
| CSP | Extend if adding external JS/CSS CDNs |
| HSTS | Leave ENABLE_HSTS=1 when behind HTTPS |
| File Ownership | Run container with non-root (future enhancement) |
| Backups | Backup ./config & ./metacache regularly |

---
## ?? Data Export Examples
| Purpose | URL |
|---------|-----|
| All queues JSON | `/queues?format=json` |
| All queues YAML | `/queues?format=yaml` |
| Single queue TOML | `/queue?guild_id=<id>&format=toml` |
| Queue XML | `/queue?guild_id=<id>&format=xml` |
| Queue CSV | `/queue?guild_id=<id>&format=csv` |

---
## ?? Download Behavior
- Auth required for all download endpoints
- Per-guild: `/download/{guild_id}/{track_id}` if user shares that guild
- Owner global: `/download/owner/{track_id}`
- Track id sanitized (alphanumeric, dash, underscore filtering)

---
## ?? Troubleshooting
| Issue | Check |
|-------|-------|
| 403 on /queues | Not logged in / not in that guild |
| OAuth not working | Redirect URI mismatch in Discord portal |
| 429 errors | Reduce request rate / raise RATE_LIMIT_PER_MIN |
| Missing album art | Ensure /app/albumart volume present |
| Downloads 404 | File not cached yet or wrong ID |
| Health shows oauth_configured=false | Missing DISCORD_CLIENT_ID/SECRET |

---
## ?? Rolling Restart (Docker)
```bash
docker compose restart dtownbeats
```

---
## ?? Summary
You now have a secure, observable, and extensible web interface for DtownBeats that can run standalone or behind a production reverse proxy with TLS. Customize rate limits, headers, and OAuth as needed.

Enjoy the music! ??
