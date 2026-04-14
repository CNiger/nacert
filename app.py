from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Импорты подприложений
try:
    from rot_cut.main import app as rot_cut_app
    print("✓ rot_cut imported")
except Exception as e:
    print(f"✗ rot_cut import error: {e}")
    rot_cut_app = None

try:
    from pol_cut.main import app as pol_cut_app
    print("✓ pol_cut imported")
except Exception as e:
    print(f"✗ pol_cut import error: {e}")
    pol_cut_app = None

try:
    from sek.main import app as sek_app
    print("✓ sek imported")
except Exception as e:
    print(f"✗ sek import error: {e}")
    sek_app = None

try:
    from ras.main import app as ras_app
    print("✓ ras imported")
except Exception as e:
    print(f"✗ ras import error: {e}")
    ras_app = None

app = FastAPI(title="CAD Tools Suite")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем сервисы
if rot_cut_app:
    app.mount("/rot_cut", rot_cut_app)
if pol_cut_app:
    app.mount("/pol_cut", pol_cut_app)
if sek_app:
    app.mount("/sek", sek_app)
if ras_app:
    app.mount("/ras", ras_app)

# Стартовая страница
@app.get("/")
def start():
    return FileResponse("start.html")

# Эпюр и аксонометрия
@app.get("/epure")
def epure():
    return FileResponse("alp.html")

@app.get("/ask")
def ask():
    return FileResponse("aks.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
