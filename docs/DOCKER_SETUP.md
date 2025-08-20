# DtownBeats Docker Setup Guide

## Quick Start

1. **Copy the Docker Compose file** and update the paths and environment variables:

```yaml
version: '3.8'

services:
  dtownbeats:
    image: angablade/dtownbeats:latest
    container_name: dtownbeats
    volumes:
      - ./lyrics:/app/lyrics
      - ./music:/app/music
      - ./config:/app/config
      - ./models:/app/models
      - ./albumart:/app/albumart
      - ./metacache:/app/metacache
      - ./static:/app/static
    environment:
      # REQUIRED: Get your bot token from https://discord.com/developers/applications
      - BOT_TOKEN=YOUR_BOT_TOKEN_HERE
      - BOT_OWNER_ID=YOUR_DISCORD_USER_ID
      
      # IMPORTANT: Change this for security!
      - SESSION_SECRET=your_very_secure_random_string_here_at_least_32_chars
      
      # Optional: For Discord OAuth login to web panel
      - DISCORD_CLIENT_ID=your_discord_app_client_id
      - DISCORD_CLIENT_SECRET=your_discord_app_client_secret
      
      # MusicBrainz (required for metadata)
      - MUSICBRAINZ_USERAGENT=dtownbeats
      - MUSICBRAINZ_VERSION=1.1
      - MUSICBRAINZ_CONTACT=youremail@example.com
      
      # Performance settings (optional)
      - EXECUTOR_MAX_WORKERS=10
      - QUEUE_PAGE_SIZE=10
      - HISTORY_PAGE_SIZE=10
      - TIMEOUT_TIME=60
      - WEB_PORT=80
    ports:
      - "3333:80"  # Access web panel at http://localhost:3333
    dns:
      - 8.8.8.8
      - 1.1.1.1
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - dtownbeats_network

networks:
  dtownbeats_network:
    driver: bridge
```

2. **Create the required directories**:
```bash
mkdir -p lyrics music config models albumart metacache static
```

3. **Set up your Discord bot**:
   - Go to https://discord.com/developers/applications
   - Create a new application
   - Go to the "Bot" section and create a bot
   - Copy the bot token and set it as `BOT_TOKEN`
   - Get your Discord user ID and set it as `BOT_OWNER_ID`

4. **Generate a secure session secret**:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

5. **Optional: Set up Discord OAuth for web panel**:
   - In your Discord application, go to OAuth2 ? General
   - Add redirect URL: `http://your-domain:3333/auth`
   - Copy Client ID and Client Secret

6. **Start the bot**:
```bash
docker-compose up -d
```

7. **Check the logs**:
```bash
docker-compose logs -f dtownbeats
```

## Web Panel Access

Once running, you can access:

- **Health Check**: http://localhost:3333/health
- **Web Panel**: http://localhost:3333/queues
- **Music Library**: http://localhost:3333/library
- **Metrics** (owner only): http://localhost:3333/metrics

## Discord Commands

New admin commands for monitoring:

- `!health` - Get bot health status (owner only)
- `!metrics` - Get detailed system metrics (owner only)
- `!webpanel` - Get web panel information (owner only)

## Environment Variables Explained

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | ? | Discord bot token |
| `BOT_OWNER_ID` | ? | Your Discord user ID |
| `SESSION_SECRET` | ?? | Web panel session encryption (change from default!) |
| `DISCORD_CLIENT_ID` | ? | For Discord OAuth login |
| `DISCORD_CLIENT_SECRET` | ? | For Discord OAuth login |
| `MUSICBRAINZ_USERAGENT` | ? | Your app name for MusicBrainz API |
| `MUSICBRAINZ_CONTACT` | ? | Your email for MusicBrainz API |
| `WEB_PORT` | ? | Web server port (default: 80) |
| `EXECUTOR_MAX_WORKERS` | ? | Max download threads (default: 10) |
| `TIMEOUT_TIME` | ? | Voice channel timeout (default: 60 seconds) |

## Security Notes

?? **IMPORTANT**: Change `SESSION_SECRET` from the default value for security!

? **Recommended**: Set up Discord OAuth for secure web panel access

?? **Never share**: Your bot token or client secret publicly

## Troubleshooting

### Health Check Failing
```bash
curl http://localhost:3333/health
```

### Check Container Status
```bash
docker-compose ps
docker-compose logs dtownbeats
```

### Update Bot
```bash
docker-compose pull
docker-compose up -d
```

### Reset Everything
```bash
docker-compose down -v
docker-compose up -d
```