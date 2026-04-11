"Вырезы на телах вращения "

import uuid
import traceback
from pathlib import Path
from typing import List, Tuple

import cadquery as cq
import ezdxf
from ezdxf.math import Vec2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, validator


try:
    from OCC.Core.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCC.Core.HLRAlgo import HLRAlgo_Projector
    from OCC.Core.TopoDS import TopoDS_Shape
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Ax1, gp_Trsf
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.GCPnts import GCPnts_AbscissaPoint
    from OCC.Core.GeomAdaptor import GeomAdaptor_Curve
    from OCC.Core.Geom import Geom_Curve
    OCC_AVAILABLE = True
except ImportError:
    OCC_AVAILABLE = False
    print("WARNING: pythonOCC not installed. HLR will use SVG fallback.")


BASE_DIR = Path(__file__).parent
PRIMITIVES_DIR = BASE_DIR / "primitives"
TEMP_DIR = BASE_DIR / "temp"
STATIC_DIR = BASE_DIR / "static"

TEMP_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

REQUIRED_PRIMITIVES = ["sphere.step", "cylinder.step", "cone.step"]
missing = [f for f in REQUIRED_PRIMITIVES if not (PRIMITIVES_DIR / f).exists()]
if missing:
    print("ERROR: Missing primitive files:", missing)
    exit(1)

SUPPORTED_SHAPES = {"sphere", "cylinder", "cone"}
CUTTER_DEPTH = 200.0

PRIMITIVE_CONFIG = {
    "sphere": {"radius": 30.0},
    "cylinder": {"radius": 30.0, "height": 70.0},
    "cone": {"radius": 30.0, "height": 70.0}
}



