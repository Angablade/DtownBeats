import os
import re
import requests
from bs4 import BeautifulSoup

YOUTUBE_MUSIC_SEARCH_URL = "https://music.youtube.com/search?q={query}"
YOUTUBE_MUSIC_BASE_URL = "https://music.youtube.com"
GENIUS_SEARCH_URL = "https://genius.com/search?q={query}"
LYRICS_OVH_URL = "https://api.lyrics.ovh/v1/{artist}/{song}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


class Lyrics:
    def __init__(self, ctx, queue):
        self.ctx = ctx
        self.queue = queue

    def get_lyrics(self, song, artist, read_cache=True):
        """Try Lyrics.ovh first, then Genius, YouTube Music, and finally AZLyrics."""
        lyrics_dir = os.path.join(os.getcwd(), "app/lyrics")
        os.makedirs(lyrics_dir, exist_ok=True)
        filepath = os.path.join(lyrics_dir, f"{artist} - {song}.txt")

        # Read from cache if enabled
        if read_cache and os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as file:
                return file.read()

        # 1. Try Lyrics.ovh
        lyrics = self.get_lyrics_from_lyrics_ovh(artist, song)
        if lyrics:
            self.save_to_cache(filepath, lyrics)
            return lyrics

        # 2. Try Genius
        lyrics = self.get_lyrics_from_genius(artist, song)
        if lyrics:
            self.save_to_cache(filepath, lyrics)
            return lyrics

        # 3. Try YouTube Music
        lyrics = self.get_lyrics_from_youtube_music(artist, song)
        if lyrics:
            self.save_to_cache(filepath, lyrics)
            return lyrics

        # 4. Try AZLyrics (Last Resort)
        lyrics = self.get_lyrics_from_azlyrics(artist, song)
        if lyrics:
            self.save_to_cache(filepath, lyrics)
            return lyrics

        return None

    def save_to_cache(self, filepath, lyrics):
        """Save lyrics to cache file."""
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(lyrics)

    ### Lyrics.ovh ###
    def get_lyrics_from_lyrics_ovh(self, artist, song):
        """Get lyrics from Lyrics.ovh API."""
        print("Trying Lyrics.ovh...")
        url = LYRICS_OVH_URL.format(artist=artist, song=song)
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            json_data = response.json()
            return json_data.get("lyrics")
        return None

    ### Genius ###
    def search_genius(self, artist, song):
        """Search for song lyrics on Genius and return top hit if it matches."""
        print("Trying Genius...")
        query = f"{artist} {song}".replace(" ", "%20")
        search_url = GENIUS_SEARCH_URL.format(query=query)

        response = requests.get(search_url, headers=HEADERS)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        top_result = soup.select_one("search-result-item a.mini_card")

        if top_result and "href" in top_result.attrs:
            song_title = soup.select_one("div.mini_card-title").get_text(strip=True)
            artist_name = soup.select_one("div.mini_card-subtitle").get_text(strip=True)

            # Verify that the top hit matches the requested song and artist
            if song.lower() in song_title.lower() and artist.lower() in artist_name.lower():
                return top_result["href"]

        return None

    def get_lyrics_from_genius(self, artist, song):
        """Scrape lyrics from a Genius song page."""
        song_url = self.search_genius(artist, song)
        if not song_url:
            return None

        response = requests.get(song_url, headers=HEADERS)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        lyrics_div = soup.find("div", class_=re.compile("Lyrics__Container"))
        return lyrics_div.get_text(separator="\n").strip() if lyrics_div else None

    ### YouTube Music ###
    def search_youtube_music(self, artist, song):
        """Search YouTube Music for the song and return the first video link."""
        print("Trying YouTube Music...")
        query = f"{artist} {song}".replace(" ", "+")
        search_url = YOUTUBE_MUSIC_SEARCH_URL.format(query=query)

        response = requests.get(search_url, headers=HEADERS)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        result = soup.find("a", class_="yt-simple-endpoint style-scope yt-formatted-string")
        return YOUTUBE_MUSIC_BASE_URL + result["href"] if result and result.get("href") else None

    def get_lyrics_from_youtube_music(self, artist, song):
        """Scrape lyrics from a YouTube Music video page."""
        video_url = self.search_youtube_music(artist, song)
        if not video_url:
            return None

        response = requests.get(video_url, headers=HEADERS)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        lyrics_button = soup.find("button", id="description-button")
        if not lyrics_button:
            return None

        lyrics_element = lyrics_button.find("yt-formatted-string", class_="description")
        return lyrics_element.get_text(separator="\n").strip() if lyrics_element else None

    ### AZLyrics (Last Option) ###
    def get_lyrics_from_azlyrics(self, artist, song):
        """Scrape lyrics from AZLyrics."""
        print("Trying AZLyrics...")
        artist_cleaned = re.sub(r'[\W_]+', '', artist).lower()
        song_cleaned = re.sub(r'[\W_]+', '', song).lower()
        url = f"https://www.azlyrics.com/lyrics/{artist_cleaned}/{song_cleaned}.html"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            html = response.text
            start_marker = "<!-- Usage of azlyrics.com content by any third-party lyrics provider is prohibited by our licensing agreement. Sorry about that. -->"
            end_marker = "<!-- MxM banner -->"
            if start_marker in html and end_marker in html:
                lyrics = html.split(start_marker, 1)[-1].split(end_marker, 1)[0]
                return self.strip_html(lyrics)
        except requests.RequestException:
            return None
        return None

    @staticmethod
    def strip_html(html):
        """Remove HTML tags and clean up text."""
        text = re.sub(r"<.*?>", " ", html)
        text = text.replace("<br>", "\n").replace("<br />", "\n")
        return re.sub(r"\n\s*\n+", "\n", text).strip()