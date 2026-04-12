from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import traceback
from pathlib import Path

app = FastAPI(title="CAD Tools Suite")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# Функция для монтирования с диагностикой
# ------------------------------------------------------------------
def mount_with_diagnostics(mount_path: str, module_name: str, app_attr: str = "app"):
    """
    Пытается импортировать module_name и смонтировать app_attr по mount_path.
    Если не получается, монтирует заглушку, показывающую ошибку.
    """
    try:
        module = __import__(module_name, fromlist=[app_attr])
        sub_app = getattr(module, app_attr)
        app.mount(mount_path, sub_app)
        print(f"✓ {mount_path} mounted from {module_name}")
    except Exception as e:
        error_text = traceback.format_exc()
        print(f"✗ {mount_path} FAILED: {error_text}")
        
        # Создаём заглушку, которая вернёт HTML с ошибкой
        async def error_stub(request):
            return HTMLResponse(
                content=f"<h1>Ошибка монтирования {mount_path}</h1><pre>{error_text}</pre>",
                status_code=500
            )
        app.add_api_route(mount_path, error_stub, methods=["GET"])
        # Также на случай, если нужен слэш в конце
        app.add_api_route(mount_path + "/", error_stub, methods=["GET"])

# ------------------------------------------------------------------
# Монтируем все подприложения с диагностикой
# ------------------------------------------------------------------
mount_with_diagnostics("/rot_cut", "rot_cut.main")
mount_with_diagnostics("/pol_cut", "pol_cut.main")
mount_with_diagnostics("/sek", "sek.main")
mount_with_diagnostics("/ras", "ras.main")

# ------------------------------------------------------------------
# Стартовая страница (встроена)
# ------------------------------------------------------------------
HTML_INDEX = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>CAD Tools Suite</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0a0c10 0%, #1a1e2a 100%);
            font-family: monospace;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container { max-width: 1200px; width: 100%; }
        h1 {
            text-align: center;
            color: #ff5500;
            font-size: 2rem;
            margin-bottom: 40px;
        }
        .tools-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 24px;
        }
        .tool-card {
            background: rgba(15, 17, 23, 0.9);
            border: 1px solid #3a3e48;
            border-radius: 16px;
            padding: 24px;
            text-decoration: none;
            color: inherit;
            transition: all 0.3s;
        }
        .tool-card:hover {
            border-color: #ff5500;
            transform: translateY(-5px);
        }
        .tool-icon { font-size: 2.5rem; margin-bottom: 16px; }
        .tool-title { font-size: 1.3rem; font-weight: bold; margin-bottom: 8px; color: #ff5500; }
        .tool-desc { color: #9ca3b5; font-size: 0.85rem; }
        footer {
            text-align: center;
            margin-top: 48px;
            color: #6b7280;
            font-size: 0.7rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ CAD TOOLS SUITE</h1>
        <div class="tools-grid">
            <a href="/rot_cut" class="tool-card"><div class="tool-icon">🔧</div><div class="tool-title">Тела вращения</div><div class="tool-desc">Профилирование деталей с вырезом.</div></a>
            <a href="/pol_cut" class="tool-card"><div class="tool-icon">🔺</div><div class="tool-title">Многогранники</div><div class="tool-desc">Пирамиды и призмы. HLR.</div></a>
            <a href="/sek" class="tool-card"><div class="tool-icon">✂️</div><div class="tool-title">Пересечения</div><div class="tool-desc">Анализ пересечений тел.</div></a>
            <a href="/ras" class="tool-card"><div class="tool-icon">📐</div><div class="tool-title">Развёртки</div><div class="tool-desc">Построение развёрток.</div></a>
            <a href="/epure" class="tool-card"><div class="tool-icon">📏</div><div class="tool-title">Эпюр Монжа</div><div class="tool-desc">Трёхпроекционное черчение.</div></a>
            <a href="/ask" class="tool-card"><div class="tool-icon">🎨</div><div class="tool-title">Аксонометрия</div><div class="tool-desc">Изометрические и диметрические проекции.</div></a>
        </div>
        <footer>CAD Tools Suite | injgaf.ru</footer>
    </div>
</body>
</html>
'''

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML_INDEX

# ------------------------------------------------------------------
# Эпюр и аксонометрия с диагностикой
# ------------------------------------------------------------------
@app.get("/epure")
async def epure():
    try:
        return FileResponse("alp.html")
    except Exception as e:
        return HTMLResponse(f"<h1>Ошибка загрузки alp.html</h1><pre>{traceback.format_exc()}</pre>", status_code=500)

@app.get("/ask")
async def ask():
    try:
        return FileResponse("aks.html")
    except Exception as e:
        return HTMLResponse(f"<h1>Ошибка загрузки aks.html</h1><pre>{traceback.format_exc()}</pre>", status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
