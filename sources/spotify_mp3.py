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

async def get_spotify_tracks_from_playlist(url, max_retries=3):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Host": "open.spotify.com",
    }
    session = Session()
    session.headers.update(headers)
    track_urls = set()
    previous_tracks = set()
    for attempt in range(max_retries):
        try:
            response = session.get(url)
            response.raise_for_status()
            html = response.text
            new_tracks = set(re.findall(r'https://open\.spotify\.com/track/[\w]+', html))
            if new_tracks - previous_tracks:
                track_urls.update(new_tracks)
                previous_tracks = new_tracks
                logging.info(f"Found {len(new_tracks)} new tracks on attempt {attempt + 1}. Total tracks: {len(track_urls)}")
            else:
                logging.warning(f"No new tracks found on attempt {attempt + 1}.  Stopping retries.")
                break
            time.sleep(3)
        except Exception as e:
            logging.error(f"Error fetching playlist (attempt {attempt + 1}): {e}")
            return []
    return list(track_urls)

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