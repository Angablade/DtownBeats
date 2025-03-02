import os
import time
import hashlib
import requests
import logging
from bs4 import BeautifulSoup
from urllib.parse import quote
from PIL import Image
from io import BytesIO
import yt_dlp

class AlbumArtFetcher:
    CACHE_DIR = "/app/albumart"
    CACHE_EXPIRY = 14 * 24 * 60 * 60
    HEADERS = {"User-Agent": "Mozilla/5.0"}
    LOG_FILE = os.path.join(CACHE_DIR, "log.txt")

    def __init__(self):
        if not os.path.exists(self.CACHE_DIR):
            os.makedirs(self.CACHE_DIR)

        # Setup logging
        logging.basicConfig(
            filename=self.LOG_FILE,
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def _get_cache_path(self, query):
        """Generate a cache file path using a hash of the query."""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return os.path.join(self.CACHE_DIR, f"{query_hash}.jpg")

    def _is_cache_valid(self, cache_path):
        """Check if the cached image is still valid."""
        return os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path)) < self.CACHE_EXPIRY

    def _fetch_image_url_google(self, query):
        """Fetch the first image result URL from Google Images within the 'search' div."""
        search_url = f"https://www.google.com/search?hl=en&tbm=isch&q={quote(query)}"
        try:
            logging.info(f"Fetching image from Google Images for query: {query}")
            response = requests.get(search_url, headers=self.HEADERS)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch Google search results: {e}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        search_div = soup.find("div", {"id": "search"})
        
        if search_div:
            img_tag = search_div.find("img")
            if img_tag and "src" in img_tag.attrs:
                img_url = img_tag["src"]
                logging.info(f"Found image URL from Google: {img_url}")
                return img_url
        logging.warning(f"No image found in Google search results for query: {query}")
        return None

    def _fetch_image_url_youtube(self, query):
        """Fetch album art from YouTube video thumbnail using yt-dlp."""
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'force_generic_extractor': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_url = f"https://www.youtube.com/results?search_query={quote(query)}"
            logging.info(f"Fetching image from YouTube for query: {query}")
            try:
                info_dict = ydl.extract_info(search_url, download=False)
                if 'thumbnail' in info_dict:
                    img_url = info_dict['thumbnail']
                    logging.info(f"Found image URL from YouTube: {img_url}")
                    return img_url
            except Exception as e:
                logging.error(f"Failed to fetch YouTube results: {e}")
        return None

    def _fetch_image_url_unsplash(self, query):
        """Fetch album art from Unsplash using their search results (scraping)."""
        search_url = f"https://unsplash.com/s/photos/{quote(query)}"
        try:
            logging.info(f"Fetching image from Unsplash for query: {query}")
            response = requests.get(search_url, headers=self.HEADERS)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch Unsplash search results: {e}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        img_tag = soup.find("img", {"class": "_2zEKz"})
        if img_tag and "src" in img_tag.attrs:
            img_url = img_tag["src"]
            logging.info(f"Found image URL from Unsplash: {img_url}")
            return img_url
        logging.warning(f"No image found in Unsplash search results for query: {query}")
        return None

    def _download_image(self, url, save_path):
        """Download and save the image."""
        try:
            logging.info(f"Downloading image from URL: {url}")
            response = requests.get(url, headers=self.HEADERS)
            if response.status_code == 200:
                image = Image.open(BytesIO(response.content))
                image.save(save_path, "JPEG")
                logging.info(f"Image downloaded and saved to {save_path}")
            else:
                logging.error(f"Failed to download image, status code: {response.status_code}")
        except Exception as e:
            logging.error(f"Error downloading image: {e}")

    def get_album_art(self, query):
        """Main function to get album art, using cache if available."""
        cache_path = self._get_cache_path(query)

        if self._is_cache_valid(cache_path):
            logging.info(f"Cache hit for query: {query}. Returning cached image.")
            return cache_path

        # Try fetching the image from multiple sources
        image_url = self._fetch_image_url_google(query)
        if not image_url:
            image_url = self._fetch_image_url_youtube(query)
        if not image_url:
            image_url = self._fetch_image_url_unsplash(query)

        if image_url:
            self._download_image(image_url, cache_path)
            return cache_path
        logging.warning(f"Failed to fetch album art for query: {query}")
        return None
