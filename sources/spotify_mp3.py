import asyncio
import os
import re
import subprocess
import requests
from bs4 import BeautifulSoup
from spotdl import Spotdl

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
            print(f"Running SpotDL for: {self.url}")
            process = await asyncio.create_subprocess_exec(
                "spotdl", f"{self.url} --redownload --overwrite",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            output = stdout.decode().strip()
            error_output = stderr.decode().strip()

            print(f"SpotDL Output:\n{output}")
            print(f"SpotDL Errors:\n{error_output}")

            if "youtube.com/watch?v=" in output:
                return output.split("youtube.com/watch?v=")[-1].split()[0]
            return None
        except Exception as e:
            print(f"Error converting Spotify link: {e}")
            return None


async def get_spotify_audio(url):
    converter = SpotifyAudioConverter(url)
    return await converter.convert_to_youtube()

async def get_spotify_tracks_from_playlist(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Host': 'open.spotify.com',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Mode': 'navigate'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching playlist: {e}")
        return []

    tracks = []
    cont = response.text.split('"')
    for itm in cont:
        if "/track/" in itm:
            tracks.append(itm)
    return list(set(tracks))


async def get_spotify_title(url):
    pattern = re.compile(r"https://open\.spotify\.com/track/[a-zA-Z0-9]+(?:\?si=[a-zA-Z0-9]+)?")
    
    if not pattern.match(url):
        return "-{Spotify Link}-"
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        artist_tag = soup.find("meta", {"name": "music:musician_description"})
        title_tag = soup.find("meta", {"property": "og:title"})
        artist = artist_tag["content"] if artist_tag else None
        title = title_tag["content"] if title_tag else None
        
        if artist and title:
            return f"{artist} - {title}"
        else:
            return "-{Spotify Link}-"
    
    except requests.RequestException:
        return "-{Spotify Link}-"