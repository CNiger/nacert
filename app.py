from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Импортируем все приложения
from rot_cut.main import app as rot_app
from pol_cut.main import app as pol_app
from sek.main import app as sek_app
from ras.main import app as ras_app

# Твои старые импорты (если они ещё нужны)
from main import app as cut_app   # если этот cut_app уже один из перечисленных – убери дубликат

app = FastAPI(title="CAD Tools Suite")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем все сервисы
app.mount("/cut", rot_app)    # вырезы тел вращения
app.mount("/pol", pol_app)    # многогранники
app.mount("/sek", sek_app)    # пересечения
app.mount("/ras", ras_app)    # развёртки

# Если у тебя остался старый cut_app, который не вошёл в список – замонтируй его куда-то ещё
# Например, если он нужен отдельно:
# app.mount("/old_cut", cut_app)

# Стартовая страница и другие статические HTML
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
