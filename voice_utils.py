import os
import sys
import subprocess
import urllib.request
import asyncio
import numpy as np
import discord
import wave
import stt
from discord import FFmpegPCMAudio
from discord.ext import commands
from tempfile import NamedTemporaryFile

MODEL_DIR = "models"
MODEL_FILE = os.path.join(MODEL_DIR, "model.tflite")
SCORER_FILE = os.path.join(MODEL_DIR, "scorer.scorer")

MODEL_URL = "https://coqui.gateway.scarf.sh/english/coqui/v1.0.0-huge-vocab/model.tflite"
SCORER_URL = "https://coqui.gateway.scarf.sh/english/coqui/v1.0.0-huge-vocab/huge-vocabulary.scorer"

def install_coqui_stt():
    """Ensure Coqui STT is installed."""
    try:
        import stt
        print("✅ Coqui STT is installed.")
    except ImportError:
        print("📥 Installing Coqui STT...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "coqui-stt"])
        import stt

def download_file(url, destination):
    """Download a file if it does not exist."""
    if not os.path.exists(destination):
        print(f"📥 Downloading {destination}...")
        urllib.request.urlretrieve(url, destination)
        print(f"✅ Downloaded: {destination}")

def setup_models():
    """Ensure model files exist."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    download_file(MODEL_URL, MODEL_FILE)
    download_file(SCORER_URL, SCORER_FILE)

install_coqui_stt()
setup_models()

voice_listeners = {}

class VoiceListener:
    def __init__(self, ctx):
        self.ctx = ctx
        self.model = stt.Model(MODEL_FILE)
        self.model.enableExternalScorer(SCORER_FILE)

    def recognize_audio(self, audio_file):
        """Process a WAV file and return transcribed text."""
        with wave.open(audio_file, "rb") as wf:
            audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        return self.model.stt(audio)

    async def capture_audio(self, voice_client):
        """Records live audio from the Discord call and transcribes it."""
        with NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            temp_audio_path = temp_audio.name

        audio_source = FFmpegPCMAudio(voice_client, executable="ffmpeg", options="-f wav -ar 16000 -ac 1 -")
        with wave.open(temp_audio_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)

            while voice_client.is_connected():
                audio_chunk = await asyncio.to_thread(audio_source.read, 4096)
                if not audio_chunk:
                    break
                wf.writeframes(audio_chunk)

        return self.recognize_audio(temp_audio_path)

async def process_audio(ctx, voice_client):
    """Continuously listens for commands from the Discord voice call."""
    listener = VoiceListener(ctx)

    while voice_client.is_connected():
        try:
            text = await listener.capture_audio(voice_client)
            print(f"🎤 Recognized: {text}")
            if "music bot" in text.lower():
                command = text.lower().replace("music bot", "").strip()

                if command.startswith("play "):
                    search_term = command[len("play "):]
                    await ctx.invoke(ctx.bot.get_command("play"), search=search_term)
                elif command == "volume up":
                    await ctx.invoke(ctx.bot.get_command("volume"), volume=10)
                elif command == "volume down":
                    await ctx.invoke(ctx.bot.get_command("volume"), volume=-10)
                elif command == "pause":
                    await ctx.invoke(ctx.bot.get_command("pause"))
                elif command == "resume":
                    await ctx.invoke(ctx.bot.get_command("resume"))
                elif command == "stop":
                    await ctx.invoke(ctx.bot.get_command("stop"))
                elif command == "skip":
                    await ctx.invoke(ctx.bot.get_command("skip"))
                elif command == "shuffle":
                    await ctx.invoke(ctx.bot.get_command("shuffle"))
                elif command == "clear queue":
                    await ctx.invoke(ctx.bot.get_command("clear"))
                elif command == "loop":
                    await ctx.invoke(ctx.bot.get_command("loop"))
                elif command == "autoplay on":
                    await ctx.invoke(ctx.bot.get_command("autoplay"), mode="on")
                elif command == "autoplay off":
                    await ctx.invoke(ctx.bot.get_command("autoplay"), mode="off")
                elif command == "leave":
                    await ctx.invoke(ctx.bot.get_command("leave"))
                await ctx.send(f"🎤 Recognized command: `{command}`")
        except Exception as e:
            print(f"⚠️ Error processing audio: {e}")
async def start_listening(ctx):
    """Start voice recognition in a Discord voice call."""
    if ctx.guild.id in voice_listeners:
        await ctx.send("🎤 Already listening!")
        return

    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ You must be in a voice channel.")
        return

    voice_channel = ctx.author.voice.channel
    voice_client = await voice_channel.connect()
    voice_listeners[ctx.guild.id] = voice_client

    await ctx.send("🎤 Listening for voice commands... Say 'Music bot <command>'.")
    await process_audio(ctx, voice_client)

async def stop_listening(ctx):
    """Stop voice recognition in a Discord voice call."""
    if ctx.guild.id not in voice_listeners:
        await ctx.send("🔇 Not currently listening.")
        return

    voice_client = voice_listeners.pop(ctx.guild.id)
    await voice_client.disconnect()
    await ctx.send("🛑 Voice control stopped.")
