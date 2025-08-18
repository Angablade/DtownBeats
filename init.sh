#!/bin/bash

set -e

# Environment variables for auto-update control
AUTO_UPDATE_INIT=${AUTO_UPDATE_INIT:-true}
DISABLE_INIT_UPDATE=${DISABLE_INIT_UPDATE:-false}

# Check if running in Docker container
is_docker() {
    [ -f /.dockerenv ] || [ "${container:-}" = "docker" ] || [ -n "${KUBERNETES_SERVICE_HOST:-}" ]
}

# Function to check if init.sh needs updating
check_init_update() {
    if [ "$DISABLE_INIT_UPDATE" = "true" ] || [ "$AUTO_UPDATE_INIT" = "false" ]; then
        echo "Init script auto-update is disabled."
        return 0
    fi

    echo "Checking for init.sh updates..."
    local current_script="/app/init.sh"
    local temp_script="/tmp/init_new.sh"
    
    # Download the latest init.sh
    for repo in "${REPO_URLS[@]}"; do
        if wget -q -O "$temp_script" "$repo/init.sh"; then
            # Compare files
            if ! cmp -s "$current_script" "$temp_script" 2>/dev/null; then
                echo "New init.sh version detected. Updating..."
                cp "$temp_script" "$current_script"
                chmod +x "$current_script"
                rm -f "$temp_script"
                echo "Init script updated. Restarting with new version..."
                exec "$current_script"
            else
                echo "Init script is up to date."
                rm -f "$temp_script"
            fi
            break
        fi
    done
}

# Detect Docker environment and configure paths accordingly
if is_docker; then
    echo "?? Running in Docker environment"
    APP_DIR="/app"
    LYRICS_DIR="/app/lyrics"
    MUSIC_DIR="/app/music"
    CONFIG_DIR="/app/config"
else
    echo "??? Running in local environment"
    APP_DIR="."
    LYRICS_DIR="./lyrics"
    MUSIC_DIR="./music"
    CONFIG_DIR="./config"
fi

# Update and install dependencies (only in Docker)
if is_docker; then
    apt-get update && apt-get upgrade -y && apt-get install -y wget python3-pip ffmpeg p7zip-full apt-utils libopus-dev psutils
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Remove any conflicting legacy discord packages
    pip uninstall -y discord.py discord 2>/dev/null || true
    
    # Install Python packages (py-cord instead of discord.py)
    pip install --no-cache-dir "pybind11>=2.12" "numpy<2" py-cord pyyaml requests yt-dlp asyncio aiohttp pillow \
        musicbrainzngs beautifulsoup4 aiofiles ffmpeg-python ffmpeg PyNaCl fuzzywuzzy python-Levenshtein spotdl \
        stt fastapi uvicorn httpx python-multipart python-dotenv authlib starlette itsdangerous psutil
else
    echo "?? Local environment detected. Please ensure all dependencies are installed manually."
    echo "Run: pip install -r requirements.txt"
fi

# Ensure necessary directories exist
for dir in "${LYRICS_DIR}" "${MUSIC_DIR}" "${CONFIG_DIR}" "${APP_DIR}/models" "${APP_DIR}/sources" "${APP_DIR}/utils" "${APP_DIR}/albumart" "${APP_DIR}/metacache" "${APP_DIR}/static" "${APP_DIR}/cmds"; do
    mkdir -p "$dir" && chmod 777 "$dir"
done

# Define repositories and files to download
REPO_URLS=(
    "https://raw.githubusercontent.com/Angablade/DtownBeats/refs/heads/master"
    "https://angablade.com/stuff/dtownbeats"
)

# Updated FILES array to include all cog files
FILES=(
    "bot3.py" 
    "utils/youtube_pl.py" "utils/voice_utils.py" "utils/albumart.py" "utils/metadata.py" "utils/web_app.py" "utils/common.py" "utils/lyrics.py"
    "sources/youtube_mp3.py" "sources/spotify_mp3.py" "sources/soundcloud_mp3.py" "sources/bandcamp_mp3.py" "sources/apple_music_mp3.py"
    "cmds/admin.py" "cmds/config.py" "cmds/events.py" "cmds/info.py" "cmds/lyrics.py" "cmds/metadata.py" "cmds/moderation.py" "cmds/music.py" "cmds/queue.py" "cmds/voice.py"
)

# Check for init.sh updates first (only in Docker)
if is_docker; then
    check_init_update
fi

# Function to download files with fallback
download_file() {
    local file=$1
    local target_path="${APP_DIR}/${file}"
    
    # Create directory if it doesn't exist
    mkdir -p "$(dirname "$target_path")"
    
    for repo in "${REPO_URLS[@]}"; do
        if wget -q --show-progress -O "$target_path" "$repo/$file"; then
            echo "? Downloaded $file from $repo"
            return 0
        fi
    done
    echo "? Failed to download $file from all sources."
    return 1
}

# Download necessary files
echo "?? Downloading project files..."
for file in "${FILES[@]}"; do
    download_file "$file"
done

# Model and scorer download URLs (only in Docker)
if is_docker; then
    MODEL_DIR="${APP_DIR}/models"
    MODEL_FILE="$MODEL_DIR/model.tflite"
    SCORER_FILE="$MODEL_DIR/scorer.scorer"

    MODEL_URL="https://coqui.gateway.scarf.sh/english/coqui/v1.0.0-huge-vocab/model.tflite"
    SCORER_URL="https://coqui.gateway.scarf.sh/english/coqui/v1.0.0-huge-vocab/huge-vocabulary.scorer"

    echo "?? Downloading AI models..."
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
fi

# Create configs.json template for local development
if ! is_docker && [ ! -f "${APP_DIR}/configs.json" ]; then
    echo "?? Creating configs.json template for local development..."
    cat > "${APP_DIR}/configs.json" << 'EOF'
{
    "BOT_TOKEN": "your_discord_bot_token_here",
    "MUSICBRAINZ_USERAGENT": "YourBotName/1.0",
    "MUSICBRAINZ_VERSION": "1.0",
    "MUSICBRAINZ_CONTACT": "your_email@example.com",
    "BOT_OWNER_ID": 123456789,
    "EXECUTOR_MAX_WORKERS": 10,
    "QUEUE_PAGE_SIZE": 10,
    "HISTORY_PAGE_SIZE": 10,
    "TIMEOUT_TIME": 60
}
EOF
    echo "?? Please edit configs.json with your actual configuration values before running the bot."
fi

# Environment-specific startup
if is_docker; then
    echo "?? Starting bot in Docker environment..."
    cd "${APP_DIR}"
    exec python3 bot3.py
else
    echo "?? Local environment setup complete!"
    echo "?? Next steps:"
    echo "  1. Edit configs.json with your bot token and other settings"
    echo "  2. Install dependencies: pip install -r requirements.txt"
    echo "  3. Run the bot: python bot3.py"
fi
