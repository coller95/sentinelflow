
from fastapi import FastAPI
from fastapi.responses import FileResponse
import os

app = FastAPI()

@app.get("/", response_class=FileResponse)
def ServeIndex():
    # Serve the HTML file from the public directory
    index_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public", "index.html")
    return FileResponse(index_path, media_type="text/html")
