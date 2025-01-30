# 🎵 Discord Music Bot

A powerful, feature-rich, and customizable music bot for Discord! Built with Python and discord.py, this bot delivers high-quality audio streaming, playlist support, and intuitive controls directly to your server.

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

### 🎵 **Music Commands**

| Command           | Description                          |
| ----------------- | ------------------------------------ |
| `!play <query>`   | Play a song or add it to the queue.  |
| `!stop`           | Stop playback and disconnect.        |
| `!pause`          | Pause playback.                      |
| `!resume`         | Resume playback.                     |
| `!skip`           | Skip the current track.              |
| `!seek <time>`    | Jump to a specific part of the song. |
| `!queue`          | Show the upcoming songs.             |
| `!loop`           | Toggle looping for the current song. |
| `!volume <0-200>` | Adjust playback volume.              |
| `!shuffle`        | Shuffle the queue.                   |

### ⚙️ **Admin & Config Commands**

| Command                 | Description                              |
| ----------------------- | ---------------------------------------- |
| `!setprefix <prefix>`   | Change the bot's prefix.                 |
| `!setdjrole <role>`     | Assign a DJ role.                        |
| `!setchannel <channel>` | Restrict commands to a specific channel. |
| `!shutdown`             | Shut down the bot (owner only).          |
| `!reboot`               | Restart the bot (owner only).            |

### 📢 **Utility Commands**

| Command          | Description                  |
| ---------------- | ---------------------------- |
| `!lyrics <song>` | Get song lyrics.             |
| `!invite`        | Get the bot invite link.     |
| `!cmds`          | List all available commands. |

---

## 🙏 Acknowledgments

Special thanks to the amazing open-source projects that make this bot possible:

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Used for YouTube audio extraction.
- [FFmpeg](https://ffmpeg.org/) - Handles audio processing.
- [discord.py](https://github.com/Rapptz/discord.py) - The foundation of this bot.
- [MusicBrainz](https://musicbrainz.org/) - Provides metadata for songs.

---

## 🤝 Contributing

Feel free to fork this repository, submit pull requests, or report issues!

---

## 📜 License

This project is licensed under the Unlicense.

---

### 🌟 Enjoy the "best" music experience on Discord! 🎧

---

```r
welcome to the idiotlanparty
```
