from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import logging
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IndF Workbench", version="4.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Пытаемся импортировать подприложения с обработкой ошибок
try:
    from rot_cut.main import app as rot_cut_app
    app.mount("/rot_cut", rot_cut_app)
    logger.info("✅ rot_cut mounted")
except Exception as e:
    logger.error(f"❌ Failed to mount rot_cut: {e}")
    traceback.print_exc()

try:
    from pol_cut.main import app as pol_cut_app
    app.mount("/pol_cut", pol_cut_app)
    logger.info("✅ pol_cut mounted")
except Exception as e:
    logger.error(f"❌ Failed to mount pol_cut: {e}")

try:
    from sek.main import app as sek_app
    app.mount("/sek", sek_app)
    logger.info("✅ sek mounted")
except Exception as e:
    logger.error(f"❌ Failed to mount sek: {e}")

try:
    from ras.main import app as ras_app
    app.mount("/ras", ras_app)
    logger.info("✅ ras mounted")
except Exception as e:
    logger.error(f"❌ Failed to mount ras: {e}")

# Отдельные HTML-страницы (работают всегда)
@app.get("/")
async def root():
    return FileResponse("start.html")

@app.get("/epure")
async def epure():
    return FileResponse("alp.html")

@app.get("/axon")
async def axon():
    return FileResponse("aks.html")

# Заглушка для /cut (если нужно)
@app.get("/cut")
async def cut_placeholder():
    return FileResponse("start.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
