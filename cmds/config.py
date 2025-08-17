# Cog for configuration commands
from discord.ext import commands
import discord
import json
import os

class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", 123456789))
        self.CONFIG_FILE = "config/server_config.json"
        self.STATS_CONFIG_PATH = "config/stats_config.json"
        self.DEBUG_CONFIG_PATH = "config/debug_mode.json"

    def is_owner_or_server_owner(self, ctx):
        """Check if user is bot owner or server owner"""
        if ctx.author.id == self.BOT_OWNER_ID:
            return True
        if ctx.author.id == ctx.guild.owner_id:
            return True
        return False

    def load_config(self):
        """Load configuration from file"""
        try:
            with open(self.CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}

    def save_config(self, config):
        """Save configuration to file"""
        with open(self.CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)

    def update_server_config(self, guild_id, key, value):
        """Update server configuration"""
        config = self.load_config()
        if str(guild_id) not in config:
            config[str(guild_id)] = {"prefix": "!", "dj_role": None, "channel": None, "autoplay": False}
        config[str(guild_id)][key] = value
        self.save_config(config)

    def load_stats_config(self):
        """Load stats configuration"""
        try:
            with open(self.STATS_CONFIG_PATH, "r") as f:
                return json.load(f)
        except:
            return {"show_stats": True}

    def save_stats_config(self, config_data):
        """Save stats configuration"""
        with open(self.STATS_CONFIG_PATH, "w") as f:
            json.dump(config_data, f, indent=4)

    def load_debug_mode(self):
        """Load debug mode configuration"""
        try:
            with open(self.DEBUG_CONFIG_PATH, "r") as f:
                return json.load(f)
        except:
            return {"debug": False}

    def save_debug_mode(self, config_data):
        """Save debug mode configuration"""
        with open(self.DEBUG_CONFIG_PATH, "w") as f:
            json.dump(config_data, f, indent=4)

    async def messagesender(self, channel_id, content=None, embed=None):
        """Send messages to Discord channels"""
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        
        try:
            if content and embed:
                await channel.send(content=content, embed=embed)
            elif content:
                await channel.send(content)
            elif embed:
                await channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending message: {e}")

    async def update_bot_presence(self):
        """Update the bot's presence based on the stats setting"""
        stats_config = self.load_stats_config()
        if stats_config["show_stats"]:
            guild_count = len(self.bot.guilds)
            await self.bot.change_presence(activity=discord.Game(name=f"Serving {guild_count} servers"))
        else:
            await self.bot.change_presence(activity=None)

    @commands.command(name="setprefix", aliases=["prefix"])
    async def setprefix_cmd(self, ctx, prefix: str):
        if not self.is_owner_or_server_owner(ctx):
            await self.messagesender(ctx.channel.id, content="You don't have permission to use this command.")
            return
        self.update_server_config(ctx.guild.id, "prefix", prefix)
        await self.messagesender(ctx.channel.id, f"Prefix updated to: `{prefix}`")

    @commands.command(name="setdjrole", aliases=["setrole"])
    async def setdjrole_cmd(self, ctx, role: discord.Role):
        if not self.is_owner_or_server_owner(ctx):
            await self.messagesender(ctx.channel.id, content="You don't have permission to use this command.")
            return
        self.update_server_config(ctx.guild.id, "dj_role", role.id)
        await self.messagesender(ctx.channel.id, f"DJ role updated to: `{role.name}`")

    @commands.command(name="setchannel")
    async def setchannel_cmd(self, ctx, channel: discord.TextChannel):
        if not self.is_owner_or_server_owner(ctx):
            await self.messagesender(ctx.channel.id, content="You don't have permission to use this command.")
            return
        self.update_server_config(ctx.guild.id, "channel", channel.id)
        await self.messagesender(ctx.channel.id, f"Designated channel updated to: `{channel.name}`")

    @commands.command(name="debugmode")
    async def toggle_debug(self, ctx):
        if ctx.author.id != self.BOT_OWNER_ID:
            await self.messagesender(ctx.channel.id, content="You don't have permission to use this command.")
            return
        
        debug_config = self.load_debug_mode()
        debug_config["debug"] = not debug_config["debug"]
        self.save_debug_mode(debug_config)
        state = "enabled" if debug_config["debug"] else "disabled"
        await self.messagesender(ctx.channel.id, content=f"Debug mode has been {state}.")

    @commands.command(name="showstats")
    async def toggle_stats(self, ctx):
        if ctx.author.id != self.BOT_OWNER_ID:
            await self.messagesender(ctx.channel.id, content="You don't have permission to use this command.")
            return
        
        stats_config = self.load_stats_config()
        stats_config["show_stats"] = not stats_config["show_stats"]
        self.save_stats_config(stats_config)
        
        await self.update_bot_presence()
        
        state = "enabled" if stats_config["show_stats"] else "disabled"
        await self.messagesender(ctx.channel.id, content=f"Bot stats display has been {state}.")

    @commands.command(name="setnick", aliases=["nickname"])
    async def setnick_cmd(self, ctx, *, nickname: str = None):
        if ctx.author.id != self.BOT_OWNER_ID:
            await self.messagesender(ctx.channel.id, content="You don't have permission to use this command.")
            return

        try:
            await ctx.guild.me.edit(nick=nickname)
            await self.messagesender(ctx.channel.id, content=f"Bot nickname changed to `{nickname}`")
        except Exception as e:
            await self.messagesender(ctx.channel.id, content=f"Failed to change nickname: {e}")

async def setup(bot):
    await bot.add_cog(Config(bot))
