import aiohttp
import asyncio
import json
import random

async def grab_youtube_pl(query):
    url = "https://music.youtube.com/youtubei/v1/search?prettyPrint=false"
    
    headers = {
        "Host": "music.youtube.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/json",
        "Referer": "https://music.youtube.com/",
        "X-Youtube-Client-Name": "67",
        "X-Youtube-Client-Version": "1.20250204.03.00",
        "X-Goog-AuthUser": "0",
        "X-Origin": "https://music.youtube.com",
        "Origin": "https://music.youtube.com",
        "DNT": "1",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "same-origin",
        "Sec-Fetch-Site": "same-origin",
        "Connection": "keep-alive",
        "Priority": "u=0",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    }

    payload = {
        "context": {
            "client": {
                "clientName": "WEB_REMIX",
                "clientVersion": "1.20250204.03.00",
            }
        },
        "query": query
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status != 200:
                return json.dumps({"error": f"Request failed with status {response.status}"}, indent=2)
            
            try:
                data = await response.json()
            except aiohttp.ContentTypeError:
                return json.dumps({"error": "Invalid JSON response"}, indent=2)

    playlist_ids = set()

    def find_playlists(obj):
        """Recursively search for playlistId keys in nested JSON."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "playlistId" and isinstance(value, str) and value.startswith("PL"):
                    playlist_ids.add(value)
                else:
                    find_playlists(value)
        elif isinstance(obj, list):
            for item in obj:
                find_playlists(item)

    find_playlists(data)
    playlist_urls = [f"{pl_id}" for pl_id in playlist_ids]
    random.shuffle(playlist_urls)

    return json.dumps(playlist_urls, indent=2)