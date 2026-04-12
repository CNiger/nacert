from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
import uvicorn
from pathlib import Path

# ------------------------------------------------------------------
# Импорт подприложений (каждое в try/except, чтобы не упало всё)
# ------------------------------------------------------------------
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

# ------------------------------------------------------------------
# Основное приложение
# ------------------------------------------------------------------
app = FastAPI(title="CAD Tools Suite")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем только те, что загрузились
if rot_cut_app:
    app.mount("/rot_cut", rot_cut_app)
if pol_cut_app:
    app.mount("/pol_cut", pol_cut_app)
if sek_app:
    app.mount("/sek", sek_app)
if ras_app:
    app.mount("/ras", ras_app)

# ------------------------------------------------------------------
# Встроенная стартовая страница (как в старом примере, но ссылки обновлены)
# ------------------------------------------------------------------
HTML_INDEX = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CAD Tools Suite</title>
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
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
            <a href="/rot_cut" class="tool-card">
                <div class="tool-icon">🔧</div>
                <div class="tool-title">Тела вращения</div>
                <div class="tool-desc">Профилирование деталей с вырезом. STEP, STL, SVG, DXF.</div>
            </a>
            <a href="/pol_cut" class="tool-card">
                <div class="tool-icon">🔺</div>
                <div class="tool-title">Многогранники с вырезом</div>
                <div class="tool-desc">Пирамиды и призмы. HLR, трёхпроекционный чертёж.</div>
            </a>
            <a href="/sek" class="tool-card">
                <div class="tool-icon">✂️</div>
                <div class="tool-title">Пересечения</div>
                <div class="tool-desc">Анализ пересечений тел. STEP, STL.</div>
            </a>
            <a href="/ras" class="tool-card">
                <div class="tool-icon">📐</div>
                <div class="tool-title">Развёртки</div>
                <div class="tool-desc">Построение развёрток. DXF, SVG.</div>
            </a>
            <a href="/epure" class="tool-card">
                <div class="tool-icon">📏</div>
                <div class="tool-title">Эпюр Монжа</div>
                <div class="tool-desc">Трёхпроекционное черчение. Линии, прямоугольники, эллипсы.</div>
            </a>
            <a href="/ask" class="tool-card">
                <div class="tool-icon">🎨</div>
                <div class="tool-title">Аксонометрия</div>
                <div class="tool-desc">Изометрические и диметрические проекции.</div>
            </a>
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
# Эпюр и аксонометрия с защитой от ошибок
# ------------------------------------------------------------------
@app.get("/epure", response_class=HTMLResponse)
async def epure_mode():
    try:
        return FileResponse("alp.html")
    except Exception as e:
        # Если файл не читается, вернём простой HTML
        return HTMLResponse(f"<h1>Ошибка загрузки alp.html</h1><p>{e}</p><p>Проверьте наличие файла в корне.</p>", status_code=500)

@app.get("/ask", response_class=HTMLResponse)
async def axonometry_mode():
    try:
        return FileResponse("aks.html")
    except Exception as e:
        return HTMLResponse(f"<h1>Ошибка загрузки aks.html</h1><p>{e}</p><p>Проверьте наличие файла в корне.</p>", status_code=500)

@app.get("/favicon.ico", include_in_schema=False)
async def get_favicon():
    favicon = Path("favicon.ico")
    if favicon.exists():
        return FileResponse("favicon.ico")
    return HTMLResponse("", status_code=204)

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
