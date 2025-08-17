# 🎵 Discord Music Bot

A powerful, feature-rich, and customizable music bot for Discord! Built with Python and **py-cord** (a maintained fork of discord.py), this bot delivers high-quality audio streaming, playlist support, and intuitive controls directly to your server.

---

## 🚀 Features

### 🎶 **Music Playback**

- Stream music from YouTube, YouTube Music, and direct audio URLs.
- Full support for YouTube playlists.
- Displays track details while playing.
- Automatic caching for smooth playback.

### 📜 **Queue Management**

- Add multiple tracks to the queue.
- View the queue with pagination.
- Remove specific tracks from the queue.
- Shuffle and reorder queue items.

### ⏯ **Playback Controls**

- Pause, resume, and stop playback.
- Skip tracks instantly.
- Seek to specific timestamps.
- Adjust volume (0-200%).
- Enable or disable track looping.

### 📢 **Voice Channel Handling**

- Joins and leaves voice channels automatically.
- Reconnects if disconnected unexpectedly.
- Smart timeout handling (30 seconds after playback ends or channel becomes empty).
- Only responds to commands from designated users and channels (configurable).

### 🎤 **Lyrics Integration**

- Fetches lyrics for the currently playing song or user-specified track.
- Uses MusicBrainz for accurate metadata.

### 🔧 **Server Customization**

- Customizable command prefix per server.
- Assign a DJ role for exclusive music control.
- Lock bot commands to a specific text channel.

### 🔗 **Utility Commands**

- Displays a list of available commands.
- Invite link generation.
- Admin-only bot shutdown and reboot commands.

---

## 🆕 Recent Enhancements

### 🔐 **Enhanced Web Panel & API**
- **FastAPI-powered web panel** with comprehensive monitoring and control features.
- **Multi-format export** (JSON, XML, YAML, CSV, TOML) for `/queue` and `/queues` endpoints.
- **Discord OAuth2 login** with session-based access control and security headers.
- **Per-guild authorization** – users only see queues for guilds they share with the bot.
- **Secure file downloads** for cached tracks (authorized users only / owner global access).
- **Advanced library search** with pagination, filtering by title/artist/ID.
- **Health monitoring** and **system metrics** endpoints.
- **Rate limiting** (60 requests/minute) for API protection.

### 🏥 **Health & Monitoring System**
- **Real-time health checks** via `/health` endpoint for Docker and monitoring systems.
- **Detailed system metrics** including CPU, memory, disk, and network usage.
- **Bot performance monitoring** with queue statistics and guild activity.
- **Discord commands** for bot owners to access health and metrics data directly.
- **Web panel integration** with monitoring dashboards.

### 🗂 **Advanced Metadata System**
- **Persistent metadata cache** with auto-fetch & MusicBrainz enrichment.
- **Owner/editor role system** to manually fetch, set, and clean metadata.
- **Album art fetcher** with embedding in now playing messages & web panel.
- **Multi-source metadata** from MusicBrainz, YouTube, and other providers.

### 🤖 **Voice Control (Experimental)**
- **Coqui STT integration** for voice command recognition inside voice channels.
- **Commands triggered with hot phrase**: "Music bot <command>" (e.g., *Music bot play daft punk*).
- **Voice-activated playback controls** for hands-free operation.

### 🔄 **Robust Voice Connection Handling**
- **Safe connect wrapper** with retry logic & cooldown to mitigate gateway issues.
- **Auto-resume functionality** after reconnects with volume reapplication.
- **Smart timeout handling** (30 seconds after inactivity or empty channels).
- **Autoplay system** for related YouTube tracks when queue becomes empty (optional per guild).

### 🧠 **Queue Intelligence**
- **Pre-download system** (preload) of upcoming tracks to minimize playback gaps.
- **Track history per guild** (recent 20) exposed in commands & web interface.
- **Duplicate & similarity filtering** when selecting related autoplay tracks.
- **Queue backup & restore** functionality (guild or global scope).

### 🛡 **Enhanced Moderation & Access Controls**
- **Blacklist/whitelist system** for banned titles with fuzzy matching & hard-coded filters.
- **Per-guild DJ role** & command channel restrictions.
- **User ban system** for bot usage control.
- **Session security** with configurable SESSION_SECRET for web panel.

### 🧰 **Comprehensive Admin Utilities**
- **Queue backup & restore** (guild or global scope).
- **Bulk queue management** - purge all queues across guilds.
- **Dynamic yt-dlp updater** command for keeping dependencies current.
- **Log retrieval** with compression & multipart splitting (7z volumes) for large logs.
- **Global messaging system** to broadcast to all reachable guilds.
- **Remote control capabilities** with guild/channel targeting.

