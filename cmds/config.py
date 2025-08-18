# Cog for configuration commands
from discord.ext import commands
import discord
import json
import os
from utils.common import messagesender

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
        """Set bot prefix for this server"""
        if not self.is_owner_or_server_owner(ctx):
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return
        self.update_server_config(ctx.guild.id, "prefix", prefix)
        await messagesender(self.bot, ctx.channel.id, f"Prefix updated to: `{prefix}`")

    @commands.command(name="setdjrole", aliases=["setrole"])
    async def setdjrole_cmd(self, ctx, role: discord.Role):
        """Set DJ role for this server"""
        if not self.is_owner_or_server_owner(ctx):
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return
        self.update_server_config(ctx.guild.id, "dj_role", role.id)
        await messagesender(self.bot, ctx.channel.id, f"DJ role updated to: `{role.name}`")

    @commands.command(name="setchannel")
    async def setchannel_cmd(self, ctx, channel: discord.TextChannel):
        """Set designated music channel for this server"""
        if not self.is_owner_or_server_owner(ctx):
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return
        self.update_server_config(ctx.guild.id, "channel", channel.id)
        await messagesender(self.bot, ctx.channel.id, f"Designated channel updated to: `{channel.name}`")

    @commands.command(name="debugmode")
    async def toggle_debug(self, ctx):
        """Toggle debug mode (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return
        
        debug_config = self.load_debug_mode()
        debug_config["debug"] = not debug_config["debug"]
        self.save_debug_mode(debug_config)
        
        # Update bot's debug config
        bot_debug_config = getattr(self.bot, 'debug_config', {"debug": False})
        bot_debug_config["debug"] = debug_config["debug"]
        
        state = "enabled" if debug_config["debug"] else "disabled"
        await messagesender(self.bot, ctx.channel.id, content=f"Debug mode has been {state}.")

    @commands.command(name="showstats")
    async def toggle_stats(self, ctx):
        """Toggle stats display in bot presence (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return
        
        stats_config = self.load_stats_config()
        stats_config["show_stats"] = not stats_config["show_stats"]
        self.save_stats_config(stats_config)
        
        # Update bot's stats config
        bot_stats_config = getattr(self.bot, 'stats_config', {"show_stats": True})
        bot_stats_config["show_stats"] = stats_config["show_stats"]
        
        await self.update_bot_presence()
        
        state = "enabled" if stats_config["show_stats"] else "disabled"
        await messagesender(self.bot, ctx.channel.id, content=f"Bot stats display has been {state}.")

    @commands.command(name="setnick", aliases=["nickname"])
    async def setnick_cmd(self, ctx, *, nickname: str = None):
        """Set bot nickname in this server (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return

        try:
            await ctx.guild.me.edit(nick=nickname)
            await messagesender(self.bot, ctx.channel.id, content=f"Bot nickname changed to `{nickname}`")
        except Exception as e:
            await messagesender(self.bot, ctx.channel.id, content=f"Failed to change nickname: {e}")

async def setup(bot):
    await bot.add_cog(Config(bot))
