from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import sys

print("=== STARTING APP.PY ===", file=sys.stderr)

app = FastAPI(title="IndF Workbench", version="4.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем подприложения
try:
    print("Importing rot_cut...", file=sys.stderr)
    from rot_cut.main import app as rot_cut_app
    app.mount("/rot_cut", rot_cut_app)
    print("rot_cut mounted OK", file=sys.stderr)
except Exception as e:
    print(f"rot_cut FAILED: {e}", file=sys.stderr)

try:
    print("Importing pol_cut...", file=sys.stderr)
    from pol_cut.main import app as pol_cut_app
    app.mount("/pol_cut", pol_cut_app)
    print("pol_cut mounted OK", file=sys.stderr)
except Exception as e:
    print(f"pol_cut FAILED: {e}", file=sys.stderr)

# Отдельные HTML-страницы
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
