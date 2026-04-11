from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

# Подключаем подприложения
from rot_cut.main import app as rot_cut_app
from pol_cut.main import app as pol_cut_app
from sek.main import app as sek_app
from ras.main import app as ras_app

app = FastAPI(title="IndF Workbench", version="4.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем модули по префиксам
app.mount("/rot_cut", rot_cut_app)
app.mount("/pol_cut", pol_cut_app)
app.mount("/sek", sek_app)
app.mount("/ras", ras_app)

# Отдельные статические HTML-страницы
@app.get("/")
async def root():
    return FileResponse("start.html")

@app.get("/epure")
async def epure():
    return FileResponse("alp.html")

@app.get("/axon")
async def axon():
    return FileResponse("aks.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
