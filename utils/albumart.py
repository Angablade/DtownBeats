import os
import time
import hashlib
import requests
import logging
import base64
from bs4 import BeautifulSoup
from urllib.parse import quote
from PIL import Image
from io import BytesIO
import yt_dlp

class AlbumArtFetcher:
    CACHE_DIR = "/app/albumart"
    CACHE_EXPIRY = 14 * 24 * 60 * 60
    HEADERS = {"User-Agent": "Mozilla/5.0"}
    LOG_FILE = "/app/config/debug.log"
    DEFAULT_IMAGE_PATH = os.path.join(CACHE_DIR, "default.jpg")
    DEFAULT_IMAGE_BASE64 = "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+AjIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/yQARCABAAEADAREAAhEBAxEB/8wACgAQEAUBEBEF/9oADAMBAAIRAxEAPwDSLIy8AHFzVcyDsbHUSvxfsUN8HqZXWk1U/Vk2qhJ/kW0Wiyx4kCMpaQjyXe+wBeYCUeo0dfWhH0XTK0kJzTF6KmHcd4t68h8kCpnC6+7aRFHc4kod5qE6X2aEhb0DoejKYarN3Q2Y3Ve4LnGjf+enkboVHmN0QHbuR0fVXIWyY/ibBlCW+ZZqIQIBqtGW/a00EmF4nHHxpMftRgm91A12+Hj7wlUgg3Ly7BmDxN9uFIzkxo0sVgigUe6hMnpm/wCOdCmKaeHX/L9GIEFbx56sNZVvveuUjN2kACrbfgYHYojx6yMRCuuvTir8FlwlCvZShwDuL4gP/9k="

    def __init__(self):
        if not os.path.exists(self.CACHE_DIR):
            os.makedirs(self.CACHE_DIR)

        logging.basicConfig(
            filename=self.LOG_FILE,
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

        self._ensure_default_image()

    def _ensure_default_image(self):
        if not os.path.exists(self.DEFAULT_IMAGE_PATH):
            image_data = base64.b64decode(self.DEFAULT_IMAGE_BASE64)
            with open(self.DEFAULT_IMAGE_PATH, "wb") as f:
                f.write(image_data)
            logging.info("Default album art created.")

    def _get_cache_path(self, query):
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return os.path.join(self.CACHE_DIR, f"{query_hash}.jpg")

    def _is_cache_valid(self, cache_path):
        return os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path)) < self.CACHE_EXPIRY

    def _fetch_image_url_google(self, query):
        encoded_query = query.replace(" ", "+")
        url = f"https://www.google.com/search?client=firefox-b-1-d&q={encoded_query}+album&udm=2"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        
        try:
            response = requests.get(url, headers=headers)
            cont = response.text.split('"')
            for itm in cont:
                if itm.startswith("http") and ".jpg" in itm:
                    return itm 
        except Exception as e:
            logging.error(f"Error fetching image URL: {e}")
        
        return None

    def _download_image(self, url, save_path):
        try:
            logging.info(f"Downloading image from URL: {url}")
            response = requests.get(url, headers=self.HEADERS)
            if response.status_code == 200:
                image = Image.open(BytesIO(response.content))
                image.save(save_path, "JPEG")
                logging.info(f"Image downloaded and saved to {save_path}")
                return True
            else:
                logging.error(f"Failed to download image, status code: {response.status_code}")
        except Exception as e:
            logging.error(f"Error downloading image: {e}")
        return False

    def get_album_art(self, query):
        cache_path = self._get_cache_path(query)

        if self._is_cache_valid(cache_path):
            logging.info(f"Cache hit for query: {query}. Returning cached image.")
            return cache_path

        image_url = self._fetch_image_url_google(query)

        if image_url and self._download_image(image_url, cache_path):
            return cache_path
        
        logging.warning(f"Failed to fetch album art for query: {query}, returning default.")
        return self.DEFAULT_IMAGE_PATH
