import asyncio
import re
import os
import aiohttp
from bs4 import BeautifulSoup
from discord import Embed

class AppleMusicScraper:
    def __init__(self, url, ctx):
        if not self.validate_url(url):
            raise ValueError("Invalid Apple Music URL")
        self.url = url
        self.ctx = ctx
        self.debug_info = []

    @staticmethod
    def validate_url(url: str) -> bool:
        return re.match(r'https?://music\.apple\.com/.+/song/.+/.+', url) is not None

    async def scrape_metadata(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url, headers=headers) as response:
                    html = await response.text()
                    self.debug_info.append(f"HTML content length: {len(html)}")
                    soup = BeautifulSoup(html, "html.parser")
                    title = soup.find("title").text.replace(" - Apple Music", "").strip()
                    self.debug_info.append(f"Scraped title: {title}")
                    return title
        except Exception as e:
            error_message = f"Error scraping Apple Music metadata: {e}"
            self.debug_info.append(error_message)
            print(error_message)
            return None

    async def search_youtube(self):
        metadata = await self.scrape_metadata()
        if not metadata:
            return None
        search_url = f"https://www.youtube.com/results?search_query={metadata.replace(' ', '+')}"
        self.debug_info.append(f"Search URL: {search_url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, headers=headers) as response:
                html = await response.text()
                self.debug_info.append(f"Search HTML content length: {len(html)}")
                video_ids = re.findall(r'"videoId":"([\w-]{11})"', html)
                @bot.command(name="applemusic", aliases=["ap"])
                async def applemusic(ctx, url: str):
                    async with ctx.typing():
                        guild_id = ctx.guild.id
                    
                        if not await check_perms(ctx, guild_id):
                            return

                        if not server_queues.get(guild_id):
                            server_queues[guild_id] = asyncio.Queue()
                            current_tracks[guild_id] = {"current_track": None, "is_looping": False}

                        await handle_voice_connection(ctx)
                    
                        await messagesender(bot, ctx.channel.id, f"Processing Apple Music link: <{url}>")
                        youtube_link = await get_apple_music_audio(url, ctx)
                        if youtube_link:
                            file_path = await get_audio_filename(youtube_link)
                            if file_path:
                                await queue_and_play_next(ctx, ctx.guild.id, file_path, "-{AppleMusic Link}-")
                            else:
                                await messagesender(bot, ctx.channel.id, "Failed to download Apple Music track.")
                        else:
                            await messagesender(bot, ctx.channel.id, "Failed to process Apple Music track.")
                self.debug_info.append(f"Found video IDs: {video_ids}")
                return f"https://www.youtube.com/watch?v={video_ids[0]}" if video_ids else None

    async def post_debug_info(self):
        embed = Embed(title="Debug Information", color=0x00ff00)
        for info in self.debug_info:
            embed.add_field(name="Debug Info", value=info, inline=False)
        await messagesender(self.ctx.bot, self.ctx.channel.id, embed=embed)

async def get_apple_music_audio(url, ctx):
    scraper = AppleMusicScraper(url, ctx)
    youtube_url = await scraper.search_youtube()
    await scraper.post_debug_info()
    return youtube_url
