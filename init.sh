#!/bin/bash

set -e

# Update and install dependencies
apt-get update && apt-get upgrade -y && apt-get install -y wget python3-pip ffmpeg p7zip-full apt-utils libopus-dev

# Upgrade pip and install necessary Python packages
pip install --upgrade pip
pip install --no-cache-dir "pybind11>=2.12" "numpy<2" py-cord pyyaml requests yt-dlp asyncio aiohttp pillow \
    musicbrainzngs beautifulsoup4 aiofiles ffmpeg-python ffmpeg PyNaCl fuzzywuzzy python-Levenshtein spotdl stt

# Ensure necessary directories exist
for dir in /app/{lyrics,music,config,models,sources,utils,albumart}; do
    mkdir -p "$dir" && chmod 777 "$dir"
done

# Define repositories and files to download
REPO_URLS=(
    "https://raw.githubusercontent.com/Angablade/DtownBeats/refs/heads/master"
    "https://angablade.com/stuff/dtownbeats"
)
FILES=(
    "bot3.py" "utils/lyrics.py" "utils/youtube_pl.py" "utils/voice_utils.py"
    "sources/youtube_mp3.py" "sources/spotify_mp3.py" "sources/soundcloud_mp3.py"
    "sources/bandcamp_mp3.py" "sources/apple_music_mp3.py" "utils/albumart.py"
)

# Function to download files with fallback
download_file() {
    local file=$1
    for repo in "${REPO_URLS[@]}"; do
        if wget -q --show-progress -O "/app/$file" "$repo/$file"; then
            echo "Downloaded $file from $repo"
            return 0
        fi
    done
    echo "Failed to download $file from all sources."
    return 1
}

# Download necessary files
for file in "${FILES[@]}"; do
    download_file "$file"
done

# Model and scorer download URLs
MODEL_DIR="/app/models"
MODEL_FILE="$MODEL_DIR/model.tflite"
SCORER_FILE="$MODEL_DIR/scorer.scorer"

MODEL_URL="https://coqui.gateway.scarf.sh/english/coqui/v1.0.0-huge-vocab/model.tflite"
SCORER_URL="https://coqui.gateway.scarf.sh/english/coqui/v1.0.0-huge-vocab/huge-vocabulary.scorer"

# Download model files if missing
for url in "$MODEL_URL" "$SCORER_URL"; do
    file="${MODEL_DIR}/$(basename $url)"
    if [ ! -f "$file" ]; then
        echo "Downloading $file..."
        wget -q --show-progress -O "$file" "$url" && echo "Downloaded: $file"
    else
        echo "$file already exists. Skipping download."
    fi
done

# Start the bot
echo "Starting bot..."
exec python3 /app/bot3.py
