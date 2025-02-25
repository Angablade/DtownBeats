import asyncio
import yt_dlp
import os
import re
import requests
from bs4 import BeautifulSoup

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
            print(f"File already cached: {output_path}")
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
            print(f"Error downloading SoundCloud audio: {e}")
            return None

    def _download_sync(self, ydl_opts):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(self.url, download=True)

async def get_soundcloud_audio(url):
    streamer = SoundCloudAudioStreamer(url)
    return await streamer.download_and_convert()

async def get_soundcloud_title(url)
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title_tag = soup.find("title")
        title = title_tag["content"] if title_tag else None
     
        if title:
            title = title[7:]
            return title.replace(" | Listen online for free on SoundCloud","")
        else:
            return "-{SoundCloud Link}-"
    
    except requests.RequestException:
        return "-{SoundCloud Link}-"