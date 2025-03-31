import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from starlette.staticfiles import StaticFiles
import uvicorn
import threading
import html

if not os.path.exists("static"):
    os.makedirs("static")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

server_queues = {}
now_playing = {}

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
        html_content += f'<button class="tablinks" onclick="openTab(event, \'tab-{guild_id}\')">{html.escape(str(guild_id))}</button>'

    html_content += "</div>"

    for guild_id, queue in server_queues.items():
        html_content += f'<div id="tab-{guild_id}" class="tabcontent">'
        if guild_id in now_playing:
            song = now_playing[guild_id]
            html_content += f"""
            <h2>Now Playing: {html.escape(song['title'])}</h2>
            <p><b>Artist:</b> {html.escape(song['artist'])}</p>
            <p><b>Album:</b> {html.escape(song['album'])}</p>
            """
            if song["album_art"]:
                html_content += f'<img src="{html.escape(song["album_art"])}" alt="Album Art">'
        
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