### 🎛 **Enhanced Playback & UX**
- **Advanced seeking** - percentage & timestamp seeking (e.g., 1:30 or 50%).
- **Volume persistence** per guild (0–200%) with automatic reapplication.
- **Full playback controls** - loop toggle, shuffle, move, remove, clear, history recall.
- **Intelligent message handling** with chunking and file splitting for Discord limits.
- **Smart file delivery** with automatic compression for large downloads.

### 🐳 **Production-Ready Docker Support**
- **Complete Docker Compose setup** with health checks and proper volume mappings.
- **Environment variable management** with comprehensive configuration options.
- **Security hardening** with proper secrets management and network isolation.
- **Automatic updates** via configurable init script with fallback mechanisms.

---

## 📦 Installation

### 🐳 **Docker Setup (Recommended)**

1. **Download the Docker Compose file** and create your environment:
   ```bash
   curl -O https://raw.githubusercontent.com/Angablade/DtownBeats/master/Docker%20Compose.yml
   ```

2. **Create required directories**:
   ```bash
   mkdir -p lyrics music config models albumart metacache static
   ```

3. **Configure environment variables** in `Docker Compose.yml`:
   ```yaml
   environment:
     # REQUIRED: Get from https://discord.com/developers/applications
     - BOT_TOKEN=YOUR_BOT_TOKEN_HERE
     - BOT_OWNER_ID=YOUR_DISCORD_USER_ID
     
     # SECURITY: Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
     - SESSION_SECRET=your_very_secure_random_string_here_at_least_32_chars
     
     # OPTIONAL: For Discord OAuth web login
     - DISCORD_CLIENT_ID=your_discord_app_client_id
     - DISCORD_CLIENT_SECRET=your_discord_app_client_secret
     
     # METADATA: Required for song information
     - MUSICBRAINZ_USERAGENT=dtownbeats
     - MUSICBRAINZ_CONTACT=youremail@example.com
   ```

4. **Start the bot**:
   ```bash
   docker-compose up -d
   ```

5. **Access the web panel**:
   - **Main Interface**: http://localhost:3333/queues
   - **Health Check**: http://localhost:3333/health
   - **Music Library**: http://localhost:3333/library
   - **System Metrics**: http://localhost:3333/metrics (owner only)

#### 📂 **Volume Mappings**

- `/app/lyrics` → Stores lyrics data
- `/app/music` → Stores downloaded music files
- `/app/config` → Stores server configurations and backups
- `/app/models` → Stores AI models for voice recognition
- `/app/albumart` → Stores album artwork cache
- `/app/metacache` → Stores metadata cache
- `/app/static` → Stores guild icons and static files

The bot includes automatic health checks and will restart unless stopped manually.

---

### 🛠 **Manual Installation**

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Angablade/DtownBeats.git
   cd DtownBeats
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Create configuration file** (`configs.json`):
   ```json
   {
     "BOT_TOKEN": "your_discord_bot_token",
     "MUSICBRAINZ_USERAGENT": "YourBotName/1.0",
     "MUSICBRAINZ_VERSION": "1.0",
     "MUSICBRAINZ_CONTACT": "your_email@example.com",
     "BOT_OWNER_ID": 123456789012345678,
     "EXECUTOR_MAX_WORKERS": 10,
     "QUEUE_PAGE_SIZE": 10,
     "HISTORY_PAGE_SIZE": 10,
     "TIMEOUT_TIME": 60,
     "WEB_PORT": 80,
     "SESSION_SECRET": "your_secure_session_secret",
     "DISCORD_CLIENT_ID": "your_discord_app_client_id",
     "DISCORD_CLIENT_SECRET": "your_discord_app_client_secret"
   }
   ```

4. **Run the bot**:
   ```bash
   python bot3.py
   ```

---

## 🛠 Configuration

### **Server-Specific Settings**

Edit `config/server_config.json` to adjust per-guild settings:

- **Prefix** (`!` by default) - Customize command prefix
- **DJ Role** - Restrict music commands to specific roles
- **Command Channel** - Limit bot commands to designated text channels
- **Autoplay** - Enable/disable automatic related track playback

