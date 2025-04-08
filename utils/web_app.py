import os
import html
import base64
import logging
import threading
import json
import csv
import io
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.staticfiles import StaticFiles
import uvicorn
from xml.etree.ElementTree import Element, tostring

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

def render_queue_html(guild_id):
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

@app.get("/queue", response_class=HTMLResponse)
async def get_queue(guild_id: str = Query(..., description="Guild ID for which to fetch the queue"),
                    format: str = Query("html", description="Response format: html, json, xml, yaml, csv, or toml")):
    if guild_id not in server_queues.keys():
        error_msg = {"error": f"No queue found for Guild ID: {guild_id}"}
        if format.lower() == "html":
            return HTMLResponse(content=f"<h1>No queue found for Guild ID: {guild_id}</h1>", status_code=404)
        else:
            return JSONResponse(content=error_msg, status_code=404)
    
    data = {
        "last_played": now_playing.get(guild_id, None),
        "queue": [{"track_id": item[0], "title": item[1]} for item in server_queues[guild_id]._queue],
        "history": track_history.get(guild_id, [])
    }
    
    if format.lower() == "html":
        html_content = render_queue_html(guild_id)
        return HTMLResponse(content=html_content)
    else:
        return convert_data(data, format)

@app.get("/queues", response_class=HTMLResponse)
async def get_queues(format: str = Query("html", description="Response format: html, json, xml, yaml, csv, or toml")):
    response_data = {}
    for guild_id, queue in server_queues.items():
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

def run_web_app():
    uvicorn.run(app, host="0.0.0.0", port=80)

def start_web_server_in_background(queues, now_playing_songs, track_historys):
    global server_queues, now_playing, track_history
    server_queues = queues
    now_playing = now_playing_songs
    track_history = track_historys
    thread = threading.Thread(target=run_web_app, daemon=True)
    thread.start()