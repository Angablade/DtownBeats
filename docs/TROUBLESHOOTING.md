# ?? Troubleshooting Guide

Common problems, diagnostics and fixes for DtownBeats.

---
## ?? Container / Process
| Problem | Diagnosis | Fix |
|---------|-----------|-----|
| Container restarts loop | `docker compose logs` shows crash | Verify BOT_TOKEN, dependencies, upgrade image |
| High memory usage | `/metrics` or host monitor | Reduce EXECUTOR_MAX_WORKERS; prune music cache |
| High CPU usage | Top/htop | Limit concurrent downloads; disable voice control; smaller STT model |

---
## ?? Discord Connectivity
| Problem | Diagnosis | Fix |
|---------|-----------|-----|
| Bot offline | Auth errors in logs | Regenerate token; check intents (Message Content) in portal |
| Commands ignored | Wrong prefix / channel restriction | Check `config/server_config.json`; run `!setprefix` / `!setchannel` |
| Voice drops | Reconnect warnings | Network instability; allow reconnect cooldown to clear |

---
## ?? Playback
| Problem | Diagnosis | Fix |
|---------|-----------|-----|
| Track not starting | Download or yt-dlp error | Run `!updateyt`; verify network; cookies if geo-blocked |
| Stuttering audio | Host I/O or CPU | Move cache to SSD; reduce concurrent preloads |
| Volume resets | Missing volume transformer | Re-set with `!volume`; ensure saved JSON writeable |
| Autoplay silent | Empty queue, no related found | Disable then re-enable autoplay; play different seed track |

---
## ?? Storage
| Problem | Diagnosis | Fix |
|---------|-----------|-----|
| Disk fills quickly | Large `music/` size | Prune old files; add cron cleanup |
| Missing album art | Default art used | Confirm `albumart/` exists & writable |
| Metadata stale | Wrong titles | `!fetchmetadata <id> <refined query>` then adjust with `!setmetadata` |

---
## ?? Web Panel
| Problem | Diagnosis | Fix |
|---------|-----------|-----|
| 403 on /queues | Not logged in / wrong guild | Log in; ensure guild membership; owner overwrites restrictions |
| 429 responses | Rate limit hit | Increase RATE_LIMIT_PER_MIN env or slow polling |
| /metrics denied | Owner only | Log in as BOT_OWNER_ID account |
| Queue empty visually | server_queues not populated yet | Interact with bot to initialize queue |

---
## ?? OAuth / Auth
| Problem | Diagnosis | Fix |
|---------|-----------|-----|
| `/login` says not configured | Missing env vars | Set DISCORD_CLIENT_ID & DISCORD_CLIENT_SECRET |
| Discord redirect error | URI mismatch | Add exact `https://domain/auth` (and optional http dev) in portal |
| Frequent logout | Session lost | Stable SESSION_SECRET, proxy preserving cookies, no clock skew |

---
## ?? Voice Control
| Problem | Diagnosis | Fix |
|---------|-----------|-----|
| `!listen` fails | Model load error | Ensure model & scorer names match in `models/` |
| No reactions to speech | Wake phrase not captured | Speak clearly; reduce noise |
| Wrong actions executed | Recognition errors | Better scorer, smaller room echo |
| CPU spikes | Heavy STT model | Switch to smaller model variant |

---
## ?? Diagnostics Commands
| Command | Purpose |
|---------|---------|
| `!version` | Build / version info |
| `!stats` | Basic uptime & memory |
| `!health` | Owner health snapshot |
| `!metrics` | Owner system metrics |
| `!fetchlogs` | Retrieve log file |
| `!debugmode` | Toggle detailed logging |

---
## ?? Maintenance Tasks
| Task | How |
|------|-----|
| Backup queues | `!backupqueue` / global variant |
| Restore queues | `!restorequeue` |
| Purge all queues | `!purgequeues` |
| Update yt-dlp | `!updateyt` |
| Clear old audio | Manual prune or script (e.g., delete oldest in `music/`) |
| Refresh metadata | Iterate IDs with `!fetchmetadata` (sparingly) |

---
## ? Escalation Steps
1. Reproduce issue after a clean restart.
2. Enable `!debugmode` (remember to disable afterwards).
3. Run `!fetchlogs` for detailed errors.
4. Open an issue with: environment (Docker/native), steps, logs excerpt.

Happy debugging! ??
