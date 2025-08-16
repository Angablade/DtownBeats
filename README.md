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

### 🔐 Web Panel & API
- FastAPI powered web panel to view: queues, all guild queues, track history, and music library.
- Multi-format export (json, xml, yaml, csv, toml) for /queue and /queues endpoints.
- OAuth2 (Discord) login with session-based access control.
- Per-guild authorization – users only see queues for guilds they share with the bot.
- Download endpoint for cached tracks (authorized users only / owner global access).
- Simple in-browser library search (title / artist / ID) with pagination.

### 🗂 Metadata System
- Persistent metadata cache with auto-fetch & MusicBrainz enrichment.
- Owner / editor role system to manually fetch, set, and clean metadata.
- Album art fetcher + embedding in now playing messages & web panel.

### 🤖 Voice Control (Experimental)
- Coqui STT integration for voice command recognition inside voice channels.
- Commands triggered with the hot phrase: "Music bot <command>" (e.g., *Music bot play daft punk*).

### 🔄 Robust Voice Connection Handling
- Safe connect wrapper with retry & cooldown to mitigate 4006 gateway/session invalid issues.
- Auto-resume scaffolding (resume intent after reconnect) and volume reapplication.
- Autoplay of related YouTube tracks when queue becomes empty (optional per guild).

### 🧠 Queue Intelligence
- Pre-download (preload) of upcoming tracks to minimize playback gaps.
- Track history per guild (recent 20) exposed in commands & web.
- Duplicate & similarity filtering when selecting related autoplay tracks.

### 🛡 Moderation & Access Controls
- Blacklist / whitelist for banned titles (includes fuzzy matching & hard-coded filters).
- Per-guild DJ role & command channel restriction.
- User ban system for bot usage.

### 🧰 Maintenance / Admin Utilities
- Queue backup & restore (guild or global scope).
- Purge all queues across guilds.
- Dynamic yt-dlp updater command.
- Log retrieval with size-based compression & multipart splitting (7z volumes) for large logs.
- Forced play (owner override) and global broadcast messaging to all reachable guilds.

### 🎛 Playback & UX Improvements
- Percentage & timestamp seeking (e.g., 1:30 or 50%).
- Volume persistence per guild (0–200%).
- Loop toggle, shuffle, move, remove, clear, history recall.
- Intelligent message chunking and file splitting for Discord upload limits.

### 🧪 Misc
- Docker friendly layout with persistent config, music, metadata, album art.
- Intent-driven prefix resolution per guild (dynamic prefixes stored in config JSON).

> Tip: Set SESSION_SECRET in your environment to secure web panel sessions.

---

## 📦 Installation

### 🐳 Docker Setup

1. Ensure you have Docker and Docker Compose installed.
2. Create a `.env` file and add your bot token:
   ```env
   BOT_TOKEN=your_discord_bot_token
   ```
3. Run the bot using Docker Compose:
   ```bash
   docker-compose up -d
   ```

#### 📂 Volume Mappings

- `/app/lyrics` → Stores lyrics data.
- `/app/music` → Stores downloaded music files.
- `/app/config` → Stores server configurations.

The bot will automatically restart unless stopped manually.

---

### 🛠 Manual Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/Angablade/DtownBeats.git
   cd DtownBeats
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   ```env
   BOT_TOKEN=your_discord_bot_token
   MUSICBRAINZ_USERAGENT=your_user_agent
   MUSICBRAINZ_VERSION=1.0
   MUSICBRAINZ_CONTACT=your_email@example.com
   BOT_OWNER_ID=your_discord_id
   EXECUTOR_MAX_WORKERS=10
   ```
4. Run the bot:
   ```bash
   python bot3.py
   ```

---

## 🛠 Configuration

Edit `config/server_config.json` to adjust settings such as:

- **Prefix** (`!` by default)
- **DJ Role** (Restricts commands to specific users)
- **Command Channel** (Limits bot commands to a designated text channel)

---

## 🖥 Commands Overview

Below is the full command catalog (prefix defaults to `!` unless changed with `setprefix`). Aliases are shown in parentheses.

