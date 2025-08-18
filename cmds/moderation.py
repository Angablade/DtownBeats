# Cog for moderation commands
from discord.ext import commands
import discord
import os
import json
from utils.common import messagesender

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", 123456789))
        self.BANNED_USERS_PATH = "config/banned.json"
        self.BLACKLIST_PATH = "config/blackwhitelist.json"

    def load_banned_users(self):
        """Load banned users from file"""
        if os.path.exists(self.BANNED_USERS_PATH):
            with open(self.BANNED_USERS_PATH, "r") as f:
                return json.load(f)
        return {}

    def save_banned_users(self, banned_data):
        """Save banned users to file"""
        with open(self.BANNED_USERS_PATH, "w") as f:
            json.dump(banned_data, f, indent=4)

    def load_blacklist(self):
        """Load blacklist from file"""
        if os.path.exists(self.BLACKLIST_PATH):
            with open(self.BLACKLIST_PATH, "r") as f:
                return json.load(f)
        return {"blacklist": [], "whitelist": []}

    def save_blacklist(self, data):
        """Save blacklist to file"""
        with open(self.BLACKLIST_PATH, "w") as f:
            json.dump(data, f, indent=4)

    def is_banned_title(self, title):
        """Check if title is banned"""
        banned_keywords = [
            "drake",
            "30 for 30 freestyle",
            "forever (feat kanye west, lil wayne and eminem)",
            "demons (feat fivio foreign and sosa geek)",
            "ignant shit",
            "ice melts (feat young thug)",
            "take care (feat rihanna)",
            "controlla",
            "laugh now cry later",
            "hold on, we're going home",
            "hotline bling",
            "Dark Lane Demo Tapes",
            "For All the Dogs",
            "Some Sexy Songs 4 U",
            "Certified Lover Boy"
        ]
        
        title = title.lower().strip()
        blacklist_data = self.load_blacklist()
        
        # Check both hardcoded and stored blacklist
        return any(keyword in title for keyword in banned_keywords) or title in blacklist_data["blacklist"]

    @commands.command(name="banuser")
    async def banuser(self, ctx, user: discord.User):
        """Ban a user from using the bot (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return
        
        banned_users = self.load_banned_users()
        banned_users[user.id] = user.name
        self.save_banned_users(banned_users)
        
        # Update bot's banned users
        bot_banned_users = getattr(self.bot, 'banned_users', {})
        bot_banned_users[user.id] = user.name
        
        await messagesender(self.bot, ctx.channel.id, content=f"{user.name} has been banned from using the bot.")

    @commands.command(name="unbanuser")
    async def unbanuser(self, ctx, user: discord.User):
        """Unban a user from using the bot (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return
        
        banned_users = self.load_banned_users()
        if user.id in banned_users:
            del banned_users[user.id]
            self.save_banned_users(banned_users)
            
            # Update bot's banned users
            bot_banned_users = getattr(self.bot, 'banned_users', {})
            if user.id in bot_banned_users:
                del bot_banned_users[user.id]
            
            await messagesender(self.bot, ctx.channel.id, content=f"{user.name} has been unbanned from using the bot.")
        else:
            await messagesender(self.bot, ctx.channel.id, content=f"{user.name} is not banned.")

    @commands.command(name="bannedlist")
    async def bannedlist(self, ctx):
        """Show list of banned users (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return
        
        banned_users = self.load_banned_users()
        if not banned_users:
            await messagesender(self.bot, ctx.channel.id, content="No users are currently banned.")
        else:
            banned_list = "\n".join([f"{uid}: {name}" for uid, name in banned_users.items()])
            await messagesender(self.bot, ctx.channel.id, content=f"Banned Users:\n{banned_list}")

    @commands.command(name="blacklist")
    async def blacklist(self, ctx, *, song: str):
        """Add a song to the blacklist (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return
        
        blacklist_data = self.load_blacklist()
        if song.lower() not in blacklist_data["blacklist"]:
            blacklist_data["blacklist"].append(song.lower())
            self.save_blacklist(blacklist_data)
            
            # Update bot's blacklist data
            bot_blacklist_data = getattr(self.bot, 'blacklist_data', {"blacklist": [], "whitelist": []})
            if song.lower() not in bot_blacklist_data["blacklist"]:
                bot_blacklist_data["blacklist"].append(song.lower())
            
            await messagesender(self.bot, ctx.channel.id, content=f"`{song}` has been blacklisted.")
        else:
            await messagesender(self.bot, ctx.channel.id, content=f"`{song}` is already blacklisted.")

    @commands.command(name="whitelist")
    async def whitelist(self, ctx, *, song: str):
        """Remove a song from the blacklist (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return
        
        blacklist_data = self.load_blacklist()
        if song.lower() in blacklist_data["blacklist"]:
            blacklist_data["blacklist"].remove(song.lower())
            self.save_blacklist(blacklist_data)
            
            # Update bot's blacklist data
            bot_blacklist_data = getattr(self.bot, 'blacklist_data', {"blacklist": [], "whitelist": []})
            if song.lower() in bot_blacklist_data["blacklist"]:
                bot_blacklist_data["blacklist"].remove(song.lower())
            
            await messagesender(self.bot, ctx.channel.id, content=f"`{song}` has been removed from the blacklist.")
        else:
            await messagesender(self.bot, ctx.channel.id, content=f"`{song}` is not in the blacklist.")

    @commands.command(name="blacklistcheck")
    async def blacklist_check(self, ctx, *, song: str):
        """Check if a song is blacklisted"""
        if self.is_banned_title(song):
            await messagesender(self.bot, ctx.channel.id, content=f"`{song}` is blacklisted.")
        else:
            await messagesender(self.bot, ctx.channel.id, content=f"`{song}` is not blacklisted.")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
