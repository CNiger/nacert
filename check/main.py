import os
import shutil
import tempfile
import hashlib
import time
from pathlib import Path
from typing import List
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import numpy as np
import cadquery as cq
import trimesh
from scipy.stats import wasserstein_distance

app = FastAPI(title="STEP Checker")

# свой temp как у всех сервисов
TEMP_DIR = Path(__file__).parent / "temp"
TEMP_DIR.mkdir(exist_ok=True)

PENALTY_POWER = 1.6

def aggressive_penalty(sim: float) -> float:
    return sim ** PENALTY_POWER

class StepComparator:
    def __init__(self, ref_path: str):
        self.ref_cq = cq.importers.importStep(ref_path)
        self.ref_mesh = self._to_mesh(self.ref_cq)
        self.ref_mesh = self._normalize(self.ref_mesh)
        self.ref_mesh = self._align_pca(self.ref_mesh)
        self.ref_voxels = {
            32: self._to_voxels(self.ref_mesh, 32),
            64: self._to_voxels(self.ref_mesh, 64)
        }
        self.ref_d2, self.ref_a3 = self._d2_a3(self.ref_mesh)
        self.ref_edges = self._count_edges(self.ref_cq)
        self.ref_fillets = self._detect_fillets(self.ref_cq)
        self.ref_circles = self._detect_circles(self.ref_cq)
        self.ref_volume = self.ref_mesh.volume

    def _to_mesh(self, shape):
        fd, stl = tempfile.mkstemp(suffix='.stl', dir=TEMP_DIR)
        os.close(fd)
        cq.exporters.export(shape, stl, 'STL')
        mesh = trimesh.load_mesh(stl)
        os.unlink(stl)
        if isinstance(mesh, list):
            mesh = trimesh.util.concatenate(mesh)
        return mesh

    def _normalize(self, mesh):
        mesh.vertices -= mesh.centroid
        s = np.max(mesh.extents)
        if s > 0:
            mesh.vertices /= s
        return mesh

    def _align_pca(self, mesh):
        points = mesh.vertices - mesh.centroid
        cov = np.cov(points.T)
        _, eigvecs = np.linalg.eigh(cov)
        mesh.vertices = points @ eigvecs[:, ::-1]
        return mesh

    def _to_voxels(self, mesh, res):
        vox = mesh.voxelized(pitch=1.0/res)
        mat = vox.matrix
        if mat.shape != (res,res,res):
            m = np.zeros((res,res,res), dtype=bool)
            r = tuple(min(mat.shape[i], res) for i in range(3))
            m[:r[0], :r[1], :r[2]] = mat[:r[0], :r[1], :r[2]]
            mat = m
        return mat

    def _d2_a3(self, mesh, n=4000):
        np.random.seed(42)
        pts, _ = trimesh.sample.sample_surface(mesh, n)
        if len(pts) < 3:
            return np.zeros(50), np.zeros(50)
        idx = np.random.choice(len(pts), size=(n//2,2))
        d = np.linalg.norm(pts[idx[:,0]] - pts[idx[:,1]], axis=1)
        d /= max(d.max(), 1e-8)
        d2, _ = np.histogram(d, bins=50, range=(0,1), density=True)
        tri = np.random.choice(len(pts), size=(n//4,3))
        angles = []
        for i,j,k in tri:
            a = pts[j]-pts[i]
            b = pts[k]-pts[i]
            na, nb = np.linalg.norm(a), np.linalg.norm(b)
            if na<1e-6 or nb<1e-6: continue
            cos = np.clip(np.dot(a,b)/(na*nb), -1,1)
            angles.append(np.arccos(cos))
        if angles:
            a3, _ = np.histogram(angles, bins=50, range=(0,np.pi), density=True)
        else:
            a3 = np.zeros(50)
        return d2, a3

    def _count_edges(self, shape):
        edges = list(shape.edges())
        straight = sum(1 for e in edges if 'LINE' in str(e.geomType()).upper())
        return {'total': len(edges), 'straight': straight, 'curved': len(edges)-straight}

    def _detect_fillets(self, shape):
        faces = list(shape.faces())
        curved = sum(1 for f in faces if any(t in str(f.geomType()).upper() for t in ('CYLINDER','SPHERE','CONE','TORUS')))
        total = len(faces)
        return {'total_faces': total, 'curved_faces': curved, 'ratio': curved/total if total else 0}

    def _detect_circles(self, shape):
        circles = []
        for f in list(shape.faces()):
            if 'PLANE' in str(f.geomType()).upper():
                wire = f.outerWire()
                edges = list(wire.edges())
                if len(edges)==1 and 'CIRCLE' in str(edges[0].geomType()).upper():
                    circles.append(edges[0].radius())
        return circles

    def compare(self, stud_path):
        stud_cq = cq.importers.importStep(stud_path)
        mesh = self._to_mesh(stud_cq)
        mesh = self._normalize(mesh)
        mesh = self._align_pca(mesh)

        ious = []
        for res in (32,64):
            sv = self._to_voxels(mesh, res)
            rv = self.ref_voxels[res]
            inter = np.logical_and(rv, sv).sum()
            union = np.logical_or(rv, sv).sum()
            ious.append(inter/union if union else 1.0)
        vox_iou = np.mean(ious)

        d2, a3 = self._d2_a3(mesh)
        d2_sim = 1 - min(1.0, wasserstein_distance(np.arange(50), np.arange(50), self.ref_d2, d2)/50)
        a3_sim = 1 - min(1.0, wasserstein_distance(np.arange(50), np.arange(50), self.ref_a3, a3)/np.pi)
        d2a3 = 0.5*d2_sim + 0.5*a3_sim

        e = self._count_edges(stud_cq)
        ed_sim = 1 - (abs(self.ref_edges['total']-e['total'])/max(self.ref_edges['total'],1)*0.6 +
                      abs(self.ref_edges['straight']/max(self.ref_edges['total'],1) - e['straight']/max(e['total'],1))*0.4)
        ed_sim = max(0, min(1, ed_sim))

        f = self._detect_fillets(stud_cq)
        fil_sim = 1 - min(1.0, abs(self.ref_fillets['ratio'] - f['ratio']))

        c = self._detect_circles(stud_cq)
        count_diff = abs(len(self.ref_circles)-len(c))/max(len(self.ref_circles),1)
        if self.ref_circles and c:
            r1, r2 = sorted(self.ref_circles), sorted(c)
            l = min(len(r1), len(r2))
            rad_diff = sum(abs(r1[i]-r2[i])/max(r1[i],1e-8) for i in range(l))/l
            rad_sim = 1 - min(1.0, rad_diff)
        else:
            rad_sim = 0.0
        circ_sim = 1 - (count_diff*0.5 + (1-rad_sim)*0.5)

        vox = aggressive_penalty(vox_iou)
        d2a3 = aggressive_penalty(d2a3)
        ed = aggressive_penalty(ed_sim)
        fil = aggressive_penalty(fil_sim)
        circ = aggressive_penalty(circ_sim)

        w_v, w_d, w_e, w_f, w_c = 0.45, 0.25, 0.10, 0.10, 0.10
        total = (vox*w_v + d2a3*w_d + ed*w_e + fil*w_f + circ*w_c) * 100

        return {
            "file": Path(stud_path).name,
            "score": round(total, 1),
            "voxel_iou": round(vox*100, 1),
            "d2a3": round(d2a3*100, 1),
            "edges": round(ed*100, 1),
            "fillets": round(fil*100, 1),
            "circles": round(circ*100, 1),
            "details": {
                "ref_edges": self.ref_edges['total'],
                "stud_edges": e['total'],
                "ref_circles": len(self.ref_circles),
                "stud_circles": len(c)
            }
        }

@app.post("/compare")
async def compare_steps(
    reference: UploadFile = File(...),
    files: List[UploadFile] = File(...)
):
    import tempfile
    if not reference.filename.lower().endswith('.step'):
        raise HTTPException(400, "reference must be .step")
    
    session_dir = TEMP_DIR / f"session_{int(time.time())}_{hashlib.md5(reference.filename.encode()).hexdigest()[:8]}"
    session_dir.mkdir(exist_ok=True)
    
    try:
        ref_path = session_dir / "reference.step"
        with open(ref_path, "wb") as f:
            shutil.copyfileobj(reference.file, f)
        
        comparator = StepComparator(str(ref_path))
        results = []
        
        for f in files:
            if not f.filename.lower().endswith('.step'):
                continue
            stud_path = session_dir / f.filename
            with open(stud_path, "wb") as sf:
                shutil.copyfileobj(f.file, sf)
            results.append(comparator.compare(str(stud_path)))
        
        return {"success": True, "results": results}
    finally:
        shutil.rmtree(session_dir, ignore_errors=True)

@app.get("/")
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

# Монтируем статику как у всех сервисов
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
