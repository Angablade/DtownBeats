# Cog for voice channel commands
from discord.ext import commands
import discord
import os
import logging

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.banned_users = getattr(bot, 'banned_users', {})

    async def check_perms(self, ctx, guild_id):
        """Check if user has permissions to use voice commands"""
        if ctx.author.id in self.banned_users:
            await self.messagesender(ctx.channel.id, content="You are banned from using this bot.")
            return False
        return True

    async def messagesender(self, channel_id, content=None):
        """Send messages to Discord channels"""
        channel = self.bot.get_channel(channel_id)
        if not channel:
            logging.error(f"[Error] Channel with ID {channel_id} not found.")
            return
        
        try:
            if content:
                await channel.send(content=content)
        except discord.HTTPException as e:
            logging.error(f"[Error] Failed to send message: {e}")

    @commands.command(name="join", aliases=["come"])
    async def join_channel(self, ctx):
        """Join the user's voice channel"""
        async with ctx.typing():
            guild_id = ctx.guild.id

            if not await self.check_perms(ctx, guild_id):
                return

            if ctx.author.voice:
                channel = ctx.author.voice.channel
                intentional_disconnections = getattr(self.bot, 'intentional_disconnections', {})
                intentional_disconnections[guild_id] = False

                try:
                    voice_client = await channel.connect()
                    if voice_client and voice_client.is_connected():
                        await self.messagesender(ctx.channel.id, f"Joined {channel.name} voice channel.")
                    else:
                        await self.messagesender(ctx.channel.id, f"Failed to join {channel.name}.")
                except Exception as e:
                    await self.messagesender(ctx.channel.id, f"Failed to join {channel.name}: {e}")
            else:
                await self.messagesender(ctx.channel.id, content="You need to be in a voice channel for me to join!")

    @commands.command(name="leave", aliases=["go"])
    async def leave_channel(self, ctx):
        """Leave the voice channel"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return
            
            if ctx.voice_client:
                intentional_disconnections = getattr(self.bot, 'intentional_disconnections', {})
                intentional_disconnections[guild_id] = True
                await ctx.voice_client.disconnect()
                await self.messagesender(ctx.channel.id, content="Disconnected from the voice channel.")
            else:
                await self.messagesender(ctx.channel.id, content="I'm not in a voice channel to leave.")

    @commands.command(name="mute", aliases=["quiet"])
    async def toggle_mute(self, ctx):
        """Toggle mute/unmute"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return
            
            voice_client = ctx.voice_client

            if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                if voice_client.is_paused():
                    voice_client.resume()
                    await self.messagesender(ctx.channel.id, content="Unmuted the bot.")
                else:
                    voice_client.pause()
                    await self.messagesender(ctx.channel.id, content="Muted the bot.")
            else:
                await self.messagesender(ctx.channel.id, content="I'm not playing anything to mute or unmute.")

async def setup(bot):
    await bot.add_cog(Voice(bot))
