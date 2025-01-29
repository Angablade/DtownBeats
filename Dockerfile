FROM python:3.9

WORKDIR /app

COPY init.sh /init.sh
RUN chmod +x /init.sh

RUN pip install --no-cache-dir discord.py yt-dlp aiohttp musicbrainzngs beautifulsoup4 requests asyncio

CMD ["/init.sh"]
