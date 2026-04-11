"Вырезы на многограниках"

from __future__ import annotations

import uuid
import traceback
from pathlib import Path
from typing import List, Tuple, Dict

import cadquery as cq
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, validator

from OCP.gp import gp_Pnt, gp_Vec
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeWire,
    BRepBuilderAPI_MakeVertex,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_MakeFace,
)
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp

# -----------------------------------------------------------------------------
# Конфигурация
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
TEMP_DIR = BASE_DIR / "temp"
STATIC_DIR = BASE_DIR / "static"

TEMP_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

FIXED_HEIGHT = 50.0
CUTTER_DEPTH = 200.0

SHAPES: Dict[str, Path] = {}

# -----------------------------------------------------------------------------
# Вспомогательные функции (без изменений)
# -----------------------------------------------------------------------------
def normalize_to_real(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    return [((x - 0.5) * 60.0, (z - 0.5) * 60.0) for x, z in points]

def normalize_single_point(point: Tuple[float, float]) -> Tuple[float, float]:
    return ((point[0] - 0.5) * 60.0, (point[1] - 0.5) * 60.0)

def calculate_volume(solid) -> float:
    try:
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(solid, props)
        return props.Mass()
    except:
        try:
            props = GProp_GProps()
            BRepGProp.VolumeProperties(solid, props)
            return props.Mass()
        except:
            return 0.0


def generate_pyramid_occ(base_points_real, apex_real, step_path):
    wire_builder = BRepBuilderAPI_MakeWire()
    for i in range(len(base_points_real)):
        p1 = base_points_real[i]
        p2 = base_points_real[(i + 1) % len(base_points_real)]
        edge = BRepBuilderAPI_MakeEdge(
            gp_Pnt(p1[0], 0.0, p1[1]),
            gp_Pnt(p2[0], 0.0, p2[1])
        ).Edge()
        wire_builder.Add(edge)
    wire = wire_builder.Wire()
    vertex = BRepBuilderAPI_MakeVertex(
        gp_Pnt(apex_real[0], FIXED_HEIGHT, apex_real[1])
    ).Vertex()
    loft = BRepOffsetAPI_ThruSections(True, True)
    loft.AddWire(wire)
    loft.AddVertex(vertex)
    loft.Build()
    if not loft.IsDone():
        raise RuntimeError("Failed to build pyramid")
    solid = loft.Shape()
    volume = calculate_volume(solid)
    writer = STEPControl_Writer()
    writer.Transfer(solid, STEPControl_AsIs)
    if writer.Write(str(step_path)) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")
    return volume, solid


def generate_prism_occ(base_points_real, apex_real, step_path):
    poly = BRepBuilderAPI_MakePolygon()
    for x, z in base_points_real:
        poly.Add(gp_Pnt(x, 0.0, z))
    poly.Close()
    wire = poly.Wire()
    face = BRepBuilderAPI_MakeFace(wire).Face()
    center_x = sum(p[0] for p in base_points_real) / len(base_points_real)
    center_z = sum(p[1] for p in base_points_real) / len(base_points_real)
    dx = apex_real[0] - center_x
    dz = apex_real[1] - center_z
    vec = gp_Vec(dx, FIXED_HEIGHT, dz)
    prism = BRepPrimAPI_MakePrism(face, vec).Shape()
    volume = calculate_volume(prism)
    writer = STEPControl_Writer()
    writer.Transfer(prism, STEPControl_AsIs)
    if writer.Write(str(step_path)) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")
    return volume, prism


def get_edges_with_visibility(part: cq.Workplane, view_plane: str):
    visible_edges = []
    hidden_edges = []
    edge_cache = {}

    for face in part.faces().objects:
        try:
            normal = face.normalAt()
        except:
            continue

        if view_plane == 'XY':
            is_visible = normal.z > 0
            def project(p): return (p.x, p.y)
        elif view_plane == 'ZY':
            is_visible = normal.x > 0
            def project(p): return (p.z, p.y)
        else:
            is_visible = normal.y > 0
            def project(p): return (p.x, p.z)

        for wire in face.Wires():
            for edge in wire.Edges():
                p1 = edge.startPoint()
                p2 = edge.endPoint()
                pts = (project(p1), project(p2))
                key = tuple(sorted([(round(pts[0][0], 6), round(pts[0][1], 6)),
                                    (round(pts[1][0], 6), round(pts[1][1], 6))]))
                if key in edge_cache:
                    edge_cache[key] = edge_cache[key] or is_visible
                else:
                    edge_cache[key] = is_visible

    for key, is_visible in edge_cache.items():
        p1, p2 = key
        if is_visible:
            visible_edges.append([p1, p2])
        else:
            hidden_edges.append([p1, p2])

    return visible_edges, hidden_edges


def get_projection_bbox(visible, hidden):
    all_edges = visible + hidden
    if not all_edges:
        return None
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    for edge in all_edges:
        for x, y in edge:
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
    return {"minX": min_x, "maxX": max_x, "minY": min_y, "maxY": max_y}


def transform_contour_to_real(contour_norm: List[List[float]], side: str, proj_bbox: Dict | None):
    if proj_bbox is None:
        return [((u - 0.5) * 60.0, (v - 0.5) * 50.0 + 25.0) for u, v in contour_norm]

    canvas_size = 600.0
    margin = 40.0

    minX = proj_bbox["minX"]
    maxX = proj_bbox["maxX"]
    minY = proj_bbox["minY"]
    maxY = proj_bbox["maxY"]

    delX = max(maxX - minX, 1e-6)
    delY = max(maxY - minY, 1e-6)

    scaleX = (canvas_size - 2 * margin) / delX
    scaleY = (canvas_size - 2 * margin) / delY
    scale = min(scaleX, scaleY)

    real_contour = []
    for u, v in contour_norm:
        screen_x = u * canvas_size
        screen_y = (1.0 - v) * canvas_size
        world_x = minX + (screen_x - margin) / scale
        world_y_unflipped = minY + (screen_y - margin) / scale
        world_y = minY + maxY - world_y_unflipped
        real_contour.append((world_x, world_y))
    return real_contour


def make_cutter_in_plane(contour_points: List[Tuple[float, float]], side: str):
    if not contour_points or len(contour_points) < 3:
        raise ValueError("Контур выреза должен содержать минимум 3 точки")

    if side == "front":
        wp = cq.Workplane("XY")
        for i, (x, y) in enumerate(contour_points):
            if i == 0:
                wp = wp.moveTo(x, y)
            else:
                wp = wp.lineTo(x, y)
        wp = wp.close()
        return wp.extrude(CUTTER_DEPTH, both=True)
    else:
        wp = cq.Workplane("YZ")
        for i, (z, y) in enumerate(contour_points):
            if i == 0:
                wp = wp.moveTo(y, z)
            else:
                wp = wp.lineTo(y, z)
        wp = wp.close()
        return wp.extrude(CUTTER_DEPTH, both=True)


def create_three_view_drawing(part: cq.Workplane, filename: str) -> Path:
    """
    Создаёт единый SVG‑файл с тремя проекциями детали (спереди, сверху, слева).
    Стиль: графитовый фон на всю страницу, оранжевые видимые линии, голубые скрытые.
    Толщина линий 0.6.
    """
    opts = {
        "width": 380,
        "height": 280,
        "marginLeft": 25,
        "marginTop": 25,
        "showAxes": False,
        "showHidden": True,
        "strokeWidth": 0.6,                     # уменьшено на 25%
        "strokeColor": (255, 140, 0),           # оранжевый – видимые линии
        "hiddenColor": (173, 216, 230),         # голубой – скрытые линии
    }

    tmp_front = TEMP_DIR / "_tmp_front.svg"
    tmp_top   = TEMP_DIR / "_tmp_top.svg"
    tmp_left  = TEMP_DIR / "_tmp_left.svg"

    try:
        cq.exporters.export(part, str(tmp_front), opt=opts | {"projectionDir": (0, 0, 1)})
        cq.exporters.export(part, str(tmp_top),   opt=opts | {"projectionDir": (0, -1, 0)})
        cq.exporters.export(part, str(tmp_left),  opt=opts | {"projectionDir": (1, 0, 0)})

        def clean_svg(path: Path) -> str:
            lines = path.read_text(encoding="utf-8").splitlines()
            cleaned = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('<?xml') or stripped.startswith('<!DOCTYPE'):
                    continue
                cleaned.append(line)
            return '\n'.join(cleaned).strip()

        svg_front = clean_svg(tmp_front)
        svg_top   = clean_svg(tmp_top)
        svg_left  = clean_svg(tmp_left)

        # Фон на всю страницу 1200×720
        combined_svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="2000" height="1400" xmlns="http://www.w3.org/2000/svg">
  <!-- Графитовый фон на всю страницу -->
  <rect x="0" y="0" width="2000" height="1400" fill="#2a2a2a" />
  
  <g transform="translate(20,80)">{svg_front}</g>
  <g transform="translate(620,80)">{svg_left}</g>
  <g transform="translate(20,480)">{svg_top}</g>
</svg>'''

        result_path = TEMP_DIR / filename
        result_path.write_text(combined_svg, encoding="utf-8")
        return result_path

    finally:
        for p in (tmp_front, tmp_top, tmp_left):
            if p.exists():
                p.unlink()
                
# -----------------------------------------------------------------------------
# FastAPI (остальное без изменений)
# -----------------------------------------------------------------------------
app = FastAPI(title="Генератор многогранников с вырезом (HLR)", version="8.0.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerateRequest(BaseModel):
    shape: str
    base_points: List[List[float]]
    apex_point: List[float]

    @validator("shape")
    def validate_shape(cls, v):
        v = v.lower()
        if v not in {"pyramid", "prism"}:
            raise ValueError("shape must be 'pyramid' or 'prism'")
        return v

    @validator("base_points")
    def validate_base_points(cls, v):
        if len(v) < 3:
            raise ValueError("Base polygon must have at least 3 points")
        for p in v:
            if len(p) != 2:
                raise ValueError("Each base point must be [x, z]")
            p[0] = max(0.0, min(1.0, float(p[0])))
            p[1] = max(0.0, min(1.0, float(p[1])))
        return v

    @validator("apex_point")
    def validate_apex_point(cls, v):
        if len(v) != 2:
            raise ValueError("apex_point must be [x, z]")
        v[0] = max(0.0, min(1.0, float(v[0])))
        v[1] = max(0.0, min(1.0, float(v[1])))
        return v


class CutRequest(BaseModel):
    base_filename: str
    side: str
    contour: List[List[float]]

    @validator("side")
    def validate_side(cls, v):
        if v not in {"front", "left"}:
            raise ValueError("side must be 'front' or 'left'")
        return v

    @validator("contour")
    def validate_contour(cls, v):
        if len(v) < 3:
            raise ValueError("Contour must have at least 3 points")
        for p in v:
            if len(p) != 2:
                raise ValueError("Each point must be [u, v]")
            p[0] = max(0.0, min(1.0, float(p[0])))
            p[1] = max(0.0, min(1.0, float(p[1])))
        return v


@app.post("/api/generate")
def generate_polyhedron(req: GenerateRequest):
    try:
        base_real = normalize_to_real([(p[0], p[1]) for p in req.base_points])
        apex_real = normalize_single_point((req.apex_point[0], req.apex_point[1]))
        file_id = uuid.uuid4().hex[:8]
        base_name = f"{req.shape}_{file_id}"
        step_path = TEMP_DIR / f"{base_name}.step"

        if req.shape == "pyramid":
            volume, solid = generate_pyramid_occ(base_real, apex_real, step_path)
        else:
            volume, solid = generate_prism_occ(base_real, apex_real, step_path)

        SHAPES[base_name] = step_path

        return {
            "success": True,
            "base_filename": base_name,
            "volumes": {"total": round(volume, 2)},
            "downloads": {
                "step": {
                    "filename": f"{base_name}.step",
                    "url": f"/api/download/step/{base_name}.step"
                }
            }
        }
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.get("/api/get-hlr")
def get_hlr(base_filename: str, side: str):
    try:
        step_path = SHAPES.get(base_filename)
        if step_path is None or not step_path.exists():
            raise HTTPException(404, "Model not found")

        part = cq.importers.importStep(str(step_path))
        view_plane = "XY" if side == "front" else "ZY"
        visible, hidden = get_edges_with_visibility(part, view_plane)
        proj_bbox = get_projection_bbox(visible, hidden)

        return {
            "visible": visible,
            "hidden": hidden,
            "proj_bbox": proj_bbox
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/apply-cut")
def apply_cut(req: CutRequest):
    try:
        step_path = SHAPES.get(req.base_filename)
        if step_path is None or not step_path.exists():
            raise HTTPException(404, "Base file not found")

        body = cq.importers.importStep(str(step_path))

        part = cq.importers.importStep(str(step_path))
        view_plane = "XY" if req.side == "front" else "ZY"
        visible, hidden = get_edges_with_visibility(part, view_plane)
        proj_bbox = get_projection_bbox(visible, hidden)

        contour_real = transform_contour_to_real(req.contour, req.side, proj_bbox)
        cutter = make_cutter_in_plane(contour_real, req.side)
        result = body.cut(cutter)

        file_id = uuid.uuid4().hex[:8]
        new_filename = f"{req.base_filename}_cut_{file_id}"
        new_step_path = TEMP_DIR / f"{new_filename}.step"
        cq.exporters.export(result, str(new_step_path))

        volume = result.val().Volume()
        SHAPES[new_filename] = new_step_path

        return {
            "success": True,
            "base_filename": new_filename,
            "volumes": {"total": round(volume, 2)},
            "downloads": {
                "step": {
                    "filename": f"{new_filename}.step",
                    "url": f"/api/download/step/{new_filename}.step"
                }
            }
        }
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.get("/api/export-drawing")
def export_drawing(base_filename: str):
    try:
        step_path = SHAPES.get(base_filename)
        if step_path is None or not step_path.exists():
            raise HTTPException(404, "Model not found")

        part = cq.importers.importStep(str(step_path))
        drawing_filename = f"{base_filename}_3views.svg"
        svg_path = create_three_view_drawing(part, drawing_filename)

        return FileResponse(
            svg_path,
            media_type="image/svg+xml",
            filename=drawing_filename
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.get("/api/download/step/{filename}")
def download_step(filename: str):
    path = TEMP_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type="application/step", filename=filename)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "8.0.2"}





if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*90)
    print("   Polyhedron Generator Service v8.0.2 — экспорт SVG исправлен (toSvg)")
    print("="*90)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
