import os
import html
import base64
import logging
import threading
import json
import csv
import io
import time
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse, FileResponse
from starlette.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import uvicorn
from xml.etree.ElementTree import Element, tostring
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv

from utils.metadata import MetadataManager

load_dotenv()

app = FastAPI()

# Add session middleware for authentication sessions
SESSION_SECRET = os.getenv("SESSION_SECRET", "change_me_secret")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

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

# Add OAuth setup at module level
oauth = OAuth()

def initialize_oauth():
    """Initialize OAuth client if credentials are available"""
    discord_client_id = os.getenv('DISCORD_CLIENT_ID')
    discord_client_secret = os.getenv('DISCORD_CLIENT_SECRET')
    
    if discord_client_id and discord_client_secret:
        oauth.register(
            name='discord',
            client_id=discord_client_id,
            client_secret=discord_client_secret,
            server_metadata_url='https://discord.com/.well-known/openid_connect',
            client_kwargs={
                'scope': 'identify guilds'
            }
        )
        return True
    return False

# Initialize OAuth on import
oauth_available = initialize_oauth()

def dict_to_xml(data, root_element="data"):
    """
    Recursively convert a dictionary to an XML string.
    """
    def build_element(parent, d):
        if isinstance(d, dict):
            for k, v in d.items():
                child = Element(str(k))
                parent.append(child)
                build_element(child, v)
        elif isinstance(d, list):
            for item in d:
                item_elem = Element("item")
                parent.append(item_elem)
                build_element(item_elem, item)
        else:
            parent.text = str(d)
    root = Element(root_element)
    build_element(root, data)
    return tostring(root, encoding='unicode')

