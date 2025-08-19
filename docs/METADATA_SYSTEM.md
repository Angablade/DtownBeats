# ?? Metadata System Guide

The current metadata system is intentionally minimal: it stores only three fields per track (`artist`, `title`, `duration`). It caches them to disk so later lookups (embeds, web panel, search) avoid repeated MusicBrainz queries. Additional fields mentioned elsewhere (e.g. `id`, `source`, `fetched_at`, album data) are **not** persisted in the existing implementation.

---
## ?? Components
| Component | Location | Purpose |
|----------|----------|---------|
| `MetadataManager` | `utils/metadata.py` | Core load / fetch / cache / update logic |
| Cache directory | `metacache/` | One JSON file per track ID (video ID) |
| Editors file | `config/metadataeditors.json` | Stores list of user IDs allowed to edit metadata (`{"editors": [ ... ]}`) |
| Album art fetcher (separate) | `utils/albumart.py` | Supplies image path for embeds / web UI (not stored in metadata JSON) |

---
## ?? Resolution Flow (Actual)
1. A track (YouTube video ID or local file identifier) is about to play.
2. Bot calls `load_metadata(<id>)`.
3. If cache miss: `fetch_metadata(query)` performs a MusicBrainz recording search (limit=1).
4. First (best) recording populates:
   - `artist` : main credited artist name
   - `title`  : recording title
   - `duration` : milliseconds / 1000 (int seconds) if `length` present, else `0` ? then embed code may convert / fallback
5. If no recording result: returns `{ "artist": "Unknown Artist", "title": <query>, "duration": "Unknown" }`.
6. Result persisted via `save_metadata(<id>, metadata)`.

---
## ?? Actual Cache File Example
If MusicBrainz returned length:
```json
{
  "artist": "Rick Astley",
  "title": "Never Gonna Give You Up",
  "duration": 213
}
```
If length was unavailable:
```json
{
  "artist": "Unknown Artist",
  "title": "Some Search Query",
  "duration": "Unknown"
}
```
> Only these keys are written unless you add more via `!setmetadata`.

---
## ?? Type Notes
| Field | Normal Type | Fallback Type | Usage in bot3.py |
|-------|-------------|---------------|------------------|
| artist | `str` | `"Unknown Artist"` | Embed field "Artist" |
| title | `str` | query string | Embed description / file lookup context |
| duration | `int` seconds | `"Unknown"` | Converted to mm:ss; code guards against non-int via try/except |

Be careful when manually editing `duration`: prefer an integer number of seconds so embeds render correctly.

---
## ?? Editor Permission System
- On startup `MetadataManager.__init__` loads `config/metadataeditors.json` if present.
- Expected structure: `{ "editors": [123456789012345678, 987654321098765432] }`.
- Owner can modify the list at runtime:
  - `!addeditor @user`
  - `!removeeditor @user`
- Updated list written back atomically with pretty JSON.

---
## ?? Commands & Their Real Effects
| Command | Action in Code | Notes |
|---------|----------------|-------|
| `!getmetadata <id>` | `load_metadata(id)` | Returns JSON or nothing if absent |
| `!fetchmetadata <id> <query>` | `get_or_fetch_metadata(id, query)` (forces create if missing) | Does NOT force refresh if already cached (because `get_or_fetch_metadata` only fetches on miss) |
| `!setmetadata <id> <key> <value>` | Mutates loaded dict then saves | Can introduce new arbitrary keys |
| `!clean <id>` | Deletes audio file(s) only | Leaves JSON metadata intact |

### Forcing a True Refresh
Currently there is **no built-in invalidate** step. To force a fresh MusicBrainz lookup:
1. Delete the cache file `metacache/<id>.json` manually (or implement a `refreshmetadata` command calling `fetch_metadata` unconditionally).
2. Re-run `!fetchmetadata <id> <query>`.

---
## ?? Library Search Integration
The `/library` endpoint loads metadata (if present) to display `title` & `artist`, and allows filtering by:
- Track ID
- Title substring (case-insensitive)
- Artist substring

If cache missing or unparseable, it falls back to using the filename/ID as the title.

---
## ?? Best Practices
| Scenario | Recommendation |
|----------|---------------|
| Wrong artist/title from MusicBrainz | Use `!setmetadata <id> <field> <value>` to correct locally |
| Need to fully refresh stale metadata | Remove the JSON file then re-trigger playback or manual fetch |
| Unknown duration but file exists | Consider adding a command that uses `ffmpeg_get_track_length` to backfill |
| Large number of stale entries | Write a maintenance script to prune or refetch on demand |

---
## ? Duration Fallback (ffmpeg)
`ffmpeg_get_track_length(path)` is available to probe real durations. In `bot3.py` the code attempts to format duration and falls back to probing if an exception is raised. You can integrate this proactively by extending `fetch_metadata` to fill a missing or zero duration from local audio once downloaded.

---
## ?? Extension Ideas
| Idea | Minimal Change Required |
|------|------------------------|
| Add `fetched_at` timestamp | Append `metadata['fetched_at']=int(time.time())` before save |
| Add album / release MBID | Capture extra fields from MusicBrainz result if present |
| Force-refresh command | New method that ignores existing cache and overwrites |
| Add multi-source merge | Integrate YouTube metadata or Spotify conversion info |
| Cache size limits | Periodic cleanup of oldest JSON files |

---
## ? FAQ
**Q:** Why is `duration` sometimes a string?  
**A:** When MusicBrainz length missing; code stores "Unknown". Later code wraps mm:ss formatting in try/except to handle that.

**Q:** Can I safely add new keys?  
**A:** Yes; they are ignored elsewhere unless you modify code to consume them.

**Q:** How do I see who can edit metadata?  
**A:** Open `config/metadataeditors.json` (owner manages via add/remove commands).

**Q:** Why didn’t `!fetchmetadata` update existing wrong data?  
**A:** Because it only fetches on cache miss. Delete the JSON or implement a refresh function.

---
Enjoy lightweight, cache-friendly metadata! ??