### **Environment Variables**

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BOT_TOKEN` | ✅ | — | Discord bot token |
| `BOT_OWNER_ID` | ✅ | — | Discord user ID for admin access |
| `SESSION_SECRET` | ⚠️ | `change_me_secret` | Web panel session encryption |
| `DISCORD_CLIENT_ID` | ❌ | — | Discord OAuth client ID |
| `DISCORD_CLIENT_SECRET` | ❌ | — | Discord OAuth client secret |
| `MUSICBRAINZ_USERAGENT` | ✅ | — | User agent for MusicBrainz API |
| `MUSICBRAINZ_CONTACT` | ✅ | — | Contact email for MusicBrainz |
| `WEB_PORT` | ❌ | `80` | Web server port |
| `EXECUTOR_MAX_WORKERS` | ❌ | `10` | Max concurrent download threads |
| `TIMEOUT_TIME` | ❌ | `60` | Voice channel timeout (seconds) |

---

## 🖥 **Complete Commands Reference**

Below is the comprehensive command catalog (default prefix: `!`). Aliases shown in parentheses.

### 🎵 **Playback & Queue Management**
| Command | Aliases | Description |
|---------|---------|-------------|
| `play <query/link>` | — | Play music (YouTube search, direct URL, or external links) |
| `youtube <query/link>` | `yt` | Explicit YouTube/playlist handler |
| `grablist <query>` | `grabplaylist` | Smart playlist search + bulk add to queue |
| `queue [page]` | `list` | Show queued tracks with pagination |
| `nowplaying` | `current`, `np` | Show current track with metadata and album art |
| `history` | `played` | Show recently played tracks (last 20) |
| `skip` | `next` | Skip to next track |
| `pause` | `hold` | Pause current playback |
| `resume` | `continue` | Resume paused playback |
| `stop` | — | Stop playback and clear queue |
| `seek <time>` | — | Seek to position (mm:ss, percentage, or seconds) |
| `loop` | `repeat` | Toggle track looping |
| `shuffle` | — | Randomize queue order |
| `remove <index>` | — | Remove specific track from queue |
| `clear` | — | Clear entire queue |
| `move <from> <to>` | — | Reorder tracks in queue |
| `autoplay <on/off>` | `autodj` | Toggle related-track autoplay |
| `volume <0-200>` | `vol` | Set and persist guild volume |
| `mute` | `quiet` | Toggle pause/resume (soft mute) |
| `join` | `come` | Join your current voice channel |
| `leave` | `go` | Leave voice channel |
| `sendplox` | `dlfile` | DM current track file (with compression if large) |

### 🌐 **External Source Integration**
| Command | Aliases | Description |
|---------|---------|-------------|
| `bandcamp <url>` | `bc` | Queue track from Bandcamp |
| `soundcloud <url>` | `sc` | Queue track from SoundCloud |
| `spotify <url>` | `sp` | Convert Spotify track/playlist via YouTube Music |
| `applemusic <url>` | `ap` | Queue track from Apple Music |

### 📝 **Metadata & Lyrics Management**
| Command | Aliases | Description |
|---------|---------|-------------|
| `lyrics [song]` | `lyr` | Fetch lyrics for current or specified track |
| `getmetadata <id>` | — | Display cached metadata in JSON format |
| `fetchmetadata <id> <query>` | — | Force refresh metadata from external sources |
| `setmetadata <id> <key> <value>` | — | Manually edit metadata fields |
| `clean <id>` | — | Remove cached media file |
| `addeditor @user` | — | Grant metadata editing privileges (owner only) |
| `removeeditor @user` | — | Revoke metadata editing privileges (owner only) |

### 🛡 **Moderation & Content Filtering**
| Command | Aliases | Description |
|---------|---------|-------------|
| `blacklist <title>` | — | Add title to global content block list |
| `whitelist <title>` | — | Remove title from blacklist |
| `blacklistcheck <title>` | — | Check if title is blacklisted |
| `banuser @user` | — | Ban user from using bot (owner only) |
| `unbanuser @user` | — | Remove user ban (owner only) |
| `bannedlist` | — | List all banned users |

### ⚙️ **Server Configuration**
| Command | Aliases | Description |
|---------|---------|-------------|
| `setprefix <prefix>` | `prefix` | Change guild command prefix |
| `setdjrole <role>` | `setrole` | Restrict music commands to specific role |
| `setchannel <#channel>` | — | Lock commands to designated text channel |
| `debugmode` | — | Toggle debug logging mode |
| `showstats` | — | Toggle server count in bot status |
| `setnick <name>` | `nickname` | Change bot nickname in guild |

### 📊 **Information & Diagnostics**
| Command | Aliases | Description |
|---------|---------|-------------|
| `stats` | — | Show bot uptime, memory usage, and guild count |
| `version` | `ver` | Display version and build information |
| `cmds` | `commands` | DM complete commands reference file |
| `invite` | `link` | Generate and DM bot invite URL |

### 🏥 **Health & Monitoring (Owner Only)**
| Command | Aliases | Description |
|---------|---------|-------------|
| `health` | — | Real-time bot health status with system metrics |
| `metrics` | `sysinfo` | Detailed system and bot performance metrics |
| `webpanel` | `panel`, `web` | Web panel access information and configuration status |

