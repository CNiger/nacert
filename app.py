from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import time
import asyncio
from pathlib import Path

# Импорты подприложений
try:
    from rot_cut.main import app as rot_cut_app
    print("✓ rot_cut imported")
except Exception as e:
    print(f"✗ rot_cut: {e}")
    rot_cut_app = None

try:
    from pol_cut.main import app as pol_cut_app
    print("✓ pol_cut imported")
except Exception as e:
    print(f"✗ pol_cut: {e}")
    pol_cut_app = None

try:
    from sek.main import app as sek_app
    print("✓ sek imported")
except Exception as e:
    print(f"✗ sek: {e}")
    sek_app = None

try:
    from ras.main import app as ras_app
    print("✓ ras imported")
except Exception as e:
    print(f"✗ ras: {e}")
    ras_app = None

# STEP CHECKER
try:
    from check.main import router as check_router
    print("✓ step checker imported")
except Exception as e:
    print(f"✗ step checker: {e}")
    check_router = None

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
if check_router:
    app.include_router(check_router, prefix="/check", tags=["step_checker"])

# ------------------ Функции очистки временных папок ------------------

def clean_old_files(directory: Path, age_minutes: int = 10):
    """
    Удаляет все файлы в указанной директории, которые старше age_minutes минут.
    Также удаляет пустые поддиректории.
    """
    if not directory.exists():
        return
    now = time.time()
    cutoff = now - age_minutes * 60

    for root, dirs, files in os.walk(directory, topdown=False):
        root_path = Path(root)
        for file in files:
            file_path = root_path / file
            try:
                if file_path.stat().st_mtime < cutoff:
                    file_path.unlink()
                    print(f"Удалён старый файл: {file_path}")
            except Exception as e:
                print(f"Ошибка при удалении {file_path}: {e}")
        for dir_name in dirs:
            dir_path = root_path / dir_name
            try:
                if not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    print(f"Удалена пустая папка: {dir_path}")
            except Exception as e:
                print(f"Ошибка при удалении папки {dir_path}: {e}")

async def periodic_cleanup(interval_minutes: int = 5):
    """
    Фоновая задача: каждые interval_minutes минут вызывает очистку temp-папок.
    """
    while True:
        try:
            base_dir = Path(__file__).parent
            temp_dirs = [
                base_dir / "rot_cut" / "temp",
                base_dir / "pol_cut" / "temp",
                base_dir / "sek" / "temp",
                base_dir / "ras" / "temp",
                base_dir / "check" / "temp",
            ]
            for temp_dir in temp_dirs:
                clean_old_files(temp_dir, age_minutes=10)
        except Exception as e:
            print(f"Ошибка в periodic_cleanup: {e}")
        await asyncio.sleep(interval_minutes * 60)

cleanup_task = None

@app.on_event("startup")
async def startup_event():
    global cleanup_task
    cleanup_task = asyncio.create_task(periodic_cleanup(interval_minutes=5))
    print("Фоновая очистка временных папок запущена (интервал 5 минут)")

@app.on_event("shutdown")
async def shutdown_event():
    global cleanup_task
    if cleanup_task:
        cleanup_task.cancel()
        print("Фоновая очистка остановлена")

# ------------------ Статические страницы ------------------

@app.get("/lekz.html")
def lekz():
    return FileResponse("lekz.html")

@app.get("/")
def start():
    return FileResponse("start.html")

@app.get("/epure")
def epure():
    return FileResponse("alp.html")

@app.get("/ask")
def ask():
    return FileResponse("aks.html")

# ------------------ Точка входа ------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
