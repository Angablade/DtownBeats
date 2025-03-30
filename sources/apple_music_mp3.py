import asyncio
import aiohttp
import json
from discord import Embed

class AppleMusicScraper:
    def __init__(self, url, ctx):
        self.url = url
        self.ctx = ctx
        self.api_url = f"https://api.song.link/v1-alpha.1/links?Country=US&songIfSingle=true&url={self.url}"

    async def fetch_metadata(self, ctx):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Mode': 'navigate'
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, headers=headers) as response:
                    data = await response.json()
                    return self.extract_youtube_link(data, ctx)
        except Exception as e:
            error_message = f"Error fetching metadata: {e}"
            print(error_message)
            return None

    def extract_youtube_link(self, data, ctx):
        try:
            youtube_id = data["linksByPlatform"].get("youtube").get("entityUniqueId").split(':')[-1]
            await ctx.send(youtube_id)
            if youtube_id:
                youtube_url = f"https://www.youtube.com/watch?v={youtube_id}"
                return youtube_url
        except KeyError as e:
            await ctx.send("Error extracting youtube link")
        return None

async def get_apple_music_audio(ctx, url):
    scraper = AppleMusicScraper(url, ctx)
    youtube_url = await scraper.fetch_metadata(ctx)
    return youtube_url
