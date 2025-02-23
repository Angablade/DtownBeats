import asyncio
import yt_dlp
import os
import re

class BandcampAudioStreamer:
    def __init__(self, url):
        if not self.validate_url(url):
            raise ValueError("Invalid Bandcamp URL")
        self.url = url
        print(f"Initialized BandcampAudioStreamer with URL: {url}")

    @staticmethod
    def validate_url(url: str) -> bool:
        valid = re.match(r'https?://[\w.-]+\.bandcamp\.com/track/[\w-]+', url) is not None
        print(f"Validating URL: {url}, Result: {valid}")
        return valid

    async def download_and_convert(self):
        output_path = f"music/{self.url.split('/')[-1]}.mp3"
        if os.path.exists(output_path):
            print(f"File already cached: {output_path}")
            return output_path
        
        print(f"Starting download for: {self.url}")
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'outtmpl': 'music/%(title)s.%(ext)s',
        }
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._download_sync, ydl_opts)
            success = os.path.exists(output_path)
            print(f"Download successful: {success}, File: {output_path if success else 'Not Found'}")
            return output_path if success else None
        except Exception as e:
            print(f"Error downloading Bandcamp audio: {e}")
            return None

    def _download_sync(self, ydl_opts):
        print(f"Executing yt-dlp download for {self.url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(self.url, download=True)
        print("yt-dlp download complete")

async def get_bandcamp_audio(url):
    print(f"Fetching Bandcamp audio for URL: {url}")
    streamer = BandcampAudioStreamer(url)
    return await streamer.download_and_convert()
