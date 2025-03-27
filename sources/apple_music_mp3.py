import asyncio
import aiohttp
import json
from discord import Embed

class AppleMusicScraper:
    def __init__(self, url, ctx):
        self.url = url
        self.ctx = ctx
        self.debug_info = []
        self.api_url = f"https://api.song.link/v1-alpha.1/links?Country=US&songIfSingle=true&url={url}"

    async def fetch_metadata(self):
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, headers=headers) as response:
                    data = await response.json()
                    self.debug_info.append(f"API Response: {json.dumps(data, indent=2)}")
                    return self.extract_youtube_link(data)
        except Exception as e:
            error_message = f"Error fetching metadata: {e}"
            self.debug_info.append(error_message)
            print(error_message)
            return None

    def extract_youtube_link(self, data):
        try:
            youtube_id = data["entitiesByUniqueId"].get(f"YOUTUBE_VIDEO::{data['entityUniqueId'].split('::')[-1]}", {}).get("id")
            if youtube_id:
                youtube_url = f"https://www.youtube.com/watch?v={youtube_id}"
                self.debug_info.append(f"Extracted YouTube URL: {youtube_url}")
                return youtube_url
        except KeyError as e:
            self.debug_info.append(f"Error extracting YouTube link: {e}")
        return None

    async def post_debug_info(self):
        embed = Embed(title="Debug Information", color=0x00ff00)
        for info in self.debug_info:
            embed.add_field(name="Debug Info", value=info, inline=False)
        await messagesender(self.ctx.bot, self.ctx.channel.id, embed=embed)

async def get_apple_music_audio(url, ctx):
    scraper = AppleMusicScraper(url, ctx)
    youtube_url = await scraper.fetch_metadata()
    await scraper.post_debug_info()
    return youtube_url
