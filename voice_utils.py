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
    """Handles speech-to-text processing using Coqui STT."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.model = stt.Model(MODEL_FILE)
        self.model.enableExternalScorer(SCORER_FILE)

    def recognize_audio(self, audio_file):
        """Process a WAV file and return transcribed text."""
        with wave.open(audio_file, "rb") as wf:
            audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        return self.model.stt(audio)

async def start_listening(ctx):
    """Starts voice recognition using Pycord's AudioSink."""
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
    
    # Start recording using WaveSink
    await voice_client.start_recording(discord.sinks.WaveSink(), finished_callback, ctx)

async def stop_listening(ctx):
    """Stops voice recognition and disconnects the bot."""
    if ctx.guild.id not in voice_listeners:
        await ctx.send("🔇 Not currently listening.")
        return

    voice_client = voice_listeners.pop(ctx.guild.id)

    # Stop the recording before disconnecting
    await voice_client.stop_recording()
    
    await voice_client.disconnect()
    await ctx.send("🛑 Voice control stopped.")

def finished_callback(sink, ctx):
    """Processes recorded audio when finished."""
    print("🔊 Recording complete!")

    transcriptions = {}
    for user, audio_data in sink.audio_data.items():
        with NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            temp_audio_path = temp_audio.name
            with wave.open(temp_audio_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(audio_data.file.getvalue())

        # Transcribe user audio
        transcriptions[user.display_name] = recognize_audio(temp_audio_path)

    # Process recognized commands asynchronously
    for user, text in transcriptions.items():
        print(f"🎤 {user}: {text}")
        asyncio.create_task(process_voice_command(ctx, text))  # Run command processing

async def process_voice_command(ctx, text):
    """Executes commands based on transcribed voice input."""
    text = text.lower().strip()

    # Ensure the command starts with "music bot"
    if not text.startswith("music bot"):
        return
    
    command = text[len("music bot"):].strip()  # Remove "Music bot" from the start

    # Check for recognized commands
    bot = ctx.bot  # Get the bot instance

    if command.startswith("play "):
        search_term = command[len("play "):]
        await ctx.invoke(bot.get_command("play"), search=search_term)
    elif command == "pause":
        await ctx.invoke(bot.get_command("pause"))
    elif command == "resume":
        await ctx.invoke(bot.get_command("resume"))
    elif command == "stop":
        await ctx.invoke(bot.get_command("stop"))
    elif command == "skip":
        await ctx.invoke(bot.get_command("skip"))
    elif command == "shuffle":
        await ctx.invoke(bot.get_command("shuffle"))
    elif command == "clear queue":
        await ctx.invoke(bot.get_command("clear"))
    elif command == "loop":
        await ctx.invoke(bot.get_command("loop"))
    elif command == "autoplay on":
        await ctx.invoke(bot.get_command("autoplay"), mode="on")
    elif command == "autoplay off":
        await ctx.invoke(bot.get_command("autoplay"), mode="off")
    elif command == "leave":
        await ctx.invoke(bot.get_command("leave"))
    
    print(f"✅ Recognized command: {command}")

def recognize_audio(audio_file):
    """Process a WAV file and return transcribed text."""
    with wave.open(audio_file, "rb") as wf:
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    return stt.Model(MODEL_FILE).stt(audio)
