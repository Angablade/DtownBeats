from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from starlette.staticfiles import StaticFiles
import uvicorn
import threading
import html
from bot3 import server_queues
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/queues", response_class=HTMLResponse)
async def list_queues():
    html_content = """
    <html>
      <head>
        <title>Bot Queues</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 20px; }
          h1 { color: #333; }
          table { border-collapse: collapse; width: 100%; margin-bottom: 30px; }
          th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
          th { background-color: #f2f2f2; }
          tr:hover { background-color: #f9f9f9; }
        </style>
      </head>
      <body>
        <h1>Queues for All Guilds</h1>
    """
    for guild_id, queue in server_queues.items():
        html_content += f"<h2>Guild ID: {html.escape(str(guild_id))}</h2>"
        html_content += """
        <table>
          <tr>
            <th>Index</th>
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
              <td>{track_id}</td>
              <td>{title}</td>
            </tr>
            """
        html_content += "</table>"
    html_content += "</body></html>"
    return HTMLResponse(content=html_content)

def run_web_app():
    uvicorn.run(app, host="0.0.0.0", port=80)

def start_web_server_in_background():
    thread = threading.Thread(target=run_web_app, daemon=True)
    thread.start()
