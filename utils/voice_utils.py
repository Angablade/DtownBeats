import os
import sys
import subprocess
import urllib.request
import asyncio
import numpy as np
import discord
import wave
import stt
from discord.ext import commands
from tempfile import NamedTemporaryFile
import logging

MODEL_DIR = "models"
MODEL_FILE = os.path.join(MODEL_DIR, "model.tflite")
SCORER_FILE = os.path.join(MODEL_DIR, "scorer.scorer")

MODEL_URL = "https://coqui.gateway.scarf.sh/english/coqui/v1.0.0-huge-vocab/model.tflite"
SCORER_URL = "https://coqui.gateway.scarf.sh/english/coqui/v1.0.0-huge-vocabulary.scorer"

def install_coqui_stt():
    """Ensure Coqui STT is installed."""
    try:
        import stt  # noqa: F401
        logging.error("✅ Coqui STT is installed.")
    except ImportError:
        logging.error("📥 Installing Coqui STT...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "coqui-stt"])
        import stt  # noqa: F401

def download_file(url, destination):
    """Download a file if it does not exist."""
    if not os.path.exists(destination):
        logging.error(f"📥 Downloading {destination}...")
        urllib.request.urlretrieve(url, destination)
        logging.error(f"✅ Downloaded: {destination}")

def setup_models():
    """Ensure model files exist."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    download_file(MODEL_URL, MODEL_FILE)
    download_file(SCORER_URL, SCORER_FILE)

install_coqui_stt()
setup_models()

# Load STT model once (expensive)
try:
    STT_MODEL = stt.Model(MODEL_FILE)
    if os.path.exists(SCORER_FILE):
        try:
            STT_MODEL.enableExternalScorer(SCORER_FILE)
        except Exception:
            logging.exception("Failed to enable external scorer.")
except Exception:
    STT_MODEL = None
    logging.exception("Failed to initialize STT model.")

voice_listeners = {}

# Detect sink support (py-cord provides discord.sinks; vanilla discord.py does not)
HAS_SINKS = hasattr(discord, "sinks") and hasattr(getattr(discord, "sinks"), "WaveSink")
if not HAS_SINKS:
    logging.error("⚠️ Voice receive (sinks) not available in current discord library. Install py-cord to enable STT: pip install -U py-cord")

HOTWORD = "music bot"  # Leading phrase to trigger parsing
SUPPORTED_VOICE_COMMANDS = {
    "pause": ("pause", {}),
    "resume": ("resume", {}),
    "stop": ("stop", {}),
    "skip": ("skip", {}),
    "shuffle": ("shuffle", {}),
    "loop": ("loop", {}),
    "autoplay on": ("autoplay", {"mode": "on"}),
    "autoplay off": ("autoplay", {"mode": "off"}),
    "leave": ("leave", {}),
}

async def start_listening(ctx: commands.Context):
    """Starts voice recognition in the user's current voice channel.
    Reuses existing voice connection if present to avoid double connections."""
    guild = ctx.guild
    if guild.id in voice_listeners:
        await ctx.send("🎤 Already listening in this guild.")
        return

    if not HAS_SINKS:
        await ctx.send("⚠️ STT unavailable (voice receive not supported by this discord.py build). Install py-cord to enable.")
        return

    if STT_MODEL is None:
        await ctx.send("❌ STT model failed to load; check logs.")
        return

    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ You must be in a voice channel.")
        return

    target_channel = ctx.author.voice.channel

    # Reuse existing voice connection if already connected elsewhere
    vc = guild.voice_client
    try:
        if vc and vc.is_connected():
            if vc.channel != target_channel:
                await vc.move_to(target_channel)
        else:
            vc = await target_channel.connect(self_deaf=False)  # self_deaf False so we can receive
    except Exception:
        logging.exception("Failed to establish/move voice client for STT")
        await ctx.send("❌ Could not connect for STT.")
        return

    if not vc:
        await ctx.send("❌ Voice connection unavailable.")
        return

    # Prepare sink
    sink = discord.sinks.WaveSink()
    try:
        vc.start_recording(sink, finished_callback, ctx, after=lambda e: logging.error(f"STT record stopped: {e}" if e else "STT recording finished."))
    except Exception:
        logging.exception("Failed to start recording; is this library py-cord?")
        await ctx.send("❌ Failed to start STT recording (library missing sink support).")
        return

    voice_listeners[guild.id] = vc
    await ctx.send("🎤 Listening enabled. Say 'Music bot <command>' or 'Music bot play <query>'.")

async def stop_listening(ctx: commands.Context):
    guild_id = ctx.guild.id
    vc = voice_listeners.pop(guild_id, None)
    if not vc:
        await ctx.send("🔇 Not currently listening.")
        return
    try:
        vc.stop_recording()
    except Exception:
        pass
    await ctx.send("🛑 Voice control stopped.")

async def process_voice_command(ctx: commands.Context, text: str):
    text = (text or "").lower().strip()
    if not text.startswith(HOTWORD):
        return
    payload = text[len(HOTWORD):].strip()
    if not payload:
        return

    # Play command dynamic
    if payload.startswith("play "):
        query = payload[5:].strip()
        if query:
            await ctx.invoke(ctx.bot.get_command("play"), srch=query)
        return

    # Static mapped commands
    # Longest phrase match first
    for key in sorted(SUPPORTED_VOICE_COMMANDS.keys(), key=lambda k: -len(k)):
        if payload.startswith(key):
            cmd_name, kwargs = SUPPORTED_VOICE_COMMANDS[key]
            cmd = ctx.bot.get_command(cmd_name)
            if cmd:
                await ctx.invoke(cmd, **kwargs)
            return

    logging.info(f"Voice payload not matched: {payload}")

# --- Internal helpers ---

def transcribe_wav(path: str) -> str:
    if STT_MODEL is None:
        return ""
    try:
        with wave.open(path, "rb") as wf:
            audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        return STT_MODEL.stt(audio)
    except Exception:
        logging.exception("Failed to transcribe audio")
        return ""

def finished_callback(sink, ctx: commands.Context):
    """Called by py-cord when stop_recording is invoked OR periodically when sink flushes.
    We iterate over collected user chunks and schedule transcription tasks."""
    logging.error("🔊 Processing buffered voice data for STT...")
    for user_id, audio in sink.audio_data.items():
        try:
            with NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp.write(audio.file.getvalue())
                temp_path = tmp.name
        except Exception:
            logging.exception("Failed to write temp wav for STT")
            continue

        async def _analyze(path=temp_path):  # closure captures path
            try:
                text = transcribe_wav(path)
                if text:
                    logging.error(f"🎤 {user_id}: {text}")
                    await process_voice_command(ctx, text)
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass
        # Schedule async processing
        asyncio.create_task(_analyze())

# Legacy function kept for backward compatibility (not used now)
def recognize_audio(audio_file):  # noqa: D401
    return transcribe_wav(audio_file)