app = FastAPI(title="Engineering CAD Cut API", version="3.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CutRequest(BaseModel):
    shape: str
    points: List[List[float]]

    @validator("shape")
    def validate_shape(cls, v):
        v = v.lower()
        if v not in SUPPORTED_SHAPES:
            raise ValueError(f"Allowed shapes: {SUPPORTED_SHAPES}")
        return v

    @validator("points")
    def validate_points(cls, v):
        if len(v) < 3:
            raise ValueError("Contour must have at least 3 points")
        for p in v:
            if len(p) != 2:
                raise ValueError("Each point must be [x, y]")
            p[0] = max(0.0, min(1.0, float(p[0])))
            p[1] = max(0.0, min(1.0, float(p[1])))
        return v



def load_primitive(shape: str) -> cq.Workplane:
    path = PRIMITIVES_DIR / f"{shape}.step"
    if not path.exists():
        raise RuntimeError(f"Primitive not found: {path}")
    shape_obj = cq.importers.importStep(str(path))
    if hasattr(shape_obj, 'val'):
        return shape_obj
    else:
        return cq.Workplane().add(shape_obj)

def align_primitive(shape: cq.Workplane, shape_type: str) -> cq.Workplane:
    bb = shape.val().BoundingBox()
    dx, dy, dz = bb.xmax - bb.xmin, bb.ymax - bb.ymin, bb.zmax - bb.zmin

    if shape_type in ("cylinder", "cone"):
        if dy > dz and dy > dx:
            shape = shape.rotate((0,0,0), (1,0,0), -90)
        elif dx > dz and dx > dy:
            shape = shape.rotate((0,0,0), (0,1,0), 90)

        bb = shape.val().BoundingBox()
        if abs(bb.zmin) > 0.1:
            shape = shape.translate((0, 0, -bb.zmin))

        if shape_type == "cone":
            try:
                cm = shape.val().Center()
                bb = shape.val().BoundingBox()
                if cm.z > (bb.zmin + bb.zmax) / 2:
                    shape = shape.rotate((0,0,0), (1,0,0), 180)
                    bb = shape.val().BoundingBox()
                    shape = shape.translate((0, 0, -bb.zmin))
            except Exception:
                pass

    elif shape_type == "sphere":
        bb = shape.val().BoundingBox()
        cx, cy, cz = (bb.xmin+bb.xmax)/2, (bb.ymin+bb.ymax)/2, (bb.zmin+bb.zmax)/2
        if abs(cx)>0.1 or abs(cy)>0.1 or abs(cz)>0.1:
            shape = shape.translate((-cx, -cy, -cz))

    return shape

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
    if len(contour) < 3:
        raise ValueError("Contour must have at least 3 points")
    try:
        return (cq.Workplane("XZ")
                .polyline(contour)
                .close()
                .extrude(CUTTER_DEPTH, both=True))
    except Exception as e:
        raise RuntimeError(f"Failed to create cutter: {e}")

def perform_cut(shape: cq.Workplane, cutter: cq.Workplane) -> cq.Workplane:
    if shape.val().intersect(cutter.val()).isNull():
        raise RuntimeError("Cutter does not intersect the shape")
    return shape.cut(cutter)


def make_3view_svg(shape: cq.Workplane, base_name: str) -> dict:
    svg_opts = {
        "width": 400,
        "height": 400,
        "marginLeft": 20,
        "marginTop": 20,
        "strokeWidth": 0.5,
        "strokeColor": (255, 140, 0),          
        "hiddenColor": (173, 216, 230),        
        "showHidden": True,
        "showAxes": False
    }

    views = {}
    for view, dir in [("front", (0,-1,0)), ("top", (0,0,-1)), ("left", (-1,0,0))]:
        svg_opts["projectionDir"] = dir
        path = TEMP_DIR / f"{base_name}_{view}.svg"
        cq.exporters.export(shape, str(path), opt=svg_opts)
        views[view] = str(path)

    return views


def get_occ_shape(cq_shape: cq.Workplane) -> TopoDS_Shape:
    return cq_shape.val().wrapped

def rotate_shape(shape: TopoDS_Shape, axis: Tuple[float, float, float], angle_deg: float) -> TopoDS_Shape:
    ax = gp_Ax1(gp_Pnt(0,0,0), gp_Dir(axis[0], axis[1], axis[2]))
    trsf = gp_Trsf()
    trsf.SetRotation(ax, angle_deg * 3.141592653589793 / 180.0)
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()

def discretize_curve_to_polyline(curve, u1: float, u2: float, num_points: int = 50) -> List[Tuple[float, float]]:
    points = []
    adaptor = GeomAdaptor_Curve(curve)
    length = GCPnts_AbscissaPoint.Length(adaptor, u1, u2)
    if length <= 1e-6:
        return []
    for i in range(num_points + 1):
        t = u1 + (u2 - u1) * i / num_points
        pnt = curve.Value(t)
        points.append((pnt.X(), pnt.Y()))
    return points

def extract_hlr_edges(occ_shape: TopoDS_Shape, direction: Tuple[float, float, float]) -> Tuple[List, List]:
    ax2 = gp_Ax2()
    ax2.SetDirection(gp_Dir(direction[0], direction[1], direction[2]))
    projector = HLRAlgo_Projector(ax2)

    hlr = HLRBRep_Algo()
    hlr.Add(occ_shape)
    hlr.SetProjector(projector)
    hlr.Update()
    hlr.Hide()

    hlr_shapes = HLRBRep_HLRToShape(hlr)

    visible, hidden = [], []

    vis_compound = hlr_shapes.VCompound()
    if vis_compound is not None:
        explorer = TopExp_Explorer(vis_compound, TopAbs_EDGE)
        while explorer.More():
            edge = explorer.Current()
            curve, first, last = BRep_Tool.Curve(edge)
            if curve is not None:
                points = discretize_curve_to_polyline(curve, first, last)
                if len(points) >= 2:
                    visible.append(points)
            explorer.Next()

    hid_compound = hlr_shapes.HCompound()
    if hid_compound is not None:
        explorer = TopExp_Explorer(hid_compound, TopAbs_EDGE)
        while explorer.More():
            edge = explorer.Current()
            curve, first, last = BRep_Tool.Curve(edge)
            if curve is not None:
                points = discretize_curve_to_polyline(curve, first, last)
                if len(points) >= 2:
                    hidden.append(points)
            explorer.Next()

    return visible, hidden

def make_3view_drawing_hlr(occ_shape: TopoDS_Shape, base_name: str) -> Path:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add("Visible", color=7, linetype="CONTINUOUS")
    doc.layers.add("Hidden", color=5, linetype="DASHED")

    gap = 200

    def add_projection(rotated_shape, offset_x, offset_y):
        visible, hidden = extract_hlr_edges(rotated_shape, (0, 0, -1))
        for polyline in visible:
            points = [Vec2(x + offset_x, y + offset_y) for x, y in polyline]
            if len(points) >= 2:
                msp.add_lwpolyline(points, close=False, dxfattribs={"layer": "Visible"})
        for polyline in hidden:
            points = [Vec2(x + offset_x, y + offset_y) for x, y in polyline]
            if len(points) >= 2:
                msp.add_lwpolyline(points, close=False, dxfattribs={"layer": "Hidden"})

    # вид сверху
    add_projection(occ_shape, 0, gap)

    # вид спереди
    front = rotate_shape(occ_shape, (1, 0, 0), -90)
    add_projection(front, 0, 0)

    # вид слева
    left = rotate_shape(occ_shape, (0, 1, 0), 90)
    add_projection(left, gap, 0)

    dxf_path = TEMP_DIR / f"{base_name}_drawing.dxf"
    doc.saveas(dxf_path)
    return dxf_path


@app.post("/api/create-model")
def create_model(req: CutRequest):
    try:
        print(f"\n🔧 Processing {req.shape} with {len(req.points)} points")

        base = load_primitive(req.shape)
        base = align_primitive(base, req.shape)
        volume = base.val().Volume()

        contour = normalize_points(req.points, req.shape)
        cutter = make_cutter(contour)
        result = perform_cut(base, cutter)
        result_volume = result.val().Volume()
        cut_volume = volume - result_volume

        file_id = uuid.uuid4().hex[:8]
        base_name = f"{req.shape}_cut_{file_id}"

        step_path = TEMP_DIR / f"{base_name}.step"
        cq.exporters.export(result, str(step_path))


        stl_path = TEMP_DIR / f"{base_name}.stl"
        cq.exporters.export(result, str(stl_path), tolerance=0.01, angularTolerance=0.1)

        svg_files = make_3view_svg(result, base_name)


        dxf_path = None
        if OCC_AVAILABLE:
            try:
                occ_shape = get_occ_shape(result)
                dxf_path = make_3view_drawing_hlr(occ_shape, base_name)
            except Exception as e:
                print(f"HLR failed, DXF not generated: {e}")

        response = {
            "success": True,
            "message": "Модель создана",
            "shape": req.shape,
            "points_count": len(req.points),
            "volumes": {
                "shape": round(volume, 1),
                "result": round(result_volume, 1),
                "cut": round(cut_volume, 1)
            },
            "base_filename": base_name,
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

        if dxf_path:
            response["downloads"]["dxf"] = {
                "filename": f"{base_name}_drawing.dxf",
                "url": f"/api/download/dxf/{base_name}_drawing.dxf",
                "size": dxf_path.stat().st_size
            }

        return response

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.get("/api/download/step/{filename}")
def download_step(filename: str):
    path = TEMP_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type="application/step", filename=filename)

@app.get("/api/download/stl/{filename}")
def download_stl(filename: str):
    path = TEMP_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type="application/sla", filename=filename)

@app.get("/api/download/dxf/{filename}")
def download_dxf(filename: str):
    path = TEMP_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type="application/dxf", filename=filename)

@app.get("/api/download/svg/{filename}")
def download_svg(filename: str):
    path = TEMP_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type="image/svg+xml", filename=filename)

@app.get("/api/health")
def health():
    primitives = {shape: "ok" if (PRIMITIVES_DIR / f"{shape}.step").exists() else "missing"
                  for shape in SUPPORTED_SHAPES}
    return {
        "status": "ok",
        "cadquery": cq.__version__,
        "pythonocc": OCC_AVAILABLE,
        "primitives": primitives,
        "temp_files": len(list(TEMP_DIR.glob("*")))
    }




if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("Engineering CAD Cut Service v3.2 (SVG always, DXF optional)")
    print("="*60)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
