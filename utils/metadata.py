import os
import json
import musicbrainzngs
import ffmpeg
import subprocess

class MetadataManager:
    def __init__(self, cache_dir, editors_file, useragent, version, contact):
        self.cache_dir = cache_dir
        self.editors_file = editors_file
        self.editor_ids = self.load_editors()
        musicbrainzngs.set_useragent(useragent, version, contact)
        os.makedirs(cache_dir, exist_ok=True)

    def load_editors(self):
        if os.path.exists(self.editors_file):
            with open(self.editors_file, 'r') as f:
                return json.load(f).get("editors", [])
        return []

    def save_editors(self):
        with open(self.editors_file, 'w') as f:
            json.dump({"editors": self.editor_ids}, f, indent=4)

    def add_editor(self, user_id):
        if user_id not in self.editor_ids:
            self.editor_ids.append(user_id)
            self.save_editors()

    def remove_editor(self, user_id):
        if user_id in self.editor_ids:
            self.editor_ids.remove(user_id)
            self.save_editors()

    def get_metadata_path(self, filename):
        return os.path.join(self.cache_dir, f"{filename}.json")

    def load_metadata(self, filename):
        metadata_path = self.get_metadata_path(filename)
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                return json.load(f)
        return None

    def save_metadata(self, filename, metadata):
        metadata_path = self.get_metadata_path(filename)
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=4)

    def fetch_metadata(self, query):
        result = musicbrainzngs.search_recordings(query=query, limit=1)
        if result["recording-list"]:
            recording = result["recording-list"][0]
            artist = recording["artist-credit"][0]["artist"]["name"]
            title = recording["title"]
            duration = int(recording.get("length", 0)) // 1000
            return {"artist": artist, "title": title, "duration": duration}
        return {"artist": "Unknown Artist", "title": query, "duration": "Unknown"}

    def get_or_fetch_metadata(self, filename, query):
        metadata = self.load_metadata(filename)
        if not metadata:
            metadata = self.fetch_metadata(query)
            self.save_metadata(filename, metadata)
        return metadata

    def update_metadata(self, filename, key, value):
        metadata = self.load_metadata(filename)
        if metadata:
            metadata[key] = value
            self.save_metadata(filename, metadata)

    def ffmpeg_get_track_length(self, path):
        try:
            result = subprocess.run(
                ["ffmpeg", "-i", path, "-f", "null", "-"],
                stderr=subprocess.PIPE,
                text=True
            )
            duration_line = [line for line in result.stderr.split("\n") if "Duration" in line]
            if duration_line:
                time_str = duration_line[0].split(",")[0].split("Duration:")[1].strip()
                h, m, s = map(float, time_str.split(":"))
                return int(h * 3600 + m * 60 + s)
        except Exception as e:
            print(f"Error getting duration: {e}")
        return None