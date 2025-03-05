import asyncio
import re
import requests
from bs4 import BeautifulSoup

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
        print("❌ Failed to fetch Spotify title.")
        return None

    search_url = f"https://music.youtube.com/search?q={query.replace(' ', '+')}"
    
    try:
        headers_with_host = headers.copy()
        headers_with_host.update({"Host": "music.youtube.com"})

        response = requests.get(search_url, headers=headers_with_host)
        response.raise_for_status()
        video_ids = re.findall(r'watch\?v=([\w-]+)', response.text)
        return video_ids[0] if video_ids else None
    except requests.RequestException as e:
        print(f"❌ Error fetching YouTube search results: {e}")
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
        print(f"Error fetching playlist: {e}")
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
        title = soup.find("meta", {"property": "og:title"})["content"]
        artist = soup.find("meta", {"property": "music:musician"})["content"]

        return f"{artist} - {title}" if artist and title else None
    except requests.RequestException:
        return None
