from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

# Импорты с обработкой ошибок
try:
    from rot_cut.main import app as rot_cut_app
    print("✓ rot_cut imported")
except Exception as e:
    print(f"✗ rot_cut import failed: {e}")
    rot_cut_app = None

try:
    from pol_cut.main import app as pol_cut_app
    print("✓ pol_cut imported")
except Exception as e:
    print(f"✗ pol_cut import failed: {e}")
    pol_cut_app = None

try:
    from sek.main import app as sek_app
    print("✓ sek imported")
except Exception as e:
    print(f"✗ sek import failed: {e}")
    sek_app = None

try:
    from ras.main import app as ras_app
    print("✓ ras imported")
except Exception as e:
    print(f"✗ ras import failed: {e}")
    ras_app = None

app = FastAPI(title="CAD Tools Suite")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем только успешные
if rot_cut_app:
    app.mount("/rot_cut", rot_cut_app)
if pol_cut_app:
    app.mount("/pol_cut", pol_cut_app)
if sek_app:
    app.mount("/sek", sek_app)
if ras_app:
    app.mount("/ras", ras_app)

# Статические HTML
@app.get("/")
def start():
    return FileResponse("start.html")

@app.get("/epure")
def epure():
    return FileResponse("alp.html")

@app.get("/ask")
def ask():
    return FileResponse("ask.html")

import os
@app.get("/debug-files")
def debug_files():
    return {"files": os.listdir(".")}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
