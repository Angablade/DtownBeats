# Cog for metadata commands
from discord.ext import commands
import discord
import json
import os

class Metadata(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", 123456789))
        self.metadata_manager = getattr(bot, 'metadata_manager', None)

    @commands.command(name="getmetadata")
    async def get_metadata(self, ctx, filename: str):
        if not self.metadata_manager:
            await ctx.send("Metadata manager not available.")
            return
            
        metadata = self.metadata_manager.load_metadata(filename)
        if metadata:
            await ctx.send(f"Metadata for {filename}:\n```json\n{json.dumps(metadata, indent=4)}```")
        else:
            await ctx.send("No metadata found.")

    @commands.command(name="fetchmetadata")
    async def fetch_metadata(self, ctx, filename: str, query: str):
        if not self.metadata_manager:
            await ctx.send("Metadata manager not available.")
            return
            
        if ctx.author.id not in self.metadata_manager.editor_ids:
            await ctx.send("You do not have permission to edit metadata.")
            return
        metadata = self.metadata_manager.get_or_fetch_metadata(filename, query)
        await ctx.send(f"Fetched metadata:\n```json\n{json.dumps(metadata, indent=4)}```")

    @commands.command(name="setmetadata")
    async def set_metadata(self, ctx, filename: str, key: str, value: str):
        if not self.metadata_manager:
            await ctx.send("Metadata manager not available.")
            return
            
        if ctx.author.id not in self.metadata_manager.editor_ids:
            await ctx.send("You do not have permission to edit metadata.")
            return
        self.metadata_manager.update_metadata(filename, key, value)
        await ctx.send(f"Updated {key} in {filename}.")

    @commands.command(name="clean")
    async def clean_file(self, ctx, ID: str):
        if not self.metadata_manager:
            await ctx.send("Metadata manager not available.")
            return
            
        if ctx.author.id not in self.metadata_manager.editor_ids:
            await ctx.send("? You do not have permission to clean this ID.")
            return

        file_path = f"music/{ID}"
        if not os.path.exists(file_path):
            file_path = f"music/{ID}.mp3"
        if not os.path.exists(file_path):
            file_path = f"music/{ID}.opus"
        if not os.path.exists(file_path):
            await ctx.send(f"? File not found for ID: {ID}")
            return

        try:
            os.remove(file_path)
            await ctx.send(f"? Cleaned {ID} from database.")
        except Exception as e:
            await ctx.send(f"? An error occurred while cleaning ID: {e}")

    @commands.command(name="addeditor")
    async def add_editor(self, ctx, user: discord.User):
        if not self.metadata_manager:
            await ctx.send("Metadata manager not available.")
            return
            
        if ctx.author.id != self.BOT_OWNER_ID:
            await ctx.send("You do not have permission to modify editors.")
            return
        self.metadata_manager.add_editor(user.id)
        await ctx.send(f"Added {user.mention} as a metadata editor.")

    @commands.command(name="removeeditor")
    async def remove_editor(self, ctx, user: discord.User):
        if not self.metadata_manager:
            await ctx.send("Metadata manager not available.")
            return
            
        if ctx.author.id != self.BOT_OWNER_ID:
            await ctx.send("You do not have permission to modify editors.")
            return
        self.metadata_manager.remove_editor(user.id)
        await ctx.send(f"Removed {user.mention} from metadata editors.")

async def setup(bot):
    await bot.add_cog(Metadata(bot))
