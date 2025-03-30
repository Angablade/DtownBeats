import asyncio
import yt_dlp
import os
import re
import requests
from bs4 import BeautifulSoup
import aiohttp
import logging

class SoundCloudAudioStreamer:
    def __init__(self, url):
        if not self.validate_url(url):
            raise ValueError("Invalid SoundCloud URL")
        self.url = url

    @staticmethod
    def validate_url(url: str) -> bool:
        return re.match(r'https?://soundcloud\.com/[\w-]+/[\w-]+', url) is not None

    async def download_and_convert(self):
        output_path = f"music/{self.url.split('/')[-1]}"
        if os.path.exists(output_path):
            logging.error(f"File already cached: {output_path}")
            return output_path
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'outtmpl': output_path,
        }
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._download_sync, ydl_opts)
            return f"{output_path}.mp3"
        except Exception as e:
            logging.error(f"Error downloading SoundCloud audio: {e}")
            return None

    def _download_sync(self, ydl_opts):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(self.url, download=True)

async def get_soundcloud_audio(url):
    streamer = SoundCloudAudioStreamer(url)
    return await streamer.download_and_convert()

async def get_soundcloud_title(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status() 
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                title = soup.find("title")

                if title:
                    title_text = title.get_text()
                    title_text = title_text[7:]
                    return title_text.replace(" | Listen online for free on SoundCloud", "").strip()
                else:
                    return "-{SoundCloud Link}-"

    except aiohttp.ClientError:
        return "-{SoundCloud Link}-"