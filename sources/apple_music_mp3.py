import asyncio
import re
import os
import aiohttp
from bs4 import BeautifulSoup

class AppleMusicScraper:
    def __init__(self, url):
        if not self.validate_url(url):
            raise ValueError("Invalid Apple Music URL")
        self.url = url

    @staticmethod
    def validate_url(url: str) -> bool:
        return re.match(r'https?://music\.apple\.com/.+/song/.+/\d+', url) is not None

    async def scrape_metadata(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    title = soup.find("title").text.replace(" - Apple Music", "").strip()
                    return title
        except Exception as e:
            print(f"Error scraping Apple Music metadata: {e}")
            return None

    async def search_youtube(self):
        metadata = await self.scrape_metadata()
        if not metadata:
            return None
        search_url = f"https://www.youtube.com/results?search_query={metadata.replace(' ', '+')}"
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url) as response:
                html = await response.text()
                video_ids = re.findall(r'"videoId":"([\w-]{11})"', html)
                return f"https://www.youtube.com/watch?v={video_ids[0]}" if video_ids else None

async def get_apple_music_audio(url):
    scraper = AppleMusicScraper(url)
    return await scraper.search_youtube()
