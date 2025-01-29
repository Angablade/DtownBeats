import os
import re
import requests

class Lyrics:

    def __init__(self, ctx, queue):
        self.ctx = ctx
        self.queue = queue

    def get_lyrics(self, song, artist, read_cache=True):
        artist_cleaned = re.sub(r'[\W_]+', '', artist)
        song_cleaned = re.sub(r'[\W_]+', '', song)
        address = f"http://www.azlyrics.com/lyrics/{artist_cleaned}/{song_cleaned}.html"
        address = address.lower()
        lyrics_dir = os.path.join(os.getcwd(), "/app/lyrics")
        os.makedirs(lyrics_dir, exist_ok=True)
        filepath = os.path.join(lyrics_dir, f"{artist} - {song}.txt")
        if read_cache and os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as file:
                return file.read()
        contents = self.download_and_strip(address)
        if contents:
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write(contents)
        return contents

    def download_and_strip(self, address):
        try:
            response = requests.get(address, timeout=10)
            response.raise_for_status()
            html = response.text
            start_marker = "<!-- Usage of azlyrics.com content by any third-party lyrics provider is prohibited by our licensing agreement. Sorry about that. -->"
            end_marker = "<!-- MxM banner -->"
            if start_marker in html and end_marker in html:
                lyrics = html.split(start_marker, 1)[-1].split(end_marker, 1)[0]
                return self.strip_html(lyrics)
        except requests.RequestException:
            return None

    @staticmethod
    def strip_html(html):
        text = re.sub(r"<.*?>", " ", html)
        text = text.replace("<br>", "\n").replace("<br />", "\n")
        return re.sub(r"\n\s*\n+", "\n", text).strip()
