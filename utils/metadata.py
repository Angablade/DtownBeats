import os
import json
import musicbrainzngs

class MetadataManager:
    def __init__(self, cache_dir, editor_file, USERAGENT, CON_VERSION, CONTACT):
        self.cache_dir = cache_dir
        self.editor_file = editor_file
        self.editor_ids = self.load_editors()
        os.makedirs(cache_dir, exist_ok=True)
        musicbrainzngs.set_useragent(USERAGENT, CON_VERSION, CONTACT)

    def _get_metadata_path(self, filename):
        base, _ = os.path.splitext(filename)
        return os.path.join(self.cache_dir, f"{base}.json")

    def load_metadata(self, filename):
        metadata_path = self._get_metadata_path(filename)
        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                return json.load(f)
        return None

    def save_metadata(self, filename, metadata):
        metadata_path = self._get_metadata_path(filename)
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=4)

    def fetch_metadata(self, query):
        print(f"Fetching metadata for {query}")
        try:
            result = musicbrainzngs.search_recordings(query, limit=5)
            if "recording-list" in result:
                recordings = result["recording-list"]
                refined_results = []
                for recording in recordings:
                    artist = recording["artist-credit"][0]["artist"]["name"]
                    title = recording["title"]
                    album = recording["release-list"][0]["title"] if "release-list" in track else "Unknown"
                    duration = recording.get("length")
                    refined_results.append({
                        "artist": artist,
                        "title": title,
                        "album": album,
                        "duration": duration,
                        "image_path": None
                    })
                return refined_results
        except Exception as e:
            print(f"Error fetching metadata: {e}")
        return {"title": title, "artist": artist or "Unknown", "album": "Unknown", "duration": 0, "image_path": None}

    def get_or_fetch_metadata(self, filename, title, artist=None):
        metadata = self.load_metadata(filename)
        if not metadata:
            metadata = self.fetch_metadata(title, artist)
            self.save_metadata(filename, metadata)
        return metadata

    def update_metadata(self, filename, key, value):
        metadata = self.load_metadata(filename) or {}
        metadata[key] = value
        self.save_metadata(filename, metadata)
    
    def load_editors(self):
        if os.path.exists(self.editor_file):
            with open(self.editor_file, "r") as f:
                return set(json.load(f))
        return set()

    def save_editors(self):
        with open(self.editor_file, "w") as f:
            json.dump(list(self.editor_ids), f, indent=4)
    
    def add_editor(self, user_id):
        self.editor_ids.add(user_id)
        self.save_editors()
    
    def remove_editor(self, user_id):
        self.editor_ids.discard(user_id)
        self.save_editors()
