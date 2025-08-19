# ?? Full Commands Reference
Default prefix: `!` (customizable per guild). Owner = BOT_OWNER_ID. Some commands respect DJ role / designated channel restrictions.

---
## ?? Playback & Queue
| Command | Aliases | Usage | Description |
|---------|---------|-------|-------------|
| play | (none) | `!play <query|url>` | Queue a track (search YouTube / route external source) |
| youtube | yt | `!yt <query|playlist|id>` | Explicit YouTube/playlist handler |
| grablist | grabplaylist | `!grablist <search>` | Finds first suitable playlist & queues all (skips podcasts) |
| queue | list | `!queue [page]` | Show queued tracks with pagination |
| nowplaying | current,np | `!nowplaying` | Display currently playing track metadata |
| history | played | `!history` | Show recent track history (20) |
| skip | next | `!skip` | Skip current track |
| pause | hold | `!pause` | Pause playback |
| resume | continue | `!resume` | Resume playback |
| stop | (none) | `!stop` | Stop & clear queue, leave voice |
| seek | (none) | `!seek <mm:ss|seconds|percent%>` | Seek within current track |
| loop | repeat | `!loop` | Toggle looping current track |
| shuffle | (none) | `!shuffle` | Shuffle queue order |
| remove | (none) | `!remove <index>` | Remove track at index (1-based) |
| clear | (none) | `!clear` | Clear entire queue |
| move | (none) | `!move <from> <to>` | Reorder queue entry |
| autoplay | autodj | `!autoplay <on|off>` | Related-track autoplay toggle |
| volume | vol | `!volume <0-200>` | Set persistent guild volume |
| mute | quiet | `!mute` | Pause/resume (soft mute toggle) |
| join | come | `!join` | Force bot join voice channel |
| leave | go | `!leave` | Disconnect from voice |
| forceplay | fplay | `!forceplay <query>` | Owner: queue & bump track to play next |
| sendplox | dlfile | `!sendplox` | DM current track file (compress if large) |

---
## ?? External Sources
| Command | Aliases | Usage | Description |
|---------|---------|-------|-------------|
| bandcamp | bc | `!bandcamp <url>` | Queue Bandcamp track |
| soundcloud | sc | `!soundcloud <url>` | Queue SoundCloud track |
| spotify | sp | `!spotify <track_or_playlist_url>` | Convert & queue via YouTube Music |
| applemusic | ap | `!applemusic <url>` | Queue Apple Music track |

---
## ?? Metadata & Lyrics
| Command | Aliases | Usage | Description |
|---------|---------|-------|-------------|
| lyrics | lyr | `!lyrics [query]` | Lyrics for current or searched song |
| getmetadata | (none) | `!getmetadata <id>` | Show cached metadata JSON |
| fetchmetadata | (none) | `!fetchmetadata <id> <query>` | Re-fetch metadata using search query |
| setmetadata | (none) | `!setmetadata <id> <key> <value>` | Manually edit metadata field |
| clean | (none) | `!clean <id>` | Remove cached audio file (keeps metadata) |
| addeditor | (none) | `!addeditor @user` | Owner: grant metadata edit rights |
| removeeditor | (none) | `!removeeditor @user` | Owner: revoke metadata edit rights |

---
## ?? Moderation & Filtering
| Command | Aliases | Usage | Description |
|---------|---------|-------|-------------|
| blacklist | (none) | `!blacklist <title>` | Add a song title to global blacklist |
| whitelist | (none) | `!whitelist <title>` | Remove title from blacklist |
| blacklistcheck | (none) | `!blacklistcheck <title>` | Check if title is blocked |
| banuser | (none) | `!banuser @user` | Owner: ban user from bot usage |
| unbanuser | (none) | `!unbanuser @user` | Owner: unban user |
| bannedlist | (none) | `!bannedlist` | Show banned users |

---
## ?? Server Configuration
| Command | Aliases | Usage | Description |
|---------|---------|-------|-------------|
| setprefix | prefix | `!setprefix <prefix>` | Change guild prefix (owner/server owner) |
| setdjrole | setrole | `!setdjrole @role` | Restrict music commands to role |
| setchannel | (none) | `!setchannel #channel` | Restrict commands to channel |
| debugmode | (none) | `!debugmode` | Toggle debug logging |
| showstats | (none) | `!showstats` | Toggle server count in presence |
| setnick | nickname | `!setnick <name>` | Change bot nickname |

---
## ?? Info & Diagnostics
| Command | Aliases | Usage | Description |
|---------|---------|-------|-------------|
| stats | (none) | `!stats` | Uptime, memory, server count |
| version | ver | `!version` | Version/build info (DM embed) |
| cmds | commands | `!cmds` | DM commands file |
| invite | link | `!invite` | DM invite link |
| health | (none) | `!health` | Owner: health snapshot |
| metrics | sysinfo | `!metrics` | Owner: detailed system metrics |
| webpanel | panel,web | `!webpanel` | Owner: panel config info (if implemented) |

---
## ?? Administrative (Owner)
| Command | Aliases | Usage | Description |
|---------|---------|-------|-------------|
| shutdown | die | `!shutdown` | Stop bot |
| reboot | restart | `!reboot` | Restart process (exec) |
| dockboot | dockerrestart | `!dockboot` | Reinvoke init script / container restart |
| backupqueue | (none) | `!backupqueue [global]` | Backup queue(s) |
| restorequeue | (none) | `!restorequeue [global]` | Restore queue(s) |
| purgequeues | (none) | `!purgequeues` | Clear all queues |
| sendglobalmsg | (none) | `!sendglobalmsg <text>` | Broadcast message |
| say | (none) | `!say <guild_id> <channel_id> <msg>` | DM only – remote send |
| fetchlogs | logs | `!fetchlogs` | Retrieve logs (compressed if large) |
| updateyt | (none) | `!updateyt` | Reinstall yt-dlp (and pip upgrade) |
| forceplay | fplay | `!forceplay <query>` | Force immediate playback |

---
## ?? Voice Control
| Command | Aliases | Usage | Description |
|---------|---------|-------|-------------|
| listen | (none) | `!listen` | Start speech recognition loop |
| unlisten | (none) | `!unlisten` | Stop speech recognition |

Wake phrase: `music bot <command>`.

---
## ?? Operational Notes
- Queue indices: 1-based for user commands.
- Volume persists per guild across sessions.
- Autoplay avoids duplicates & banned titles using fuzzy matching.
- Some permission failures intentionally silent to reduce spam.

---
Enjoy the music! ??
