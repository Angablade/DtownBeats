# Cog for lyrics commands
from discord.ext import commands
import discord
import asyncio
import musicbrainzngs
import logging
import os
import re
import requests
import aiohttp
import yt_dlp
from bs4 import BeautifulSoup
from discord import Embed

# Lyrics search URLs and headers
YOUTUBE_MUSIC_SEARCH_URL = "https://music.youtube.com/search?q={query}"
YOUTUBE_MUSIC_BASE_URL = "https://music.youtube.com"
GENIUS_SEARCH_URL = "https://genius.com/search?q={query}"
LYRICS_OVH_URL = "https://api.lyrics.ovh/v1/{artist}/{song}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

class LyricsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_lyrics(self, song, artist, read_cache=True):
        """Try Lyrics.ovh first, then Genius, YouTube Music, and finally AZLyrics."""
        lyrics_dir = os.path.join(os.getcwd(), "lyrics")
        os.makedirs(lyrics_dir, exist_ok=True)
        filepath = os.path.join(lyrics_dir, f"{artist} - {song}.txt")

        # Read from cache if enabled
        if read_cache and os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as file:
                return file.read()

        # 1. Try Lyrics.ovh
        lyrics = await self.get_lyrics_from_lyrics_ovh(artist, song)
        if lyrics:
            self.save_to_cache(filepath, lyrics)
            return lyrics

        # 2. Try Genius
        lyrics = await self.get_lyrics_from_genius(artist, song)
        if lyrics:
            self.save_to_cache(filepath, lyrics)
            return lyrics

        # 3. Try YouTube Music
        lyrics = await self.get_lyrics_from_youtube_music(artist, song)
        if lyrics:
            self.save_to_cache(filepath, lyrics)
            return lyrics

        # 4. Try AZLyrics (Last Resort)
        lyrics = await self.get_lyrics_from_azlyrics(artist, song)
        if lyrics:
            self.save_to_cache(filepath, lyrics)
            return lyrics

        return None

    def save_to_cache(self, filepath, lyrics):
        """Save lyrics to cache file."""
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(lyrics)

    async def get_lyrics_from_lyrics_ovh(self, artist, song):
        """Get lyrics from Lyrics.ovh API."""
        logging.info("Trying Lyrics.ovh...")
        url = LYRICS_OVH_URL.format(artist=artist, song=song)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=HEADERS) as response:
                    if response.status == 200:
                        json_data = await response.json()
                        return json_data.get("lyrics")
        except Exception as e:
            logging.error(f"Error fetching from Lyrics.ovh: {e}")
        return None

    async def search_genius(self, artist, song):
        """Search for song lyrics on Genius and return top hit if it matches."""
        logging.info("Trying Genius...")
        query = f"{artist} {song}".replace(" ", "%20")
        search_url = GENIUS_SEARCH_URL.format(query=query)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=HEADERS) as response:
                    if response.status != 200:
                        return None

                    html_content = await response.text()
                    soup = BeautifulSoup(html_content, "html.parser")
                    top_result = soup.select_one("search-result-item a.mini_card")

                    if top_result and "href" in top_result.attrs:
                        song_title = soup.select_one("div.mini_card-title").get_text(strip=True)
                        artist_name = soup.select_one("div.mini_card-subtitle").get_text(strip=True)

                        # Verify that the top hit matches the requested song and artist
                        if song.lower() in song_title.lower() and artist.lower() in artist_name.lower():
                            return top_result["href"]
        except Exception as e:
            logging.error(f"Error searching Genius: {e}")

        return None

    async def get_lyrics_from_genius(self, artist, song):
        """Scrape lyrics from a Genius song page."""
        song_url = await self.search_genius(artist, song)
        if not song_url:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(song_url, headers=HEADERS) as response:
                    if response.status != 200:
                        return None

                    html_content = await response.text()
                    soup = BeautifulSoup(html_content, "html.parser")
                    lyrics_div = soup.find("div", class_=re.compile("Lyrics__Container"))
                    return lyrics_div.get_text(separator="\n").strip() if lyrics_div else None
        except Exception as e:
            logging.error(f"Error fetching lyrics from Genius: {e}")
        return None

    async def search_youtube_music(self, artist, song):
        """Search YouTube Music for the song and return the first video link."""
        logging.info("Trying YouTube Music...")
        query = f"{artist} {song}".replace(" ", "+")
        search_url = YOUTUBE_MUSIC_SEARCH_URL.format(query=query)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=HEADERS) as response:
                    if response.status != 200:
                        return None

                    html_content = await response.text()
                    soup = BeautifulSoup(html_content, "html.parser")
                    result = soup.find("a", class_="yt-simple-endpoint style-scope yt-formatted-string")
                    return YOUTUBE_MUSIC_BASE_URL + result["href"] if result and result.get("href") else None
        except Exception as e:
            logging.error(f"Error searching YouTube Music: {e}")
        return None

    async def get_lyrics_from_youtube_music(self, artist, song):
        """Scrape lyrics from a YouTube Music video page."""
        video_url = await self.search_youtube_music(artist, song)
        if not video_url:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(video_url, headers=HEADERS) as response:
                    if response.status != 200:
                        return None

                    html_content = await response.text()
                    soup = BeautifulSoup(html_content, "html.parser")
                    lyrics_button = soup.find("button", id="description-button")
                    if not lyrics_button:
                        return None

                    lyrics_element = lyrics_button.find("yt-formatted-string", class_="description")
                    return lyrics_element.get_text(separator="\n").strip() if lyrics_element else None
        except Exception as e:
            logging.error(f"Error fetching lyrics from YouTube Music: {e}")
        return None

    async def get_lyrics_from_azlyrics(self, artist, song):
        """Scrape lyrics from AZLyrics."""
        logging.info("Trying AZLyrics...")
        artist_cleaned = re.sub(r'[\W_]+', '', artist).lower()
        song_cleaned = re.sub(r'[\W_]+', '', song).lower()
        url = f"https://www.azlyrics.com/lyrics/{artist_cleaned}/{song_cleaned}.html"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    response.raise_for_status()
                    html = await response.text()
                    start_marker = "<!-- Usage of azlyrics.com content by any third-party lyrics provider is prohibited by our licensing agreement. Sorry about that. -->"
                    end_marker = "<!-- MxM banner -->"
                    if start_marker in html and end_marker in html:
                        lyrics = html.split(start_marker, 1)[-1].split(end_marker, 1)[0]
                        return self.strip_html(lyrics)
        except Exception as e:
            logging.error(f"Error fetching from AZLyrics: {e}")
        return None

    @staticmethod
    def strip_html(html):
        """Remove HTML tags and clean up text."""
        text = re.sub(r"<.*?>", " ", html)
        text = text.replace("<br>", "\n").replace("<br />", "\n")
        return re.sub(r"\n\s*\n+", "\n", text).strip()

    @commands.command(name="lyrics", aliases=["lyr"])
    async def lyrics_cmd(self, ctx, *, song: str = None):
        """Get lyrics for the currently playing song or a specified song"""
        async with ctx.typing():
            # Import utils functions
            from utils.common import check_perms, messagesender, fetch_video_id_from_ytsearch, get_youtube_video_title
            
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return
            
            server_queues = getattr(self.bot, 'server_queues', {})
            current_tracks = getattr(self.bot, 'current_tracks', {})

            try:
                if not song:
                    current_track = current_tracks.get(guild_id, {}).get("current_track")
                    if not current_track:
                        await messagesender(self.bot, ctx.channel.id, content="No song is currently playing.")
                        return
                    video_title = ''.join(current_track[1:])
                else:
                    video_id = await fetch_video_id_from_ytsearch(song, ctx, self.bot)
                    if not video_id:
                        return 
                    video_title = await get_youtube_video_title(video_id)

                result = musicbrainzngs.search_recordings(query=video_title, limit=1)
                if not result["recording-list"]:
                    await messagesender(self.bot, ctx.channel.id, f"No matching song found on MusicBrainz for: {song or video_title}")
                    return

                recording = result["recording-list"][0]
                artist_name = recording["artist-credit"][0]["artist"]["name"]
                track_title = recording["title"]

                lyrics = await self.get_lyrics(track_title, artist_name)
                if lyrics:
                    embed = Embed(
                        title=f"Lyrics: {track_title} by {artist_name}",
                        description=lyrics[:2048],
                        color=discord.Color.purple()
                    )
                    await messagesender(self.bot, ctx.channel.id, embed=embed)
                else:
                    await messagesender(self.bot, ctx.channel.id, f"Lyrics not found for: {track_title} by {artist_name}")

            except Exception as e:
                await messagesender(self.bot, ctx.channel.id, f"An error occurred: {e}")

async def setup(bot):
    await bot.add_cog(LyricsCog(bot))
