from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Импортируем подприложения (каждое имеет свой FastAPI app)
from rot_cut.main import app as rot_cut_app
from pol_cut.main import app as pol_cut_app
from sek.main import app as sek_app
from ras.main import app as ras_app

BASE_DIR = Path(__file__).parent

app = FastAPI(title="IndF Workbench", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем модули по префиксам
app.mount("/rot_cut", rot_cut_app)   # вырезы на телах вращения
app.mount("/pol_cut", pol_cut_app)   # вырезы на многогранниках
app.mount("/sek", sek_app)           # пересечения
app.mount("/ras", ras_app)           # развёртки

# Отдельные инструменты (HTML‑страницы)
@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("start.html")

@app.get("/epure", response_class=HTMLResponse)
async def epure():
    return FileResponse("alp.html")

@app.get("/axon", response_class=HTMLResponse)
async def axon():
    return FileResponse("aks.html")

# Общая статика (если нужна для корневых страниц)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Health‑check для мониторинга
@app.get("/health")
async def health():
    return {"status": "ok", "version": "4.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