### 🛰 **Administrative Controls (Owner Only)**
| Command | Aliases | Description |
|---------|---------|-------------|
| `shutdown` | `die` | Safely shut down the bot |
| `reboot` | `restart` | Restart bot process |
| `dockboot` | `dockerrestart` | Restart via Docker init script |
| `forceplay <query>` | `fplay` | Override queue and play track immediately |
| `sendglobalmsg <text>` | — | Broadcast message to all reachable guilds |
| `say <guild_id> <channel_id> <msg>` | — | Send message to specific guild/channel (DM only) |
| `fetchlogs` | `logs` | Retrieve debug logs (compressed/split if large) |
| `backupqueue [global]` | — | Backup queue(s) to configuration directory |
| `restorequeue [global]` | — | Restore queue(s) from backup |
| `purgequeues` | — | Clear all guild queues globally |
| `updateyt` | — | Update pip and force reinstall yt-dlp |

### 🎤 **Voice Control (Experimental)**
| Command | Aliases | Description |
|---------|---------|-------------|
| `listen` | — | Start voice command recognition |
| `unlisten` | — | Stop voice command recognition |

**Voice Commands**: Say "Music bot [command]" to trigger voice commands.
- Supported: play, pause, resume, stop, skip, shuffle, clear queue, loop, autoplay on/off, leave
- Example: "Music bot play daft punk"

---

## 🌐 **Web Panel Features**

### **Public Endpoints**
- **`/`** - Welcome page with navigation links
- **`/health`** - Health check for monitoring systems
- **`/queues`** - View all accessible guild queues
- **`/queue?guild_id=X`** - View specific guild queue
- **`/library`** - Browse music library with search and pagination

### **Authentication**
- **`/login`** - Discord OAuth2 authentication
- **`/logout`** - Clear session and logout
- **Per-guild access control** - Users restricted to their guilds' data

### **Owner-Only Endpoints**
- **`/metrics`** - Detailed system and bot metrics
- **`/download/owner/{track_id}`** - Download any cached track

### **API Features**
- **Multi-format export**: JSON, XML, YAML, CSV, TOML
- **Rate limiting**: 60 requests per minute per IP
- **Security headers**: CSP, XSS protection, frame denial
- **File downloads**: Authorized access to cached music files

---

## 🔒 **Security Features**

### **Web Panel Security**
- **Discord OAuth2** integration for secure authentication
- **Session-based access control** with configurable SECRET_KEY
- **Per-guild authorization** - users restricted to their guilds
- **Comprehensive security headers** (CSP, XSS protection, etc.)
- **Rate limiting** to prevent abuse

### **Bot Security**
- **Owner-only sensitive commands** with ID verification
- **Role-based access control** for music commands
- **Content filtering** with blacklist/whitelist system
- **User ban system** for problematic users

### **Infrastructure Security**
- **Docker network isolation** with custom bridge networks
- **Health checks** for container monitoring
- **Secure environment variable handling**
- **Automatic log rotation** and compression

---

## 🐛 **Troubleshooting**

### **Docker Issues**
```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs -f dtownbeats

# Restart container
docker-compose restart dtownbeats

# Update to latest image
docker-compose pull && docker-compose up -d
```

### **Voice Connection Problems**
- Bot automatically retries connections with exponential backoff
- 30-second cooldown prevents connection spam
- Check Discord permissions for voice channels
- Verify FFmpeg installation for audio processing

### **Web Panel Access Issues**
- Ensure `SESSION_SECRET` is properly configured
- Check Discord OAuth2 credentials and redirect URLs
- Verify port configuration and firewall settings
- Use `/health` endpoint to verify service status

### **Performance Optimization**
- Adjust `EXECUTOR_MAX_WORKERS` based on system capabilities
- Monitor system resources via `/metrics` endpoint
- Use SSD storage for better cache performance
- Configure appropriate `TIMEOUT_TIME` for your use case

---

## 🙏 **Acknowledgments**

Special thanks to the amazing open-source projects that make this bot possible:

- **[py-cord](https://github.com/Pycord-Development/py-cord)** - Discord API library with voice receive support
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** - YouTube audio extraction and processing
- **[FFmpeg](https://ffmpeg.org/)** - Multimedia framework for audio processing
- **[MusicBrainz](https://musicbrainz.org/)** - Open music encyclopedia for metadata
- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern web framework for the API
- **[Coqui STT](https://github.com/coqui-ai/STT)** - Speech-to-text for voice commands

---

## 🤝 **Contributing**

We welcome contributions! Please feel free to:

- **Fork this repository** and submit pull requests
- **Report bugs and issues** via GitHub Issues
- **Suggest new features** and improvements
- **Improve documentation** and examples

### **Development Setup**
1. Fork and clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `configs.json.template` to `configs.json` and configure
5. Run locally: `python bot3.py`

---

## 📜 **License**

This project is licensed under the **Unlicense** - see the LICENSE file for details.

---

### 🌟 **Enjoy the ultimate music experience on Discord!** 🎧

```r
welcome to the idiotlanparty
```