set -e

echo "Updating system packages..."
apt-get update && apt-get install -y git

echo "Downloading latest bot files from GitHub..."
REPO_URL="https://raw.githubusercontent.com/Angablade/DtownBeats/main"
FILES=("bot3.py" "lyrics.py" "youtube_mp3.py")

for file in "${FILES[@]}"; do
    wget -O "/app/$file" "$REPO_URL/$file"
done

echo "Installing required Python libraries..."
pip install --no-cache-dir -r <(python3 -m pip freeze)

echo "Starting bot..."
exec python3 /app/bot3.py
