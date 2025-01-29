#!/bin/bash

apt-get update && apt-get upgrade && apt-get install -y git pip
REPO_URL="https://raw.githubusercontent.com/Angablade/DtownBeats/main"
FILES=("bot3.py" "lyrics.py" "youtube_mp3.py")

for file in "${FILES[@]}"; do
    git clone -b main "$REPO_URL/$file" /app/$file 
done

if [ ! -d "/app/lyrics" ]; then
    echo "Creating Lyrics Folder."
    mkdir -p /app/lyrics && chmod 777 -R /app/lyrics
fi

if [ ! -d "/app/music" ]; then
    echo "Creating Music Folder."
    mkdir -p /app/music && chmod 777 -R /app/music 
fi

if [ ! -d "/app/config" ]; then
    echo "Creating Config Folder."
    mkdir -p /app/config && chmod 777 -R /app/config
fi

pip install --no-cache-dir discord pyyaml requests yt-dlp asyncio aiohttp musicbrainzngs beautifulsoup4 aiofiles


echo "Starting bot..."
exec python3 /app/bot3.py 
