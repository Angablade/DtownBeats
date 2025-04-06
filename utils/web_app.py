import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from starlette.staticfiles import StaticFiles
import uvicorn
import threading
import html
import base64
from utils.metadata import MetadataManager

if not os.path.exists("static"):
    os.makedirs("static")

app = FastAPI()
app.mount("/static", StaticFiles(directory="/app/static"), name="static")
app.mount("/albumart", StaticFiles(directory="/app/albumart"), name="albumart")

MUSICBRAINZ_USERAGENT = os.getenv("MUSICBRAINZ_USERAGENT", "default_user")
MUSICBRAINZ_VERSION = os.getenv("MUSICBRAINZ_VERSION", "1.0")
MUSICBRAINZ_CONTACT = os.getenv("MUSICBRAINZ_CONTACT", "default@example.com")
metadata_manager = MetadataManager("./metacache","./config/metadataeditors.json",MUSICBRAINZ_USERAGENT, MUSICBRAINZ_VERSION, MUSICBRAINZ_CONTACT)

server_queues = {}
now_playing = {}

def encode_image_as_base64(image_path):
    """Helper function to read an image file and return its base64 encoding."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

@app.get("/queues", response_class=HTMLResponse)
async def list_queues():
    html_content = """
    <html>
      <head>
        <title>Bot Queues</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 20px; }
          h1 { color: #333; text-align: center; }
          .tab { overflow: hidden; border-bottom: 1px solid #ccc; display: flex; }
          .tab button { background-color: inherit; border: none; outline: none; padding: 10px 15px; cursor: pointer; transition: 0.3s; font-size: 16px; }
          .tab button:hover { background-color: #ddd; }
          .tab button.active { background-color: #ccc; }
          .tabcontent { display: none; padding: 20px; border: 1px solid #ccc; border-top: none; }
          table { border-collapse: collapse; width: 100%; margin-top: 10px; }
          th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
          th { background-color: #f2f2f2; }
          img { max-width: 150px; display: block; margin: 10px auto; border-radius: 10px; }
        </style>
        <script>
          function openTab(evt, guildId) {
            var i, tabcontent, tablinks;
            tabcontent = document.getElementsByClassName("tabcontent");
            for (i = 0; i < tabcontent.length; i++) {
              tabcontent[i].style.display = "none";
            }
            tablinks = document.getElementsByClassName("tablinks");
            for (i = 0; i < tablinks.length; i++) {
              tablinks[i].className = tablinks[i].className.replace(" active", "");
            }
            document.getElementById(guildId).style.display = "block";
            evt.currentTarget.className += " active";
          }
        </script>
      </head>
      <body>
        <h1>Music Queues</h1>
        <div class="tab">
    """

    for guild_id in server_queues.keys():
        encoded_image = encode_image_as_base64(os.path.join("/static/", str(guild_id), ".png"))
        html_content += f'<button class="tablinks" onclick="openTab(event, \'tab-{guild_id}\')"><img src="data:image/png;base64,{encoded_image}" alt="{str(guild_id)}" /></button>'

    html_content += "</div>"

    for guild_id, queue in server_queues.items():
        html_content += f'<div id="tab-{guild_id}" class="tabcontent">'
        if guild_id in now_playing:
            song = now_playing[guild_id]
            
            metadata = metadata_manager.load_metadata(song[0])
            if not metadata:
                video_title = current_track[1]
                metadata = metadata_manager.get_or_fetch_metadata(song[0], song[1])
                metadata_manager.save_metadata(video_id, metadata)

            artist = metadata["artist"]
            title = metadata["title"]
            duration = metadata.get("duration", "Unknown")

            html_content += f"""
            <h2>Now Playing: {html.escape(artist)} - {html.escape(title)}</h2>
            <p><b>Length:</b> {html.escape(str(duration))}</p>
            <p><b>ID:</b> {html.escape(song[0])}</p>
            """
            if song[2]:
                album_art_path = song[2][4:]
                album_art_base64 = encode_image_as_base64(album_art_path)
                html_content += f'<img src="data:image/png;base64,{album_art_base64}" alt="Album Art">'
        
        html_content += """
        <h3>Upcoming Tracks:</h3>
        <table>
          <tr>
            <th>#</th>
            <th>Track ID</th>
            <th>Title</th>
          </tr>
        """
        for index, item in enumerate(queue._queue, start=1):
            track_id = html.escape(str(item[0]))
            title = html.escape(str(item[1]))
            html_content += f"""
            <tr>
              <td>{index}</td>
              <td><a href="https://youtube.com/watch?v={track_id}">{track_id}</a></td>
              <td>{title}</td>
            </tr>
            """
        html_content += "</table></div>"

    html_content += """
        <script>
          document.getElementsByClassName("tablinks")[0]?.click(); // Auto-open the first tab
        </script>
      </body>
    </html>
    """
    return HTMLResponse(content=html_content)


def run_web_app():
    uvicorn.run(app, host="0.0.0.0", port=80)

def start_web_server_in_background(queues, now_playing_songs):
    global server_queues, now_playing
    server_queues = queues
    now_playing = now_playing_songs
    thread = threading.Thread(target=run_web_app, daemon=True)
    thread.start()
