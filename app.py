from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uuid
import traceback
from pathlib import Path
from typing import List, Tuple

import cadquery as cq

import sys
print("=== STARTING APP.PY ===", file=sys.stderr)
print("Importing rot_cut...", file=sys.stderr)
from rot_cut.main import app as rot_cut_app
print("rot_cut imported OK", file=sys.stderr)
print("Importing pol_cut...", file=sys.stderr)
from pol_cut.main import app as pol_cut_app
print("pol_cut imported OK", file=sys.stderr)

app = FastAPI(title="IndF Workbench", version="5.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Статические HTML ----------
@app.get("/")
async def root():
    return FileResponse("start.html")

@app.get("/epure")
async def epure():
    return FileResponse("alp.html")

@app.get("/axon")
async def axon():
    return FileResponse("aks.html")

# ---------- Модуль вырезов на телах вращения (прямо здесь) ----------
PRIMITIVES_DIR = Path("rot_cut/primitives")
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

SUPPORTED_SHAPES = {"sphere", "cylinder", "cone"}
PRIMITIVE_CONFIG = {
    "sphere": {"radius": 30.0},
    "cylinder": {"radius": 30.0, "height": 70.0},
    "cone": {"radius": 30.0, "height": 70.0}
}
CUTTER_DEPTH = 200.0

def load_primitive(shape: str) -> cq.Workplane:
    path = PRIMITIVES_DIR / f"{shape}.step"
    if not path.exists():
        raise RuntimeError(f"Primitive not found: {path}")
    shape_obj = cq.importers.importStep(str(path))
    if hasattr(shape_obj, 'val'):
        return shape_obj
    return cq.Workplane().add(shape_obj)

def normalize_points(points: List[List[float]], shape: str) -> List[Tuple[float, float]]:
    cfg = PRIMITIVE_CONFIG[shape]
    result = []
    for ux, uz in points:
        x = (ux - 0.5) * 2 * cfg["radius"]
        if shape == "sphere":
            z = (uz - 0.5) * 2 * cfg["radius"]
        else:
            z = (1 - uz) * cfg["height"]
        result.append((x, z))
    if len(result) >= 3 and result[0] != result[-1]:
        result.append(result[0])
    return result

def make_cutter(contour: List[Tuple[float, float]]) -> cq.Workplane:
    return (cq.Workplane("XZ")
            .polyline(contour)
            .close()
            .extrude(CUTTER_DEPTH, both=True))

@app.post("/api/create-model")
def create_model(req: dict):
    try:
        shape = req.get("shape")
        points = req.get("points")
        
        base = load_primitive(shape)
        volume = base.val().Volume()
        contour = normalize_points(points, shape)
        cutter = make_cutter(contour)
        result = base.cut(cutter)
        result_volume = result.val().Volume()
        
        base_name = f"{shape}_cut_{uuid.uuid4().hex[:8]}"
        step_path = TEMP_DIR / f"{base_name}.step"
        cq.exporters.export(result, str(step_path))
        
        return {
            "success": True,
            "base_filename": base_name,
            "volumes": {"original": round(volume, 1), "result": round(result_volume, 1)},
            "downloads": {
                "step": {"filename": f"{base_name}.step", "url": f"/api/download/{base_name}.step"}
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/download/{filename}")
def download_file(filename: str):
    path = TEMP_DIR / filename
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, filename=filename)

# ---------- Заглушки для остальных модулей ----------
@app.get("/rot_cut")
async def rot_cut_page():
    return HTMLResponse("""
    <h2>Вырезы на телах вращения</h2>
    <p>API доступен по <a href='/api/create-model'>/api/create-model</a></p>
    <p>Используйте POST запрос с JSON: {"shape": "cylinder", "points": [[0.2,0.3],[0.5,0.6],[0.8,0.2]]}</p>
    <a href='/'>На главную</a>
    """)

@app.get("/pol_cut")
async def pol_cut():
    return HTMLResponse("<h2>Вырезы на многогранниках</h2><p>В разработке</p><a href='/'>На главную</a>")

@app.get("/sek")
async def sek():
    return HTMLResponse("<h2>Пересечения</h2><p>В разработке</p><a href='/'>На главную</a>")

@app.get("/ras")
async def ras():
    return HTMLResponse("<h2>Развёртки</h2><p>В разработке</p><a href='/'>На главную</a>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