### 🎵 Playback & Queue
| Command | Aliases | Description |
|---------|---------|-------------|
| play <query/link> | — | Play (YouTube search, direct ID/URL, Bandcamp/SoundCloud/Spotify/Apple links) |
| youtube <query/link> | yt | Explicit YouTube/playlist handler |
| grablist <query> | grabplaylist | Smart playlist search + bulk add |
| queue [page] | list | Show queued tracks (paginated) |
| nowplaying | current, np | Show current track metadata |
| history | played | Recently played (last 20) |
| skip | next | Skip current track |
| pause | hold | Pause playback |
| resume | continue | Resume playback |
| stop | — | Stop & clear state (disconnect) |
| seek <mm:ss / % / seconds> | — | Jump to position in current track |
| loop | repeat | Toggle looping for current track |
| shuffle | — | Shuffle queue |
| remove <index> | — | Remove specific queued item |
| clear | — | Clear queue |
| move <from> <to> | — | Reorder a queued item |
| autoplay <on/off> | autodj | Toggle related-track autoplay when queue empty |
| volume <0-200> | vol | Set & persist guild volume |
| mute | quiet | Toggle pause/resume (soft mute) |
| forceplay <query> | fplay | Owner: insert track to play next immediately |
| join | come | Join your voice channel |
| leave | go | Leave voice channel |
| sendplox | dlfile | DM current track file (zips/splits if large) |

### 🌐 External Source Shortcuts
| Command | Aliases | Description |
|---------|---------|-------------|
| bandcamp <url> | bc | Queue Bandcamp track |
| soundcloud <url> | sc | Queue SoundCloud track |
| spotify <url> | sp | Track or playlist conversion via YouTube Music |
| applemusic <url> | ap | Apple Music lookup & queue |

### 📝 Metadata & Lyrics
| Command | Aliases | Description |
|---------|---------|-------------|
| lyrics [song] | lyr | Fetch lyrics (current or query) |
| getmetadata <id> | — | Show cached metadata JSON |
| fetchmetadata <id> <query> | — | Force refetch/update metadata |
| setmetadata <id> <key> <value> | — | Manually edit a metadata field |
| clean <id> | — | Remove local media file for ID |
| addeditor @user | — | Owner: grant metadata editor rights |
| removeeditor @user | — | Owner: revoke metadata editor rights |

### 🛡 Moderation & Filtering
| Command | Aliases | Description |
|---------|---------|-------------|
| blacklist <title> | — | Add title to global block list |
| whitelist <title> | — | Remove title from blacklist |
| blacklistcheck <title> | — | Check if blacklisted |
| banuser @user | — | Owner: ban user from bot |
| unbanuser @user | — | Owner: unban user |
| bannedlist | — | List banned users |

### ⚙️ Configuration
| Command | Aliases | Description |
|---------|---------|-------------|
| setprefix <p> | prefix | Change guild prefix |
| setdjrole <role> | setrole | Restrict music commands to role |
| setchannel <#channel> | — | Lock commands to one text channel |
| debugmode | — | Toggle debug logging mode flag |
| showstats | — | Toggle dynamic presence (server count) |
| setnick <name> | nickname | Change bot nickname |

### 📊 Info & Diagnostics
| Command | Aliases | Description |
|---------|---------|-------------|
| stats | — | Bot uptime / memory / guilds |
| version | ver | Show version / build info |
| cmds | commands | DM full commands file |
| invite | link | DM bot invite URL |
| fetchlogs | logs | Owner: fetch debug log (compress/split) |
| backupqueue [global] | — | Backup queue(s) to config dir |
| restorequeue [global] | — | Restore queue(s) from backup |
| purgequeues | — | Owner: clear all guild queues |
| updateyt | — | Update pip & force reinstall yt-dlp |

### 🛰 Admin & Control
| Command | Aliases | Description |
|---------|---------|-------------|
| shutdown | die | Owner: stop bot |
| reboot | restart | Owner: restart process |
| dockboot | dockerrestart | Owner: run init script & exit |
| sendglobalmsg <text> | — | Owner: broadcast message |
| say <guild_id> <channel_id> <msg> | — | Owner (DM only): relay message |
| forceplay <query> | fplay | Owner: priority insert & play |

### 🎤 Voice Control (Experimental)
| Command | Aliases | Description |
|---------|---------|-------------|
| listen | — | Start STT voice command listener |
| unlisten | — | Stop STT listener |

Hot phrase: `Music bot <command>` (e.g., “Music bot play daft punk”). Supports: play, pause, resume, stop, skip, shuffle, clear queue, loop, autoplay on/off, leave.

---

## 🙏 Acknowledgments

Special thanks to the amazing open-source projects that make this bot possible:

- [py-cord](https://github.com/Pycord-Development/py-cord) - Discord API library & voice receive (sinks) support.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Used for YouTube audio extraction.
- [FFmpeg](https://ffmpeg.org/) - Handles audio processing.
- [MusicBrainz](https://musicbrainz.org/) - Provides metadata for songs.

---

## 🤝 Contributing

Feel free to fork this repository, submit pull requests, or report issues!

---

## 📜 License

This project is licensed under the Unlicense.

---

### 🌟 Enjoy the "best" music experience on Discord! 🎧


```r
welcome to the idiotlanparty
```