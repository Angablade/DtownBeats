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
