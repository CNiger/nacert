import os
import shutil
import tempfile
import hashlib
import time
import traceback
import gc
import asyncio
from pathlib import Path
from typing import List
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import numpy as np
import cadquery as cq
import trimesh

app = FastAPI(title="STEP Checker (Light)")
TEMP_DIR = Path(__file__).parent / "temp"
TEMP_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024
MEMORY_SEMAPHORE = asyncio.Semaphore(1)

class StepComparatorLight:
    def __init__(self, ref_path: str):
        self.ref_edges = {'total': 0, 'straight': 0}
        self.ref_voxels = None
        
        try:
            ref_cq = cq.importers.importStep(ref_path)
            ref_mesh = self._to_mesh(ref_cq)
            ref_mesh = self._normalize(ref_mesh)
            self.ref_voxels = self._to_voxels(ref_mesh, 24)  # 24³ вокселей
            self.ref_edges = self._count_edges(ref_cq)
        except Exception as e:
            print(f"Ошибка эталона: {e}", flush=True)

    def _to_mesh(self, shape):
        fd, stl = tempfile.mkstemp(suffix='.stl', dir=str(TEMP_DIR))
        os.close(fd)
        cq.exporters.export(shape, stl, 'STL')
        mesh = trimesh.load_mesh(stl)
        os.unlink(stl)
        if isinstance(mesh, list):
            mesh = trimesh.util.concatenate(mesh)
        return mesh

    def _normalize(self, mesh):
        if mesh is None or mesh.vertices is None or len(mesh.vertices) == 0:
            return mesh
        mesh.vertices -= mesh.centroid
        s = np.max(mesh.extents)
        if s > 0:
            mesh.vertices /= s
        return mesh

    def _to_voxels(self, mesh, res):
        try:
            pitch = max(mesh.extents.max() / res, 0.01)
            vox = mesh.voxelized(pitch=pitch)
            matrix = vox.matrix
            if matrix.size > res**3:
                from scipy.ndimage import zoom
                factors = [res / s for s in matrix.shape]
                matrix = zoom(matrix.astype(float), factors, order=0) > 0.5
            return matrix.astype(bool)
        except:
            return np.zeros((res, res, res), dtype=bool)

    def _count_edges(self, shape):
        try:
            edges = shape.edges().vals()
            straight = sum(1 for e in edges if 'LINE' in str(e.geomType()).upper())
            return {'total': len(edges), 'straight': straight}
        except:
            return {'total': 0, 'straight': 0}

    def compare(self, stud_path):
        try:
            stud_cq = cq.importers.importStep(stud_path)
            stud_mesh = self._to_mesh(stud_cq)
            stud_mesh = self._normalize(stud_mesh)
            sv = self._to_voxels(stud_mesh, 24)
            rv = self.ref_voxels if self.ref_voxels is not None else np.zeros((24,24,24), dtype=bool)
            
            inter = np.logical_and(rv, sv).sum()
            union = np.logical_or(rv, sv).sum()
            vox_iou = inter / union if union > 0 else 0.0
            
            e = self._count_edges(stud_cq)
            # Сходство по рёбрам (с учётом общего количества)
            edge_sim = 1.0
            if self.ref_edges['total'] > 0:
                diff = abs(self.ref_edges['total'] - e['total']) / self.ref_edges['total']
                edge_sim = max(0, 1 - min(1, diff))
            
            # Итоговая оценка (без штрафов)
            score = (vox_iou * 0.7 + edge_sim * 0.3) * 100
            
            return {
                "file": Path(stud_path).name,
                "score": round(score, 1),
                "voxel_iou": round(vox_iou * 100, 1),
                "edges": round(edge_sim * 100, 1),
                "details": {
                    "ref_edges": self.ref_edges['total'],
                    "stud_edges": e['total']
                }
            }
        except Exception as e:
            return {
                "file": Path(stud_path).name,
                "score": 0,
                "voxel_iou": 0,
                "edges": 0,
                "details": {"error": str(e)}
            }

@app.post("/compare")
async def compare_steps(
    reference: UploadFile = File(...),
    files: List[UploadFile] = File(...)
):
    async with MEMORY_SEMAPHORE:
        try:
            content = await reference.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(413, "Reference too large")
            
            session_dir = TEMP_DIR / f"session_{int(time.time())}_{hashlib.md5(reference.filename.encode()).hexdigest()[:8]}"
            session_dir.mkdir(exist_ok=True)
            
            ref_path = session_dir / "reference.step"
            with open(ref_path, "wb") as f:
                f.write(content)
            
            comparator = StepComparatorLight(str(ref_path))
            results = []
            
            for f in files[:5]:  # максимум 5 файлов
                if not f.filename.lower().endswith('.step'):
                    continue
                stud_content = await f.read()
                stud_path = session_dir / f.filename
                with open(stud_path, "wb") as sf:
                    sf.write(stud_content)
                results.append(comparator.compare(str(stud_path)))
                gc.collect()
            
            shutil.rmtree(session_dir, ignore_errors=True)
            return {"success": True, "results": results}
        except Exception as e:
            return JSONResponse(status_code=500, content={"success": False, "detail": str(e)})

@app.get("/")
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>STEP Checker</h1>")

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
