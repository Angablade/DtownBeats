import asyncio
import os
import re
import subprocess

class SpotifyAudioConverter:
    def __init__(self, url):
        if not self.validate_url(url):
            raise ValueError("Invalid Spotify URL")
        self.url = url

    @staticmethod
    def validate_url(url: str) -> bool:
        return re.match(r'https?://open\.spotify\.com/track/[\w]+', url) is not None

    async def convert_to_youtube(self):
        try:
            process = await asyncio.create_subprocess_exec(
                "spotdl", self.url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            output = stdout.decode().strip()
            if "youtube.com/watch?v=" in output:
                return output.split("youtube.com/watch?v=")[-1].split()[0]
            return None
        except Exception as e:
            print(f"Error converting Spotify link: {e}")
            return None

async def get_spotify_audio(url):
    converter = SpotifyAudioConverter(url)
    return await converter.convert_to_youtube()
