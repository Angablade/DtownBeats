#!/bin/bash

apt-get update && apt-get upgrade -y && apt-get install -y wget python3-pip ffmpeg p7zip-full

pip install --upgrade pip
pip install --no-cache-dir discord.py pyyaml requests yt-dlp asyncio aiohttp musicbrainzngs beautifulsoup4 aiofiles ffmpeg-python ffmpeg PyNaCl fuzzywuzzy python-Levenshtein numpy
pip install --no-cache-dir stt

REPO_URLS=("https://raw.githubusercontent.com/Angablade/DtownBeats/refs/heads/master" "https://angablade.com/stuff/dtownbeats")
FILES=("bot3.py" "lyrics.py" "youtube_mp3.py" "youtube_pl.py" "voice_utils.py")

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

for dir in "/app/lyrics" "/app/music" "/app/config" "/app/models"; do
    if [ ! -d "$dir" ]; then
        echo "Creating directory $dir."
        mkdir -p "$dir" && chmod 777 "$dir"
    fi
done

MODEL_DIR="/app/models"
MODEL_FILE="$MODEL_DIR/model.tflite"
SCORER_FILE="$MODEL_DIR/scorer.scorer"

MODEL_URL="https://coqui.gateway.scarf.sh/english/coqui/v1.0.0-huge-vocab/model.tflite"
SCORER_URL="https://coqui.gateway.scarf.sh/english/coqui/v1.0.0-huge-vocab/huge-vocabulary.scorer"

download_file() {
    local url=$1
    local destination=$2
    if [ ! -f "$destination" ]; then
        echo "Downloading $destination..."
        wget -q --show-progress -O "$destination" "$url"
        echo "Downloaded: $destination"
    else
        echo "$destination already exists. Skipping download."
    fi
}

download_file "$MODEL_URL" "$MODEL_FILE"
download_file "$SCORER_URL" "$SCORER_FILE"

echo "Starting bot..."
exec python3 /app/bot3.py