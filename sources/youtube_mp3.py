import asyncio
import re
import os
import yt_dlp
import logging

class YouTubeAudioStreamer:

    def __init__(self, video_id):
        if not self.validate_video_id(video_id):
            raise ValueError("Invalid YouTube video ID")
        self.video_id = video_id
        self.video_url = f'https://www.youtube.com/watch?v={video_id}'
        self.music_url = f'https://music.youtube.com/watch?v={video_id}'

    @staticmethod
    def validate_video_id(video_id: str) -> bool:
        return re.match(r'^[a-zA-Z0-9_-]{11}$', video_id) is not None

    async def download_and_convert(self):
        opus_file_path = f"music/{self.video_id}.opus"
        mp3_file_path = f"music/{self.video_id}.mp3"

        if os.path.exists(opus_file_path):
            logging.error(f"File already cached: {opus_file_path}")
            return opus_file_path
        if os.path.exists(mp3_file_path):
            logging.error(f"File already cached: {mp3_file_path}")
            return mp3_file_path

        # Try downloading Opus 774 first from YouTube Music
        if await self._attempt_download(self.music_url, 'opus', '774', opus_file_path):
            return opus_file_path
        
        # Try downloading Opus 774 from regular YouTube
        if await self._attempt_download(self.video_url, 'opus', '774', opus_file_path):
            return opus_file_path
        
        # Fallback to MP3 if Opus 774 isn't available
        if await self._attempt_download(self.video_url, 'mp3', '320', mp3_file_path):
            return mp3_file_path
        
        raise RuntimeError("Error: Unable to download audio in any format")

    async def _attempt_download(self, url, codec, quality, output_path):
        ydl_opts = {
            'format': 'bestaudio[acodec^=opus]/bestaudio',
            'cookiefile': '/app/config/cookies.txt',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': codec,
                'preferredquality': quality,
            }],
            'outtmpl': f'music/%(id)s',
        }
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._download_sync, ydl_opts, url)
            return os.path.exists(output_path)
        except Exception as e:
            logging.error(f"Error downloading {codec} format from {url}: {e}")
            return False

    def _download_sync(self, ydl_opts, url):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

async def get_audio_filename(video_id):
    streamer = YouTubeAudioStreamer(video_id)
    return await streamer.download_and_convert()
