import asyncio
import yt_dlp
import os
import re

class SoundCloudAudioStreamer:
    def __init__(self, url):
        if not self.validate_url(url):
            raise ValueError("Invalid SoundCloud URL")
        self.url = url

    @staticmethod
    def validate_url(url: str) -> bool:
        return re.match(r'https?://soundcloud\.com/[\w-]+/[\w-]+', url) is not None

    async def download_and_convert(self):
        output_path = f"music/{self.url.split('/')[-1]}.mp3"
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
            'outtmpl': 'music/%(title)s.%(ext)s',
        }
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._download_sync, ydl_opts)
            return output_path if os.path.exists(output_path) else None
        except Exception as e:
            print(f"Error downloading SoundCloud audio: {e}")
            return None

    def _download_sync(self, ydl_opts):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(self.url, download=True)

async def get_soundcloud_audio(url):
    streamer = SoundCloudAudioStreamer(url)
    return await streamer.download_and_convert()
