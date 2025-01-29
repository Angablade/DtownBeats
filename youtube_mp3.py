import asyncio
import re
import os
import yt_dlp

class YouTubeMP3Streamer:

    def __init__(self, video_id):
        if not self.validate_video_id(video_id):
            raise ValueError("Invalid YouTube video ID")
        self.video_url = f'https://www.youtube.com/watch?v={video_id}'
        self.video_id = video_id

    @staticmethod
    def validate_video_id(video_id: str) -> bool:
        return re.match(r'^[a-zA-Z0-9_-]{11}$', video_id) is not None

    async def download_and_convert(self):
        mp3_file_path = f"music/{self.video_id}.mp3"

        if os.path.exists(mp3_file_path):
            print(f"File already cached: {mp3_file_path}")
            return mp3_file_path

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'outtmpl': 'music/%(id)s',
        }

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._download_and_convert_sync, ydl_opts)
            return mp3_file_path

        except Exception as e:
            raise RuntimeError(f"Error: Unable to stream audio - {e}")

    def _download_and_convert_sync(self, ydl_opts):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(self.video_url, download=True)

async def get_mp3_filename(video_id):
    streamer = YouTubeMP3Streamer(video_id)
    return await streamer.download_and_convert()
