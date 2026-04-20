from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse, HTMLResponse
from pathlib import Path

app = FastAPI()

@app.post("/compare")
async def compare_steps():
    print("🔵 /compare вызван")
    return {"success": True, "message": "Минимальный тест работает"}

@app.get("/")
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>STEP Checker</h1><p>Минимальная версия работает</p>")
