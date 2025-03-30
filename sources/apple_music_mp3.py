import asyncio
import aiohttp
import json
from discord import Embed

class AppleMusicScraper:
    def __init__(self, url, ctx):
        self.url = url
        self.ctx = ctx
        self.debug_info = []
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
                    ctx.send(f"API Response: {json.dumps(data, indent=2)}")
                    self.debug_info.append(f"API Response: {json.dumps(data, indent=2)}")
                    ctx.send(self.extract_youtube_link(data))
                    return self.extract_youtube_link(data)
        except Exception as e:
            error_message = f"Error fetching metadata: {e}"

            ctx.send(error_message)
            
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

async def get_apple_music_audio(url, ctx):
    scraper = AppleMusicScraper(url, ctx)
    youtube_url = await scraper.fetch_metadata(ctx)
    return youtube_url