def dict_to_csv(data):
    """
    Convert a dictionary to CSV.
    If data is a dict of dicts (as in /queues), each key becomes a row id.
    For a simple dict (as in /queue) a single row is generated.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    if isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
        sample = next(iter(data.values()))
        header = ["guild_id"] + list(sample.keys())
        writer.writerow(header)
        for guild_id, val in data.items():
            row = [guild_id]
            for key in header[1:]:
                cell = val.get(key, "")
                if isinstance(cell, (dict, list)):
                    cell = json.dumps(cell)
                row.append(cell)
            writer.writerow(row)
    else:
        header = list(data.keys())
        writer.writerow(header)
        row = []
        for key in header:
            cell = data[key]
            if isinstance(cell, (dict, list)):
                cell = json.dumps(cell)
            row.append(cell)
        writer.writerow(row)
    return output.getvalue()

def dict_to_yaml(data, indent=0):
    """
    Naively convert a dictionary to a YAML formatted string.
    This simple function handles dicts, lists, and basic values.
    """
    lines = []
    prefix = "  " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(dict_to_yaml(value, indent+1))
            else:
                lines.append(f"{prefix}{key}: {value}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(dict_to_yaml(item, indent+1))
            else:
                lines.append(f"{prefix}- {item}")
    else:
        lines.append(f"{prefix}{data}")
    return "\n".join(lines)

def dict_to_toml(data, parent_key=''):
    """
    Naively convert a dictionary to a TOML formatted string.
    Handles simple dictionaries and lists.
    """
    lines = []
    if isinstance(data, dict):
        for key, value in data.items():
            qualified_key = f"{parent_key}.{key}" if parent_key else key
            if isinstance(value, dict):
                lines.append(f"[{qualified_key}]")
                lines.append(dict_to_toml(value, qualified_key))
            elif isinstance(value, list):
                if all(isinstance(x, dict) for x in value):
                    for item in value:
                        lines.append(f"[[{qualified_key}]]")
                        lines.append(dict_to_toml(item, qualified_key))
                else:
                    lines.append(f'{key} = {json.dumps(value)}')
            else:
                if isinstance(value, str):
                    lines.append(f'{key} = "{value}"')
                else:
                    lines.append(f'{key} = {value}')
    elif isinstance(data, list):
        for item in data:
            lines.append(dict_to_toml(item, parent_key))
    return "\n".join(lines)

def convert_data(data, fmt):
    """
    Convert data (a dict) into the requested format.
    """
    fmt = fmt.lower()
    if fmt == "json":
        return JSONResponse(content=data)
    elif fmt == "xml":
        xml_string = dict_to_xml(data)
        return Response(content=xml_string, media_type="application/xml")
    elif fmt == "yaml":
        yaml_string = dict_to_yaml(data)
        return Response(content=yaml_string, media_type="text/yaml")
    elif fmt == "csv":
        csv_string = dict_to_csv(data)
        return Response(content=csv_string, media_type="text/csv")
    elif fmt == "toml":
        toml_string = dict_to_toml(data)
        return Response(content=toml_string, media_type="text/toml")
    else:
        return JSONResponse(content=data)

def render_queue_html(guild_id, request):
    if guild_id not in server_queues.keys():
        return f"<h1>No queue found for Guild ID: {guild_id}</h1>"
    html_content = f"""
    <html>
      <head>
        <title>Bot Queue - {guild_id}</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 20px; }}
          h1, h2, h3 {{ color: #333; text-align: center; }}
          table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
          th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
          th {{ background-color: #f2f2f2; }}
          img {{ max-width: 150px; display: block; margin: 10px auto; border-radius: 10px; }}
        </style>
      </head>
      <body>
        <h1>Music Queue for Guild ID: {guild_id}</h1>
        <a href="/login">Login with Discord</a>
    """
    queue = server_queues[guild_id]
    
    if guild_id in now_playing:
        song = now_playing[guild_id]
        metadata = metadata_manager.load_metadata(song[0])
        if not metadata:
            metadata = metadata_manager.get_or_fetch_metadata(song[0], song[1])
            metadata_manager.save_metadata(song[0], metadata)
        artist = metadata.get("artist", "Unknown")
        title = metadata.get("title", "Unknown")
        duration = metadata.get("duration", "Unknown")
        html_content += f"""
        <h2>Last Played: {html.escape(artist)} - {html.escape(title)}</h2>
        <p><b>Length:</b> {html.escape(str(duration))}</p>
        <p><b>ID:</b> {html.escape(song[0])}</p>
        """
        if song[2]:
            img_src = song[2][4:] if song[2].startswith("/app") else song[2]
            html_content += f'<img src="{img_src}" alt="Album Art">'
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
    can_download = user_in_guild(request, guild_id)
    for index, item in enumerate(queue._queue, start=1):
        track_id = html.escape(str(item[0]))
        title = html.escape(str(item[1]))
        download_link = f'<a href="/download/{guild_id}/{track_id}">[Download]</a>' if can_download else ''
        html_content += f"""
        <tr>
          <td>{index}</td>
          <td><a href="https://youtube.com/watch?v={track_id}">{track_id}</a> {download_link}</td>
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
              <td><a href="https://youtube.com/watch?v={track_id}">{track_id}</a></td>
              <td>{title}</td>
            </tr>
            """
        html_content += "</table>"
    html_content += "</body></html>"
    return html_content

def render_queues_html():
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
        <a href="/login">Login with Discord</a>
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
                metadata = metadata_manager.get_or_fetch_metadata(song[0], song[1])
                metadata_manager.save_metadata(song[0], metadata)
            artist = metadata.get("artist", "Unknown")
            title = metadata.get("title", "Unknown")
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
                  <td><a href="https://youtube.com/watch?v={track_id}">{track_id}</a></td>
                  <td>{title}</td>
                </tr>
                """
            html_content += "</table>"
        html_content += "</div>"
    html_content += """
        <script>
          document.getElementsByClassName("tablinks")[0]?.click();
        </script>
      </body>
    </html>
    """
    return html_content

def is_owner(user_id: str) -> bool:
    return str(user_id) == str(os.getenv("BOT_OWNER_ID"))

def user_in_guild(request: Request, guild_id: str) -> bool:
    user = request.session.get('user')
    if not user:
        return False
    if is_owner(user['id']):
        return True
    user_guilds = request.session.get('guilds', [])
    return any(g['id'] == guild_id for g in user_guilds)

@app.get('/login')
async def login(request: Request):
    if not oauth_available:
        return HTMLResponse(content="<h1>Discord OAuth not configured</h1><p>Set DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET environment variables.</p>")
    redirect_uri = request.url_for('auth')
    return await oauth.discord.authorize_redirect(request, redirect_uri)

@app.get('/auth')
async def auth(request: Request):
    if not oauth_available:
        return HTMLResponse(content="<h1>Discord OAuth not configured</h1>")
    token = await oauth.discord.authorize_access_token(request)
    user = await oauth.discord.get('users/@me', token=token)
    guilds = await oauth.discord.get('users/@me/guilds', token=token)
    request.session['user'] = user.json()
    request.session['guilds'] = guilds.json()
    return RedirectResponse(url='/queues')

@app.get('/logout')
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url='/')

@app.get("/", response_class=HTMLResponse)
async def home():
    """Home page with navigation links"""
    html_content = """
    <html>
      <head>
        <title>DtownBeats Music Bot</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
          .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
          h1 { color: #333; text-align: center; }
          .nav { text-align: center; margin: 20px 0; }
          .nav a { margin: 0 10px; padding: 10px 20px; background: #7289da; color: white; text-decoration: none; border-radius: 5px; }
          .nav a:hover { background: #5b6eae; }
          .status { background: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0; }
        </style>
      </head>
      <body>
        <div class="container">
          <h1>?? DtownBeats Music Bot</h1>
          <div class="nav">
            <a href="/queues">View Queues</a>
            <a href="/library">Music Library</a>
            <a href="/health">Health Check</a>
            <a href="/login">Login with Discord</a>
          </div>
          <div class="status">
            <h3>Bot Status</h3>
            <p><strong>Guilds:</strong> """ + str(len(server_queues)) + """</p>
            <p><strong>Active Queues:</strong> """ + str(len([q for q in server_queues.values() if not q.empty()])) + """</p>
            <p><strong>Now Playing:</strong> """ + str(len(now_playing)) + """</p>
            <p><strong>OAuth Configured:</strong> """ + ("Yes" if oauth_available else "No") + """</p>
          </div>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/queue", response_class=HTMLResponse)
async def get_queue(request: Request, guild_id: str = Query(..., description="Guild ID for which to fetch the queue"),
                    format: str = Query("html", description="Response format: html, json, xml, yaml, csv, or toml")):
    user = request.session.get('user')
    if not user:
        return RedirectResponse(url='/login')
    if not user_in_guild(request, guild_id):
        return HTMLResponse(content="You are not authorized to view this queue.", status_code=403)
    
    if guild_id not in server_queues.keys():
        error_msg = {"error": f"No queue found for Guild ID: {guild_id}"}
        if format.lower() == "html":
            html_content = render_queue_html(guild_id, request)
            return HTMLResponse(content=html_content, status_code=404)
        else:
            return JSONResponse(content=error_msg, status_code=404)
    
    data = {
        "last_played": now_playing.get(guild_id, None),
        "queue": [{"track_id": item[0], "title": item[1]} for item in server_queues[guild_id]._queue],
        "history": track_history.get(guild_id, [])
    }
    
    if format.lower() == "html":
        html_content = render_queue_html(guild_id, request)
        return HTMLResponse(content=html_content)
    else:
        return convert_data(data, format)

@app.get("/queues", response_class=HTMLResponse)
async def get_queues(request: Request, format: str = Query("html")):
    user = request.session.get('user')
    if not user:
        return RedirectResponse(url='/login')
    guilds = request.session.get('guilds', [])
    allowed_guilds = [g['id'] for g in guilds]
    if is_owner(user['id']):
        allowed_guilds = list(server_queues.keys())
    response_data = {}
    for guild_id in allowed_guilds:
        if guild_id in server_queues:
            queue = server_queues[guild_id]
            last_played = now_playing.get(guild_id, None)
            if last_played:
                metadata = metadata_manager.load_metadata(last_played[0])
                if not metadata:
                    metadata = metadata_manager.get_or_fetch_metadata(last_played[0], last_played[1])
                    metadata_manager.save_metadata(last_played[0], metadata)
                track_info = {
                    "artist": metadata.get("artist", "Unknown"),
                    "title": metadata.get("title", "Unknown"),
                    "duration": metadata.get("duration", "Unknown"),
                    "track_id": last_played[0]
                }
            else:
                track_info = {}
            response_data[guild_id] = {
                "last_played": track_info,
                "queue": [{"track_id": item[0], "title": item[1]} for item in queue._queue],
                "history": track_history.get(guild_id, [])
            }
    if format.lower() == "html":
        html_content = render_queues_html()
        return HTMLResponse(content=html_content)
    else:
        return convert_data(response_data, format)

@app.get("/download/{guild_id}/{track_id}")
async def download_track(request: Request, guild_id: str, track_id: str):
    user = request.session.get('user')
    if not user or not user_in_guild(request, guild_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    # Sanitize track_id
    if not track_id.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid track id")
    file_path = f"/app/music/{track_id}.mp3"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=f"{track_id}.mp3")

@app.get("/download/owner/{track_id}")
async def download_owner_track(request: Request, track_id: str):
    user = request.session.get('user')
    if not user or not is_owner(user['id']):
        raise HTTPException(status_code=403, detail="Not authorized")
    # Sanitize track_id
    if not track_id.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid track id")
    file_path = f"/app/music/{track_id}.mp3"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=f"{track_id}.mp3")

@app.get("/library", response_class=HTMLResponse)
async def music_library(request: Request, q: str = "", page: int = 1, per_page: int = 20):
    user = request.session.get('user')
    if not user:
        return RedirectResponse(url='/login')
    allowed_guilds = [g['id'] for g in request.session.get('guilds', [])]
    if is_owner(user['id']):
        allowed_guilds = list(server_queues.keys())
    # Build a mapping of track_id -> allowed_guilds that have it in their queue/history
    track_guild_map = {}
    for guild_id in allowed_guilds:
        if guild_id in server_queues:
            for item in server_queues[guild_id]._queue:
                tid = str(item[0])
                track_guild_map.setdefault(tid, set()).add(guild_id)
        if guild_id in track_history:
            for item in track_history[guild_id]:
                tid = str(item[0])
                track_guild_map.setdefault(tid, set()).add(guild_id)
    music_files = []
    q_lower = q.lower()
    for fname in os.listdir("/app/music"):
        if fname.endswith(".mp3"):
            track_id = fname[:-4]
            metadata = metadata_manager.load_metadata(track_id) or {}
            title = metadata.get("title", track_id)
            artist = metadata.get("artist", "Unknown")
            # Enhanced search: match query in track_id, title, or artist
            if (not q or q_lower in track_id.lower() or q_lower in title.lower() or q_lower in artist.lower()):
                if is_owner(user['id']) or track_id in track_guild_map:
                    music_files.append((track_id, title, artist, sorted(track_guild_map.get(track_id, []))))
    # Pagination
    total = len(music_files)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    paged_files = music_files[start:end]
    # Render HTML
    html_content = f"<form method='get'>"
    html_content += f"<input name='q' value='{html.escape(q)}' placeholder='Search by ID, title, or artist...'>"
    html_content += f"<input type='hidden' name='per_page' value='{per_page}'>"
    html_content += f"<input type='submit' value='Search'></form>"
    html_content += '<a href="/queues">Queues</a> | <a href="/library">Library</a> | <a href="/logout">Logout</a>'
    html_content += f"<p>Showing {start+1}-{min(end,total)} of {total} results. Page {page} of {total_pages}.</p>"
    html_content += "<table><tr><th>Title</th><th>Artist</th><th>Track ID</th><th>Download</th></tr>"
    for track_id, title, artist, guilds in paged_files:
        download_link = ""
        if is_owner(user['id']) and not guilds:
            download_link = f'<a href="/download/owner/{track_id}">[Download]</a>'
        elif guilds:
            download_link = f'<a href="/download/{guilds[0]}/{track_id}">[Download]</a>'
        html_content += f"<tr><td>{html.escape(title)}</td><td>{html.escape(artist)}</td><td>{html.escape(track_id)}</td><td>{download_link}</td></tr>"
    html_content += "</table>"
    # Pagination controls
    html_content += "<div style='margin-top:10px;'>"
    if page > 1:
        html_content += f'<a href="?q={html.escape(q)}&per_page={per_page}&page={page-1}">Previous</a> '
    if page < total_pages:
        html_content += f'<a href="?q={html.escape(q)}&per_page={per_page}&page={page+1}">Next</a>'
    html_content += "</div>"
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and monitoring"""
    try:
        # Basic health checks
        health_status = {
            "status": "healthy",
            "timestamp": str(time.time()),
            "guilds": len(server_queues),
            "active_queues": len([q for q in server_queues.values() if not q.empty()]),
            "now_playing": len(now_playing),
            "oauth_configured": oauth_available
        }
        return JSONResponse(content=health_status, status_code=200)
    except Exception as e:
        return JSONResponse(
            content={
                "status": "unhealthy", 
                "error": str(e),
                "timestamp": str(time.time())
            }, 
            status_code=503
        )

@app.get("/metrics")
async def metrics_endpoint(request: Request):
    """Detailed metrics endpoint (owner only)"""
    user = request.session.get('user')
    if not user or not is_owner(user['id']):
        raise HTTPException(status_code=403, detail="Owner access required")
    
    import psutil
    import platform
    
    # System metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    network = psutil.net_io_counters()
    
    # Bot metrics
    total_tracks_queued = sum(q.qsize() for q in server_queues.values())
    total_history = sum(len(hist) for hist in track_history.values())
    
    metrics = {
        "system": {
            "platform": platform.system(),
            "cpu_percent": cpu_percent,
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "memory_percent": memory.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_percent": disk.percent,
            "network_sent_mb": round(network.bytes_sent / (1024**2), 1),
            "network_recv_mb": round(network.bytes_recv / (1024**2), 1)
        },
        "bot": {
            "guilds": len(server_queues),
            "active_queues": len([q for q in server_queues.values() if not q.empty()]),
            "total_tracks_queued": total_tracks_queued,
            "now_playing_count": len(now_playing),
            "total_history_tracks": total_history,
            "oauth_configured": oauth_available
        }
    }
    
    return JSONResponse(content=metrics)

def run_web_app():
    uvicorn.run(app, host="0.0.0.0", port=80)

def start_web_server_in_background(queues, now_playing_songs, track_historys):
    global server_queues, now_playing, track_history
    server_queues = queues
    now_playing = now_playing_songs
    track_history = track_historys
    thread = threading.Thread(target=run_web_app, daemon=True)
    thread.start()