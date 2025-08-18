# Cog for music playback commands only
from discord.ext import commands
import discord
import asyncio
import os
import logging
import re
import json

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Access shared state from bot instance
        self.server_queues = getattr(bot, 'server_queues', {})
        self.current_tracks = getattr(bot, 'current_tracks', {})
        self.queue_paused = getattr(bot, 'queue_paused', {})
        self.autoplay_enabled = getattr(bot, 'autoplay_enabled', {})
        self.guild_volumes = getattr(bot, 'guild_volumes', {})
        self.banned_users = getattr(bot, 'banned_users', {})
        
        # Constants
        self.BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", 123456789))
        self.VOLUME_CONFIG_PATH = "config/volume.json"

    async def check_perms(self, ctx, guild_id):
        """Check if user has permissions to use music commands"""
        if ctx.author.id in self.banned_users:
            await self.messagesender(ctx.channel.id, content="You are banned from using this bot.")
            return False

        config = self.get_server_config(guild_id)
        dj_role_id = config.get("dj_role")
        designated_channel_id = config.get("channel")

        if dj_role_id:
            dj_role = discord.utils.get(ctx.guild.roles, id=dj_role_id)
            if dj_role not in ctx.author.roles:
                await self.messagesender(ctx.channel.id, content="You don't have the required DJ role to use this command.")
                return False

        if designated_channel_id and ctx.channel.id != designated_channel_id:
            return False

        return True

    def get_server_config(self, guild_id):
        """Get server configuration"""
        try:
            with open("config/server_config.json", 'r') as f:
                config = json.load(f)
            return config.get(str(guild_id), {"prefix": "!", "dj_role": None, "channel": None, "autoplay": False})
        except:
            return {"prefix": "!", "dj_role": None, "channel": None, "autoplay": False}

    def update_server_config(self, guild_id, key, value):
        """Update server configuration"""
        try:
            with open("config/server_config.json", 'r') as f:
                config = json.load(f)
        except:
            config = {}
        if str(guild_id) not in config:
            config[str(guild_id)] = {"prefix": "!", "dj_role": None, "channel": None, "autoplay": False}
        config[str(guild_id)][key] = value
        with open("config/server_config.json", 'w') as f:
            json.dump(config, f, indent=4)

    def save_volume_settings(self, volume_data):
        """Save volume settings"""
        with open(self.VOLUME_CONFIG_PATH, "w") as f:
            json.dump(volume_data, f, indent=4)

    async def messagesender(self, channel_id, content=None, embed=None):
        """Send messages to Discord channels"""
        channel = self.bot.get_channel(channel_id)
        if not channel:
            logging.error(f"[Error] Channel with ID {channel_id} not found.")
            return
        
        try:
            if content and embed:
                await channel.send(content=content, embed=embed)
            elif content:
                await channel.send(content=content)
            elif embed:
                await channel.send(embed=embed)
        except discord.HTTPException as e:
            logging.error(f"[Error] Failed to send message: {e}")

    async def handle_voice_connection(self, ctx):
        """Handle voice connection"""
        guild_id = ctx.guild.id
        if ctx.author.voice and ctx.author.voice.channel:
            voice_channel = ctx.author.voice.channel
            if not ctx.voice_client:
                intentional_disconnections = getattr(self.bot, 'intentional_disconnections', {})
                intentional_disconnections[guild_id] = False
                await voice_channel.connect()
        else:
            await self.messagesender(ctx.channel.id, content="You need to be in a voice channel for me to join!")

    @self.bot.command(name="play")
    async def play(self, ctx, *, srch: str):
        """Play music from various sources"""
        async with ctx.typing():
            guild_id = ctx.guild.id

            if not await self.check_perms(ctx, guild_id):
                return

            if not self.server_queues.get(guild_id):
                self.server_queues[guild_id] = asyncio.Queue()
                self.current_tracks[guild_id] = {"current_track": None, "is_looping": False}

            await self.handle_voice_connection(ctx)
            await self.messagesender(ctx.channel.id, f"Processing: {srch}")

    @self.bot.command(name="pause", aliases=["hold"])
    async def pause(self, ctx):
        """Pause the current track"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return
            
            if ctx.voice_client and ctx.voice_client.is_playing():
                ctx.voice_client.pause()
                self.queue_paused[guild_id] = True
                await self.messagesender(ctx.channel.id, content="Paused the music")

    @commands.command(name="resume", aliases=["continue"])
    async def resume(self, ctx):
        """Resume the current track"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return
            
            if ctx.voice_client and ctx.voice_client.is_paused():
                ctx.voice_client.resume()
                self.queue_paused[guild_id] = False
                await self.messagesender(ctx.channel.id, content="Resumed the music")

    @commands.command(name="stop")
    async def stop(self, ctx):
        """Stop playback and disconnect"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return
            
            if ctx.voice_client:
                intentional_disconnections = getattr(self.bot, 'intentional_disconnections', {})
                intentional_disconnections[guild_id] = True
                await ctx.voice_client.disconnect()
                self.server_queues[guild_id] = asyncio.Queue()
                self.current_tracks[guild_id] = {"current_track": None, "is_looping": False}
                await self.messagesender(ctx.channel.id, content="Stopped the bot and left the voice channel.")

    @commands.command(name="skip", aliases=["next"])
    async def skip(self, ctx):
        """Skip the current track"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return
            
            if ctx.voice_client and ctx.voice_client.is_playing():
                ctx.voice_client.stop()
                await self.messagesender(ctx.channel.id, content="Skipped the current track.")

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx, volume: int):
        """Set the playback volume"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            
            if not await self.check_perms(ctx, guild_id):
                return
            
            if not ctx.voice_client or not ctx.voice_client.is_playing():
                await self.messagesender(ctx.channel.id, content="There's no audio currently playing.")
                return
            
            if 0 <= volume <= 200:
                ctx.voice_client.source = discord.PCMVolumeTransformer(ctx.voice_client.source)
                ctx.voice_client.source.volume = volume / 100
                self.guild_volumes[guild_id] = volume
                self.save_volume_settings(self.guild_volumes)
                await self.messagesender(ctx.channel.id, f"Volume set to {volume}% and saved.")
            else:
                await self.messagesender(ctx.channel.id, content="Volume must be between 0 and 200.")

    @commands.command(name="autoplay", aliases=["autodj"])
    async def autoplay(self, ctx, mode: str):
        """Toggle autoplay mode"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return

            if mode.lower() not in ["on", "off"]:
                await self.messagesender(ctx.channel.id, "Use `!autoplay on` or `!autoplay off`.")
                return

            autoplay_value = mode.lower() == "on"
            self.autoplay_enabled[guild_id] = autoplay_value
            self.update_server_config(guild_id, "autoplay", autoplay_value)
            
            intentional_disconnections = getattr(self.bot, 'intentional_disconnections', {})
            intentional_disconnections[guild_id] = False 

            status = "enabled" if autoplay_value else "disabled"
            await self.messagesender(ctx.channel.id, f"Autoplay is now {status} for this server.")

async def setup(bot):
    await bot.add_cog(Music(bot))
