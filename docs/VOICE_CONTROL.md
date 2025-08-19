# ?? Voice Control (Experimental)

Hands?free interaction using speech recognition (Coqui STT). Optional; inactive unless you explicitly start it.

---
## ?? Overview
| Aspect | Detail |
|--------|-------|
| Activation | User runs `!listen` in a voice channel |
| Deactivation | `!unlisten` |
| Wake Phrase | `music bot` (case?insensitive) |
| Command Pattern | `music bot <command and arguments>` |
| Model Source | Coqui STT `.tflite` + scorer |
| Location | `models/` volume (mounted inside container) |

---
## ?? Model Files
Place or bind the following into `models/`:
```
models/
 ?? model.tflite          # acoustic model
 ?? huge-vocabulary.scorer (or scorer.scorer)
```
Names must match what `utils/voice_utils.py` expects; rename if needed.

---
## ?? Basic Usage
| Command | Effect |
|---------|--------|
| `!listen` | Begin capturing & transcribing voice in current VC |
| `!unlisten` | Stop transcription & free resources |

> Bot must already be connected to the same voice channel as the invoking user.

---
## ?? Supported Spoken Commands
Say these after the wake phrase:
| Spoken Example | Resulting Bot Command |
|----------------|----------------------|
| music bot play daft punk | `!play daft punk` |
| music bot pause | `!pause` |
| music bot resume | `!resume` |
| music bot skip | `!skip` |
| music bot stop | `!stop` |
| music bot shuffle | `!shuffle` |
| music bot loop | `!loop` |
| music bot autoplay on | `!autoplay on` |
| music bot autoplay off | `!autoplay off` |
| music bot leave | `!leave` |

---
## ?? Performance Tips
| Issue | Mitigation |
|-------|-----------|
| High CPU use | Use smaller model variant; reduce sampling rate |
| Latency | Ensure host has free CPU; isolate from heavy downloads |
| Misrecognition | Higher quality mic; quieter environment; better scorer file |
| False triggers | Stricter wake phrase matching or add confidence threshold |

---
## ?? Security & Privacy
- No raw audio persisted by default (verify in `voice_utils`).
- Limit who can start listening: combine with DJ role / restricted command channel.
- Consider notifying channel when listening starts (already via command feedback).

---
## ?? Troubleshooting
| Symptom | Check |
|---------|-------|
| "Model file not found" | Correct filenames present in `models/` |
| Nothing happens after `!listen` | Bot connected? Permissions to receive audio? |
| Repeated wrong commands | Ambient noise; switch to closer mic |
| Bot unresponsive post?listen | Run `!unlisten`, rejoin voice, reissue `!listen` |

---
## ?? Potential Enhancements
- Per?guild custom wake phrase
- Dynamic language model selection
- Noise suppression / VAD integration
- Partial result streaming feedback

---
Enjoy hands?free control! ??
