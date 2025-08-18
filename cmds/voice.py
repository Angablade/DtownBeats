# Cog for voice channel commands
from discord.ext import commands
import discord
import os
import logging
from utils.common import check_perms, messagesender, safe_voice_connect

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.banned_users = getattr(bot, 'banned_users', {})

    @commands.command(name="join", aliases=["come"])
    async def join_channel(self, ctx):
        """Join the user's voice channel"""
        async with ctx.typing():
            guild_id = ctx.guild.id

            if not await check_perms(ctx, guild_id, self.bot):
                return

            if ctx.author.voice:
                channel = ctx.author.voice.channel
                intentional_disconnections = getattr(self.bot, 'intentional_disconnections', {})
                intentional_disconnections[guild_id] = False

                voice_client = await safe_voice_connect(self.bot, ctx.guild, channel)

                if voice_client and voice_client.is_connected():
                    await messagesender(self.bot, ctx.channel.id, f"? Joined **{channel.name}** voice channel. ??")
                else:
                    await messagesender(self.bot, ctx.channel.id, f"? Failed to join **{channel.name}**.")
            else:
                await messagesender(self.bot, ctx.channel.id, content="? You need to be in a voice channel for me to join!")

    @commands.command(name="leave", aliases=["go"])
    async def leave_channel(self, ctx):
        """Leave the voice channel"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return
            
            if ctx.voice_client:
                intentional_disconnections = getattr(self.bot, 'intentional_disconnections', {})
                intentional_disconnections[guild_id] = True
                await ctx.voice_client.disconnect()
                await messagesender(self.bot, ctx.channel.id, content="Disconnected from the voice channel. ??")
            else:
                await messagesender(self.bot, ctx.channel.id, content="I'm not in a voice channel to leave.")

    @commands.command(name="mute", aliases=["quiet"])
    async def toggle_mute(self, ctx):
        """Toggle mute/unmute"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return
            
            voice_client = ctx.voice_client

            if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                if voice_client.is_paused():
                    voice_client.resume()
                    await messagesender(self.bot, ctx.channel.id, content="Unmuted the bot. ??")
                else:
                    voice_client.pause()
                    await messagesender(self.bot, ctx.channel.id, content="Muted the bot. ??")
            else:
                await messagesender(self.bot, ctx.channel.id, content="I'm not playing anything to mute or unmute.")

    @commands.command(name="listen")
    async def listen_command(self, ctx):
        """Start voice listening (if implemented)"""
        try:
            from utils.voice_utils import start_listening
            await start_listening(ctx)
        except ImportError:
            await messagesender(self.bot, ctx.channel.id, content="Voice listening feature not available.")
        except Exception as e:
            await messagesender(self.bot, ctx.channel.id, content=f"Error starting voice listening: {e}")

    @commands.command(name="unlisten")
    async def unlisten_command(self, ctx):
        """Stop voice listening (if implemented)"""
        try:
            from utils.voice_utils import stop_listening
            await stop_listening(ctx)
        except ImportError:
            await messagesender(self.bot, ctx.channel.id, content="Voice listening feature not available.")
        except Exception as e:
            await messagesender(self.bot, ctx.channel.id, content=f"Error stopping voice listening: {e}")

async def setup(bot):
    await bot.add_cog(Voice(bot))
