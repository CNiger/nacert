"Пересечения "

from __future__ import annotations

import uuid
import traceback
from pathlib import Path
from typing import List, Tuple

import cadquery as cq
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, validator

# -----------------------------------------------------------------------------
# Конфигурация
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
PRIMITIVES_DIR = BASE_DIR / "primitives"
TEMP_DIR = BASE_DIR / "temp"
STATIC_DIR = BASE_DIR / "static"

TEMP_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

SUPPORTED_SHAPES = {"sphere", "cylinder", "cone"}

app = FastAPI(title="Intersection of Solids", version="6.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Модели
# -----------------------------------------------------------------------------
class BodyPosition(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

class BodyRotation(BaseModel):
    axis: str = "Y"
    angle_deg: float = 0.0

class IntersectBody(BaseModel):
    type: str
    position: BodyPosition
    rotation: BodyRotation

    @validator("type")
    def validate_type(cls, v):
        v = v.lower()
        if v not in SUPPORTED_SHAPES:
            raise ValueError(f"Shape must be one of {SUPPORTED_SHAPES}")
        return v

class IntersectRequest(BaseModel):
    body1: IntersectBody
    body2: IntersectBody

# -----------------------------------------------------------------------------
# Функции загрузки и трансформации (проверенные)
# -----------------------------------------------------------------------------
def load_primitive(shape: str) -> cq.Workplane:
    """Загружает STEP-примитив и центрирует его в (0,0,0)"""
    path = PRIMITIVES_DIR / f"{shape}.step"
    if not path.exists():
        raise RuntimeError(f"Primitive not found: {path}")
    
    imported = cq.importers.importStep(str(path))
    wp = cq.Workplane().add(imported.val()) if hasattr(imported, 'val') and imported.val() else imported
    
    # Поворот для согласования осей (Y → Z)
    wp = wp.rotate((0, 0, 0), (1, 0, 0), 90)
    
    # Центрирование
    bb = wp.val().BoundingBox()
    center = cq.Vector((bb.xmin + bb.xmax)/2, (bb.ymin + bb.ymax)/2, (bb.zmin + bb.zmax)/2)
    wp = wp.translate(-center)
    return wp

def transform_primitive(shape: cq.Workplane, pos: BodyPosition, rot: BodyRotation) -> cq.Workplane:
    """Применяет поворот и перемещение к примитиву"""
    wp = shape
    if abs(rot.angle_deg) > 0.001:
        wp = wp.rotate((0, 0, 0), (0, 1, 0), -rot.angle_deg)
    wp = wp.translate((pos.x, pos.y, pos.z))
    return wp

# -----------------------------------------------------------------------------
# Функции пересечения
# -----------------------------------------------------------------------------
def get_intersection_curves(shape1: cq.Workplane, shape2: cq.Workplane) -> List[List[Tuple[float, float, float]]]:
    intersection = shape1.intersect(shape2)
    if intersection.val().isNull():
        return []
    curves = []
    for edge in intersection.edges().vals():
        pts = []
        length = edge.Length()
        n = max(2, min(50, int(length / 2)))
        for i in range(n + 1):
            p = edge.positionAt(i / n)
            pts.append((p.x, p.y, p.z))
        curves.append(pts)
    return curves

# -----------------------------------------------------------------------------
# SVG экспорт (100% рабочий, как в вашем резаке)
# -----------------------------------------------------------------------------
def make_3view_svg(shape: cq.Workplane, base_name: str) -> dict:
    """Создаёт SVG-чертёж с тремя видами (фронт, топ, лево)"""
    svg_opts = {
        "width": 400,
        "height": 400,
        "marginLeft": 20,
        "marginTop": 20,
        "strokeWidth": 0.6,
        "strokeColor": (255, 140, 0),
        "hiddenColor": (173, 216, 230),
        "showHidden": True,
        "showAxes": False
    }

    views = {}
    for view, proj in [("front", (0, 0, -1)), ("top", (0, -1, 0)), ("left", (-1, 0, 0))]:
        svg_opts["projectionDir"] = proj
        path = TEMP_DIR / f"{base_name}_{view}.svg"
        cq.exporters.export(shape, str(path), opt=svg_opts)
        views[view] = str(path)

    return views

# -----------------------------------------------------------------------------
# API эндпоинт пересечения
# -----------------------------------------------------------------------------
@app.post("/api/intersect")
async def intersect_endpoint(req: IntersectRequest):
    try:
        print(f"\n=== INTERSECTION: {req.body1.type} + {req.body2.type} ===")
        print(f"  Body A: pos=({req.body1.position.x}, {req.body1.position.z}), rot={req.body1.rotation.angle_deg}")
        print(f"  Body B: pos=({req.body2.position.x}, {req.body2.position.z}), rot={req.body2.rotation.angle_deg}")

        shape1 = transform_primitive(load_primitive(req.body1.type), req.body1.position, req.body1.rotation)
        shape2 = transform_primitive(load_primitive(req.body2.type), req.body2.position, req.body2.rotation)

        curves = get_intersection_curves(shape1, shape2)
        print(f"  Intersection curves: {len(curves)}")

        combined = shape1.union(shape2)
        volume = combined.val().Volume()
        print(f"  Volume: {volume:.2f} mm3")

        base_name = f"intersect_{uuid.uuid4().hex[:8]}"

        step_path = TEMP_DIR / f"{base_name}.step"
        stl_path = TEMP_DIR / f"{base_name}.stl"
        cq.exporters.export(combined, str(step_path))
        cq.exporters.export(combined, str(stl_path), tolerance=0.01, angularTolerance=0.1)
        print("  Exported STEP and STL")

        svg_files = make_3view_svg(combined, base_name)
        print("  Created SVG drawings")

        return {
            "success": True,
            "message": "Drawing created",
            "volume": round(volume, 2),
            "downloads": {
                "step": {
                    "filename": f"{base_name}.step",
                    "url": f"/api/download/step/{base_name}.step",
                    "size": step_path.stat().st_size
                },
                "stl": {
                    "filename": f"{base_name}.stl",
                    "url": f"/api/download/stl/{base_name}.stl",
                    "size": stl_path.stat().st_size
                },
                "svg": {
                    "front": {
                        "filename": f"{base_name}_front.svg",
                        "url": f"/api/download/svg/{base_name}_front.svg",
                        "size": Path(svg_files["front"]).stat().st_size
                    },
                    "top": {
                        "filename": f"{base_name}_top.svg",
                        "url": f"/api/download/svg/{base_name}_top.svg",
                        "size": Path(svg_files["top"]).stat().st_size
                    },
                    "left": {
                        "filename": f"{base_name}_left.svg",
                        "url": f"/api/download/svg/{base_name}_left.svg",
                        "size": Path(svg_files["left"]).stat().st_size
                    }
                }
            }
        }
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

# -----------------------------------------------------------------------------
# (Опционально) ваш старый эндпоинт create-model – можно оставить для совместимости
# -----------------------------------------------------------------------------
# ... если нужно, вставьте сюда код из вашего прошлого проекта, но он не обязателен.

# -----------------------------------------------------------------------------
# Эндпоинты скачивания
# -----------------------------------------------------------------------------
@app.get("/api/download/step/{filename}")
def download_step(filename: str):
    path = TEMP_DIR / filename
    if not path.exists(): raise HTTPException(404)
    return FileResponse(path, media_type="application/step", filename=filename)

@app.get("/api/download/stl/{filename}")
def download_stl(filename: str):
    path = TEMP_DIR / filename
    if not path.exists(): raise HTTPException(404)
    return FileResponse(path, media_type="application/sla", filename=filename)

@app.get("/api/download/svg/{filename}")
def download_svg(filename: str):
    path = TEMP_DIR / filename
    if not path.exists(): raise HTTPException(404)
    return FileResponse(path, media_type="image/svg+xml", filename=filename)

@app.get("/api/health")
def health():
    return {"status": "ok", "cadquery": cq.__version__}

from pathlib import Path
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True))

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*70)
    print("Intersection of Solids (working SVG export)")
    print("http://localhost:8000")
    print("="*70)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
