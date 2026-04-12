from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Импортируем все сервисы из папок
from rot_cut.main import app as rot_cut_app
from pol_cut.main import app as pol_cut_app
from sek.main import app as sek_app
from ras.main import app as ras_app

app = FastAPI(title="CAD Tools Suite")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем сервисы - путь РАВЕН имени папки
app.mount("/rot_cut", rot_cut_app)   # папка rot_cut → путь /rot_cut
app.mount("/pol_cut", pol_cut_app)   # папка pol_cut → путь /pol_cut
app.mount("/sek", sek_app)           # папка sek → путь /sek
app.mount("/ras", ras_app)           # папка ras → путь /ras

# Статические страницы
@app.get("/")
def start():
    return FileResponse("start.html")

@app.get("/epure")
def epure():
    return FileResponse("alp.html")

@app.get("/ask")
def ask():
    return FileResponse("ask.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
