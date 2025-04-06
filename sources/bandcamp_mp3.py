import asyncio
import yt_dlp
import os
import re
import aiohttp
from bs4 import BeautifulSoup
import logging

class BandcampAudioStreamer:
    def __init__(self, url):
        if not self.validate_url(url):
            raise ValueError("Invalid Bandcamp URL")
        self.url = url
        logging.error(f"Initialized BandcampAudioStreamer with URL: {url}")

    @staticmethod
    def validate_url(url: str) -> bool:
        valid = re.match(r'https?://[\w.-]+\.bandcamp\.com/track/[\w-]+', url) is not None
        logging.error(f"Validating URL: {url}, Result: {valid}")
        return valid

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
            logging.error(f"Error downloading Bandcamp audio: {e}")
            return None

    def _download_sync(self, ydl_opts):
        logging.error(f"Executing yt-dlp download for {self.url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(self.url, download=True)
        logging.error("yt-dlp download complete")

async def get_bandcamp_audio(url):
    logging.error(f"Fetching Bandcamp audio for URL: {url}")
    streamer = BandcampAudioStreamer(url)
    return await streamer.download_and_convert()

async def get_bandcamp_title(url):
    pattern = re.compile(r"https?://[\w.-]+\.bandcamp\.com/track/[\w-]+")

    if not pattern.match(url):
        return "-{Bandcamp Link}-"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Mode': 'navigate'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                soup = BeautifulSoup(await response.text(), "html.parser")

        track = soup.find("h2", class_="trackTitle").text.strip()
        album = soup.find("span", class_="fromAlbum").text.strip()
        artist = soup.find("h3", class_="albumTitle").find_all("a")[-1].text.strip()

        if artist and track:
            return f"{artist} - {album} - {track}"
        else:
            return "-{Bandcamp Link}-"

    except aiohttp.ClientError as e:
        return "-{Bandcamp Link}-"
    except AttributeError:
        return "-{Bandcamp Link}-"