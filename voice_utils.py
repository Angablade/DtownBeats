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

class UserAudioRecorder:
    """Captures and stores individual users' audio streams."""
    
    def __init__(self):
        self.audio_buffers = {}

    def write(self, user, data):
        """Store user audio separately."""
        if user not in self.audio_buffers:
            self.audio_buffers[user] = []

        decoder = discord.opus.Decoder()
        pcm_data = decoder.decode(data, 960)
        self.audio_buffers[user].append(pcm_data)

    def get_audio(self, user):
        """Retrieve compiled audio for a specific user."""
        return b''.join(self.audio_buffers.get(user, []))

class VoiceListener:
    """Handles speech-to-text processing using Coqui STT."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.model = stt.Model("models/model.tflite") 
        self.model.enableExternalScorer("models/scorer.scorer")

    def recognize_audio(self, audio_file):
        """Process a WAV file and return transcribed text."""
        with wave.open(audio_file, "rb") as wf:
            audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        return self.model.stt(audio)

async def capture_audio(voice_client):
    """Captures per-user audio and returns transcriptions."""
    try:
        recorder = UserAudioRecorder()
        voice_client.listen(recorder)

        await asyncio.sleep(5)

        transcriptions = {}
        for user, audio_data in recorder.audio_buffers.items():
            if not audio_data:
                continue

            with NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
                temp_audio_path = temp_audio.name
                with wave.open(temp_audio_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(b''.join(audio_data))
                transcriptions[user] = recognize_audio(temp_audio_path)

        return transcriptions

    except Exception as e:
        print(f"⚠️ Error capturing audio: {e}")
        return {}



def recognize_audio(audio_file):
    """Process a WAV file and return transcribed text."""
    with wave.open(audio_file, "rb") as wf:
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    return stt.Model(MODEL_FILE).stt(audio)

async def process_audio(ctx, voice_client):
    """Processes voice input in smaller chunks to reduce CPU usage."""
    listener = VoiceListener(ctx) 

    while voice_client.is_connected():
        try:
            transcriptions = await capture_audio(voice_client)
            for user, text in transcriptions.items():
                print(f"🎤 Recognized ({user}): {text}")

                if len(text) < 4:
                    continue

                words = text.split()
                chunk = []
                for word in words:
                    chunk.append(word)
                    if len(chunk) >= 6:
                        command = " ".join(chunk)
                        await handle_voice_command(ctx, user, command)
                        chunk = []
                        await asyncio.sleep(0.5)

                if chunk:
                    command = " ".join(chunk)
                    await handle_voice_command(ctx, user, command)

        except Exception as e:
            print(f"⚠️ Error processing audio: {e}")



async def handle_voice_command(ctx, user, command):
    """Executes commands based on transcribed voice input."""
    command = command.lower().strip()
    
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
    
    await ctx.send(f"🎤 `{user}` said: `{command}`")


async def start_listening(ctx):
    """Starts voice recognition, even if already connected."""
    guild_id = ctx.guild.id

    if guild_id in voice_listeners:
        await ctx.send("🎤 Already connected! Starting voice recognition now...")
        voice_client = voice_listeners[guild_id]
    else:
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ You must be in a voice channel.")
            return

        voice_channel = ctx.author.voice.channel
        voice_client = await voice_channel.connect()
        voice_listeners[guild_id] = voice_client

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
