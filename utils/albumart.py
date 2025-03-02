import os
import time
import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from PIL import Image
from io import BytesIO

class AlbumArtFetcher:
    CACHE_DIR = "/app/albumart"
    CACHE_EXPIRY = 14 * 24 * 60 * 60
    HEADERS = {"User-Agent": "Mozilla/5.0"}

    def __init__(self):
        if not os.path.exists(self.CACHE_DIR):
            os.makedirs(self.CACHE_DIR)

    def _get_cache_path(self, query):
        """Generate a cache file path using a hash of the query."""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return os.path.join(self.CACHE_DIR, f"{query_hash}.jpg")

    def _is_cache_valid(self, cache_path):
        """Check if the cached image is still valid."""
        return os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path)) < self.CACHE_EXPIRY

    def _fetch_image_url(self, query):
        """Fetch the first image result URL from Google Images."""
        search_url = f"https://www.google.com/search?hl=en&tbm=isch&q={quote(query)}"
        response = requests.get(search_url, headers=self.HEADERS)
        if response.status_code != 200:
            raise Exception("Failed to fetch search results.")

        soup = BeautifulSoup(response.text, "html.parser")
        img_tag = soup.find("img")
        if img_tag and "src" in img_tag.attrs:
            return img_tag["src"]
        return None

    def _download_image(self, url, save_path):
        """Download and save the image."""
        response = requests.get(url, headers=self.HEADERS)
        if response.status_code == 200:
            image = Image.open(BytesIO(response.content))
            image.save(save_path, "JPEG")

    def get_album_art(self, query):
        """Main function to get album art, using cache if available."""
        cache_path = self._get_cache_path(query)

        if self._is_cache_valid(cache_path):
            return cache_path  


        image_url = self._fetch_image_url(query)
        if image_url:
            self._download_image(image_url, cache_path)
            return cache_path

        return None 
