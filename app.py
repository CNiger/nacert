from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Импорты подприложений (если они падают, обернул в try)
try:
    from rot_cut.main import app as rot_cut_app
    rot_cut_ok = True
except Exception as e:
    print(f"rot_cut import error: {e}")
    rot_cut_ok = False

try:
    from pol_cut.main import app as pol_cut_app
    pol_cut_ok = True
except Exception as e:
    print(f"pol_cut import error: {e}")
    pol_cut_ok = False

try:
    from sek.main import app as sek_app
    sek_ok = True
except Exception as e:
    print(f"sek import error: {e}")
    sek_ok = False

try:
    from ras.main import app as ras_app
    ras_ok = True
except Exception as e:
    print(f"ras import error: {e}")
    ras_ok = False

app = FastAPI(title="CAD Tools Suite")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем только если импорт удался
if rot_cut_ok:
    app.mount("/rot_cut", rot_cut_app)
if pol_cut_ok:
    app.mount("/pol_cut", pol_cut_app)
if sek_ok:
    app.mount("/sek", sek_app)
if ras_ok:
    app.mount("/ras", ras_app)

# Главная страница
@app.get("/")
def start():
    return FileResponse("start.html")

# Эпюр и аксонометрия – теперь точно будут работать
@app.get("/epure")
def epure():
    return FileResponse("alp.html")

@app.get("/ask")
def ask():
    return FileResponse("ask.html")

# Если вдруг файлы не найдены – отдадим понятную ошибку
@app.get("/{path:path}")
def catch_all(path: str):
    return {"error": f"Path '{path}' not found", "available": ["/", "/epure", "/ask", "/rot_cut", "/pol_cut", "/sek", "/ras"]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
