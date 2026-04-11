from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI()

@app.get("/")
async def root():
    return FileResponse("start.html")

@app.get("/epure")
async def epure():
    return FileResponse("alp.html")

@app.get("/axon")
async def axon():
    return FileResponse("aks.html")

# Заглушки для модулей
@app.get("/rot_cut")
async def rot_cut():
    return JSONResponse({"message": "Модуль временно отключён. Ошибка импорта зависимостей."})

@app.get("/pol_cut")
async def pol_cut():
    return JSONResponse({"message": "Модуль временно отключён."})

@app.get("/sek")
async def sek():
    return JSONResponse({"message": "Модуль временно отключён."})

@app.get("/ras")
async def ras():
    return JSONResponse({"message": "Модуль временно отключён."})

# Также заглушки для любых других путей, которые могут вызываться из интерфейса
@app.get("/rot_cut/{path:path}")
async def rot_cut_catchall():
    return JSONResponse({"error": "Модуль не активен"})
