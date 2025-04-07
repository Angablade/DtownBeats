import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.staticfiles import StaticFiles
import uvicorn
import threading
import html
import base64
import logging
from utils.metadata import MetadataManager

app = FastAPI()

static_dir = "/app/static"
albumart_dir = "/app/albumart"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/albumart", StaticFiles(directory=albumart_dir), name="albumart")

MUSICBRAINZ_USERAGENT = os.getenv("MUSICBRAINZ_USERAGENT", "default_user")
MUSICBRAINZ_VERSION = os.getenv("MUSICBRAINZ_VERSION", "1.0")
MUSICBRAINZ_CONTACT = os.getenv("MUSICBRAINZ_CONTACT", "default@example.com")

metadata_manager = MetadataManager(
    "./metacache",
    "./config/metadataeditors.json",
    MUSICBRAINZ_USERAGENT,
    MUSICBRAINZ_VERSION,
    MUSICBRAINZ_CONTACT
)

server_queues = {}
now_playing = {}
track_history = {}

@app.get("/queues/{guild_id}", response_class=HTMLResponse)
async def list_queue_for_guild(guild_id: str):
    logging.info(f"Fetching queue for Guild ID: {guild_id}")
    if guild_id not in server_queues.keys():
        logging.warning(f"No queue found for Guild ID: {guild_id}")
        return HTMLResponse(
            content=f"<h1>No queue found for Guild ID: {guild_id}</h1>", status_code=404
        )

    html_content = f"""
    <html>
      <head>
        <title>Bot Queue - {guild_id}</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 20px; }}
          h1 {{ color: #333; text-align: center; }}
          table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
          th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
          th {{ background-color: #f2f2f2; }}
          img {{ max-width: 150px; display: block; margin: 10px auto; border-radius: 10px; }}
        </style>
      </head>
      <body>
        <h1>Music Queue for Guild ID: {guild_id}</h1>
    """

    queue = server_queues[guild_id]
    
    if guild_id in now_playing:
        song = now_playing[guild_id]
        
        metadata = metadata_manager.load_metadata(song[0])
        if not metadata:
            video_title = song[1]
            metadata = metadata_manager.get_or_fetch_metadata(song[0], song[1])
            metadata_manager.save_metadata(song[0], metadata)

        artist = metadata["artist"]
        title = metadata["title"]
        duration = metadata.get("duration", "Unknown")

        html_content += f"""
        <h2>Last Played: {html.escape(artist)} - {html.escape(title)}</h2>
        <p><b>Length:</b> {html.escape(str(duration))}</p>
        <p><b>ID:</b> {html.escape(song[0])}</p>
        """
        if song[2]:
            logging.info(f"Album art path: {song[2][4:]}")
            html_content += f'<img src="{song[2][4:]}" alt="Album Art">'
        else:
            html_content += f'<img src="/albumart/default.jpg" alt="Default Album Art">'
    
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
    
    html_content += "</table>"

    if guild_id in track_history:
        history = track_history[guild_id]
        html_content += "<h3>Track History:</h3>"
        html_content += "<table><tr><th>#</th><th>Track ID</th><th>Title</th></tr>"
        
        for index, item in enumerate(history, start=1):
            track_id = html.escape(str(item[0]))
            title = html.escape(str(item[1]))
            html_content += f"""
            <tr>
              <td>{index}</td>
              <td>{track_id}</td>
              <td>{title}</td>
            </tr>
            """
        
        html_content += "</table>"

    html_content += """</body></html>"""

    return HTMLResponse(content=html_content)

@app.get("/queues/{guild_id}/json")
async def queue_json_for_guild(guild_id: str):
    if guild_id not in server_queues:
        return JSONResponse(
            content={"error": f"No queue found for Guild ID: {guild_id}"}, status_code=404
        )
    
    response = {
        "last_played": now_playing.get(guild_id, None),
        "queue": [{"track_id": item[0], "title": item[1]} for item in server_queues[guild_id]._queue],
        "history": track_history.get(guild_id, [])
    }
    return JSONResponse(content=response)

@app.get("/queues/json")
async def all_queues_json():
    response = {}
    
    for guild_id, queue in server_queues.items():
        last_played = now_playing.get(guild_id, None)
        
        metadata = metadata_manager.load_metadata(last_played[0]) if last_played else {}
        track_info = {
            "artist": metadata.get("artist", "Unknown"),
            "title": metadata.get("title", "Unknown"),
            "duration": metadata.get("duration", "Unknown"),
            "track_id": last_played[0] if last_played else None
        }
        
        response[guild_id] = {
            "last_played": track_info,
            "queue": [{"track_id": item[0], "title": item[1]} for item in queue._queue],
            "history": track_history.get(guild_id, [])
        }

    return JSONResponse(content=response)

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
        encoded_image = f"/static/{guild_id}.png"
        html_content += f'<button class="tablinks" onclick="openTab(event, \'tab-{guild_id}\')"><img src="{encoded_image}" alt="{str(guild_id)}" /></button>'

    html_content += "</div>"

    for guild_id, queue in server_queues.items():
        html_content += f'<div id="tab-{guild_id}" class="tabcontent">'
        
        if guild_id in now_playing:
            song = now_playing[guild_id]
            
            metadata = metadata_manager.load_metadata(song[0])
            if not metadata:
                video_title = song[1]
                metadata = metadata_manager.get_or_fetch_metadata(song[0], song[1])
                metadata_manager.save_metadata(song[0], metadata)

            artist = metadata["artist"]
            title = metadata["title"]
            duration = metadata.get("duration", "Unknown")

            html_content += f"""
            <h2>Last played: {html.escape(artist)} - {html.escape(title)}</h2>
            <p><b>Length:</b> {html.escape(str(duration))}</p>
            <p><b>ID:</b> {html.escape(song[0])}</p>
            """
            if song[2]:
                html_content += f'<img src="/albumart/{song[2][4:]}" alt="Album Art">'
            else:
                html_content += f'<img src="/albumart/default.jpg" alt="Default Album Art">'
        
        html_content += "<h3>Upcoming Tracks:</h3><table><tr><th>#</th><th>Track ID</th><th>Title</th></tr>"
        
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
        
        html_content += "</table>"

        if guild_id in track_history:
            history = track_history[guild_id]
            html_content += "<h3>Track History:</h3><table><tr><th>#</th><th>Track ID</th><th>Title</th></tr>"
            
            for index, item in enumerate(history, start=1):
                track_id = html.escape(str(item[0]))
                title = html.escape(str(item[1]))
                html_content += f"""
                <tr>
                  <td>{index}</td>
                  <td>{track_id}</td>
                  <td>{title}</td>
                </tr>
                """
            
            html_content += "</table>"

        html_content += "</div>"
    
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

def start_web_server_in_background(queues, now_playing_songs, track_historys):
    global server_queues, now_playing, track_history
    server_queues = queues
    now_playing = now_playing_songs
    track_history = track_historys
    thread = threading.Thread(target=run_web_app, daemon=True)
    thread.start()