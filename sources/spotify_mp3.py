import asyncio
import re
import requests
from bs4 import BeautifulSoup
import json
import logging

SPOTIFY_TRACK_REGEX = r'https?://open\.spotify\.com/track/[\w]+'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Mode': 'navigate'
}

def validate_url(url: str) -> bool:
    """Validates if the given URL is a Spotify track."""
    return re.match(SPOTIFY_TRACK_REGEX, url) is not None

async def spotify_to_youtube(url: str):
    if not validate_url(url):
        raise ValueError("Invalid Spotify URL")
    query = await get_spotify_title(url)
    if not query:
        logging.error("❌ Failed to fetch Spotify title.")
        return None
    search_url = f"https://music.youtube.com/search?q={query.replace(' ', '+')}"
    try:
        headers_with_host = headers.copy()
        headers_with_host.update({"Host": "music.youtube.com"})
        response = requests.get(search_url, headers=headers_with_host)
        response.raise_for_status()
        contents = response.text.split(",")
        for item in contents:
            if "videoId" in item:
                logging.error(item)
                videoid = item.split(":")[-1][4:][:-4]
                return videoid
    except requests.RequestException as e:
        logging.error(f"❌ Error fetching YouTube search results: {e}")
        return None

async def get_spotify_tracks_from_playlist(url):
    """Extracts all track URLs from a Spotify playlist page."""
    try:
        headers_with_host = headers.copy()
        headers_with_host.update({"Host": "open.spotify.com"})
        response = requests.get(url, headers=headers_with_host)
        response.raise_for_status()
        return list(set(re.findall(r'https://open\.spotify\.com/track/[\w]+', response.text)))
    except requests.RequestException as e:
        logging.error(f"Error fetching playlist: {e}")
        return []

async def get_spotify_title(url):
    """Fetches the title and artist from a Spotify track URL."""
    if not validate_url(url):
        return None 
    try:
        headers_with_host = headers.copy()
        headers_with_host.update({"Host": "open.spotify.com"})
        response = requests.get(url, headers=headers_with_host)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        script_tag = soup.find('script', {'id': 'urlSchemeConfig'})
        if script_tag:
            json_data = json.loads(script_tag.string)
            redirect_url = json_data.get('redirectUrl')
            response = requests.get(redirect_url, headers=headers_with_host)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
        artist_tag = soup.find("meta", {"name": "music:musician_description"})
        title_tag = soup.find("meta", {"property": "og:title"})
        artist = artist_tag["content"]
        title = title_tag["content"]

        return f"{artist} - {title}"
    except requests.RequestException:
        return None