#!/bin/bash

apt-get update && apt-get upgrade -y && apt-get install -y wget pip ffmpeg 
pip install --upgrade pip
pip install --no-cache-dir discord.py pyyaml requests yt-dlp asyncio aiohttp musicbrainzngs beautifulsoup4 aiofiles ffmpeg PyNaCl shutil

REPO_URLS=("https://raw.githubusercontent.com/Angablade/DtownBeats/refs/heads/master" "https://angablade.com/stuff/dtownbeats")
FILES=("bot3.py" "lyrics.py" "youtube_mp3.py")

for file in "${FILES[@]}"; do
    for repo in "${REPO_URLS[@]}"; do
        if wget -q --show-progress -O "/app/$file" "$repo/$file"; then
            echo "Downloaded $file from $repo"
            break
        else
            echo "Failed to download $file from $repo, trying next..."
        fi
    done
done

for dir in "/app/lyrics" "/app/music" "/app/config"; do
    if [ ! -d "$dir" ]; then
        echo "Creating directory $dir."
        mkdir -p "$dir" && chmod 777 "$dir"
    fi
done

echo "Starting bot..."
exec python3 /app/bot3.py
