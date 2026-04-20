import os
import shutil
import tempfile
import hashlib
import time
import traceback
import gc
from pathlib import Path
from typing import List
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import numpy as np
import cadquery as cq
import trimesh
from scipy.stats import wasserstein_distance

# OCC импорты для детекции кругов (если есть)
try:
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    OCC_OK = True
except:
    OCC_OK = False

app = FastAPI(title="STEP Checker")

TEMP_DIR = Path(__file__).parent / "temp"
TEMP_DIR.mkdir(exist_ok=True)

PENALTY_POWER = 1.6

def aggressive_penalty(sim: float) -> float:
    return sim ** PENALTY_POWER


class StepComparator:
    def __init__(self, ref_path: str):
        self.ref_cq = None
        self.ref_mesh = None
        self.ref_voxels = None
        self.ref_d2 = None
        self.ref_a3 = None
        self.ref_edges = None
        self.ref_fillets = None
        self.ref_circles = None

        try:
            self.ref_cq = cq.importers.importStep(ref_path)
            self.ref_mesh = self._to_mesh(self.ref_cq)
            self.ref_mesh = self._normalize(self.ref_mesh)
            self.ref_mesh = self._align_pca(self.ref_mesh)
            # Только разрешение 16 для экономии памяти
            self.ref_voxels = self._to_voxels(self.ref_mesh, 16)
            self.ref_d2, self.ref_a3 = self._d2_a3(self.ref_mesh, n=1000)
            self.ref_edges = self._count_edges(self.ref_cq)
            self.ref_fillets = self._detect_fillets(self.ref_cq)
            self.ref_circles = self._detect_circles(self.ref_cq)

            # Очищаем временные данные
            self.ref_cq = None
            gc.collect()

        except Exception as e:
            raise RuntimeError(f"Ошибка инициализации эталона: {e}")

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

    def _align_pca(self, mesh):
        if mesh is None or mesh.vertices is None or len(mesh.vertices) < 3:
            return mesh
        points = mesh.vertices - mesh.centroid
        cov = np.cov(points.T)
        _, eigvecs = np.linalg.eigh(cov)
        mesh.vertices = points @ eigvecs[:, ::-1]
        return mesh

    def _to_voxels(self, mesh, res):
        try:
            vox = mesh.voxelized(pitch=1.0 / res)
            return vox.matrix
        except:
            return np.zeros((res, res, res), dtype=bool)

    def _d2_a3(self, mesh, n=1000):
        try:
            np.random.seed(42)
            if mesh.is_empty or mesh.area < 1e-6:
                return np.zeros(50), np.zeros(50)
            pts, _ = trimesh.sample.sample_surface(mesh, min(n, int(mesh.area * 500)))
            if len(pts) < 3:
                return np.zeros(50), np.zeros(50)

            idx = np.random.choice(len(pts), size=(n // 2, 2))
            d = np.linalg.norm(pts[idx[:, 0]] - pts[idx[:, 1]], axis=1)
            d /= max(d.max(), 1e-8)
            d2, _ = np.histogram(d, bins=50, range=(0, 1), density=True)

            tri = np.random.choice(len(pts), size=(n // 4, 3))
            angles = []
            for i, j, k in tri:
                a = pts[j] - pts[i]
                b = pts[k] - pts[i]
                na, nb = np.linalg.norm(a), np.linalg.norm(b)
                if na < 1e-6 or nb < 1e-6:
                    continue
                cos = np.clip(np.dot(a, b) / (na * nb), -1, 1)
                angles.append(np.arccos(cos))

            if angles:
                a3, _ = np.histogram(angles, bins=50, range=(0, np.pi), density=True)
            else:
                a3 = np.zeros(50)

            return d2, a3
        except:
            return np.zeros(50), np.zeros(50)

    def _count_edges(self, shape):
        try:
            edges = shape.edges().vals()
            straight = sum(1 for e in edges if 'LINE' in str(e.geomType()).upper())
            return {'total': len(edges), 'straight': straight, 'curved': len(edges) - straight}
        except:
            return {'total': 0, 'straight': 0, 'curved': 0}

    def _detect_fillets(self, shape):
        try:
            faces = shape.faces().vals()
            curved = sum(1 for f in faces if any(t in str(f.geomType()).upper() for t in ('CYLINDER', 'SPHERE', 'CONE', 'TORUS')))
            total = len(faces)
            return {'total_faces': total, 'curved_faces': curved, 'ratio': curved / total if total else 0}
        except:
            return {'total_faces': 0, 'curved_faces': 0, 'ratio': 0}

    def _detect_circles(self, shape):
        circles = []
        if not OCC_OK:
            return circles
        try:
            faces = shape.faces().vals()
            for f in faces:
                try:
                    if 'PLANE' in str(f.geomType()).upper():
                        wire_occ = f.wrapped.OuterWire()
                        if wire_occ.IsNull():
                            continue
                        explorer = TopExp_Explorer(wire_occ, TopAbs_EDGE)
                        edge_count = 0
                        while explorer.More():
                            edge_count += 1
                            explorer.Next()
                        if edge_count == 1:
                            explorer = TopExp_Explorer(wire_occ, TopAbs_EDGE)
                            explorer.More()
                            edge_occ = explorer.Current()
                            curve = BRepAdaptor_Curve(edge_occ)
                            if curve.GetType() == 2:  # GeomAbs_Circle
                                circles.append(curve.Circle().Radius())
                except:
                    continue
        except:
            pass
        return circles

    def compare(self, stud_path):
        result = {
            "file": Path(stud_path).name,
            "score": 0,
            "voxel_iou": 0,
            "d2a3": 0,
            "edges": 0,
            "fillets": 0,
            "circles": 0,
            "details": {}
        }
        
        try:
            print(f"🔵 Сравнение: {stud_path}", flush=True)
            
            # 1. Загрузка студенческой модели
            stud_cq = cq.importers.importStep(stud_path)
            print(f"   ✅ Загружена", flush=True)
            
            # 2. Меш
            mesh = self._to_mesh(stud_cq)
            mesh = self._normalize(mesh)
            mesh = self._align_pca(mesh)
            print(f"   ✅ Меш создан, вершин: {len(mesh.vertices) if mesh.vertices is not None else 0}", flush=True)
            
            # 3. Воксельный IoU
            sv = self._to_voxels(mesh, 16)
            rv = self.ref_voxels
            inter = np.logical_and(rv, sv).sum()
            union = np.logical_or(rv, sv).sum()
            vox_iou = inter / union if union else 1.0
            print(f"   ✅ Voxel IoU: {vox_iou:.3f}", flush=True)
            
            # 4. D2/A3
            d2, a3 = self._d2_a3(mesh, n=1000)
            d2_sim = 1 - min(1.0, wasserstein_distance(np.arange(50), np.arange(50), self.ref_d2, d2) / 50)
            a3_sim = 1 - min(1.0, wasserstein_distance(np.arange(50), np.arange(50), self.ref_a3, a3) / np.pi)
            d2a3 = 0.5 * d2_sim + 0.5 * a3_sim
            print(f"   ✅ D2/A3: {d2a3:.3f}", flush=True)
            
            # 5. Рёбра
            e = self._count_edges(stud_cq)
            print(f"   ✅ Рёбра: total={e['total']}, straight={e['straight']}", flush=True)
            
            ed_sim = 1 - (abs(self.ref_edges['total'] - e['total']) / max(self.ref_edges['total'], 1) * 0.6 +
                          abs(self.ref_edges['straight'] / max(self.ref_edges['total'], 1) - e['straight'] / max(e['total'], 1)) * 0.4)
            ed_sim = max(0, min(1, ed_sim))
            
            # 6. Скругления
            f = self._detect_fillets(stud_cq)
            print(f"   ✅ Скругления: ratio={f['ratio']:.3f}", flush=True)
            fil_sim = 1 - min(1.0, abs(self.ref_fillets['ratio'] - f['ratio']))
            
            # 7. Круги
            c = self._detect_circles(stud_cq)
            print(f"   ✅ Круги: {len(c)} шт.", flush=True)
            
            count_diff = abs(len(self.ref_circles) - len(c)) / max(len(self.ref_circles), 1) if self.ref_circles else 0
            
            if len(self.ref_circles) == 0:
                circ_sim = 1.0
            else:
                if self.ref_circles and c:
                    r1, r2 = sorted(self.ref_circles), sorted(c)
                    l = min(len(r1), len(r2))
                    rad_diff = sum(abs(r1[i] - r2[i]) / max(r1[i], 1e-8) for i in range(l)) / l
                    rad_sim = 1 - min(1.0, rad_diff)
                else:
                    rad_sim = 0.0
                circ_sim = 1 - (count_diff * 0.5 + (1 - rad_sim) * 0.5)
            
            # 8. Штрафы
            vox = aggressive_penalty(vox_iou)
            d2a3 = aggressive_penalty(d2a3)
            ed = aggressive_penalty(ed_sim)
            fil = aggressive_penalty(fil_sim)
            circ = aggressive_penalty(circ_sim)
            
            # 9. Веса
            w_v, w_d, w_e, w_f, w_c = 0.45, 0.25, 0.10, 0.10, 0.10
            
            if len(self.ref_circles) == 0:
                w_c = 0
                total_other = w_v + w_d + w_e + w_f
                if total_other > 0:
                    w_v = w_v / total_other
                    w_d = w_d / total_other
                    w_e = w_e / total_other
                    w_f = w_f / total_other
            
            total = (vox * w_v + d2a3 * w_d + ed * w_e + fil * w_f + circ * w_c) * 100
            
            # 10. Заполняем результат
            result["score"] = round(total, 1)
            result["voxel_iou"] = round(vox * 100, 1)
            result["d2a3"] = round(d2a3 * 100, 1)
            result["edges"] = round(ed * 100, 1)
            result["fillets"] = round(fil * 100, 1)
            result["circles"] = round(circ * 100, 1)
            result["details"] = {
                "ref_edges": self.ref_edges['total'],
                "stud_edges": e['total'],
                "ref_circles": len(self.ref_circles),
                "stud_circles": len(c)
            }
            
            print(f"   ✅ ИТОГОВАЯ ОЦЕНКА: {result['score']}", flush=True)
            
            # Очистка
            del stud_cq, mesh
            gc.collect()
            
            return result
            
        except Exception as e:
            error_msg = f"Ошибка при сравнении {Path(stud_path).name}: {type(e).__name__}: {e}"
            print(f"❌ {error_msg}", flush=True)
            traceback.print_exc()
            
            result["details"] = {"error": error_msg}
            return result
    
    
    @app.post("/compare")
    async def compare_steps(
        reference: UploadFile = File(...),
        files: List[UploadFile] = File(...)
    ):
        try:
            if not reference.filename.lower().endswith('.step'):
                raise HTTPException(400, "reference must be .step")
    
            # Ограничение по памяти: не более 3 файлов за раз
            if len(files) > 3:
                files = files[:3]
    
            session_dir = TEMP_DIR / f"session_{int(time.time())}_{hashlib.md5(reference.filename.encode()).hexdigest()[:8]}"
            session_dir.mkdir(exist_ok=True)
    
            ref_path = session_dir / "reference.step"
            with open(ref_path, "wb") as f:
                shutil.copyfileobj(reference.file, f)
    
            comparator = StepComparator(str(ref_path))
            results = []
    
            for idx, f in enumerate(files):
                if not f.filename.lower().endswith('.step'):
                    continue
                stud_path = session_dir / f"{idx}_{f.filename}"
                with open(stud_path, "wb") as sf:
                    shutil.copyfileobj(f.file, sf)
                results.append(comparator.compare(str(stud_path)))
                gc.collect()
    
            del comparator
            gc.collect()
            shutil.rmtree(session_dir, ignore_errors=True)
    
            return {"success": True, "results": results}
    
        except Exception as e:
            error_details = traceback.format_exc()
            print(error_details, flush=True)
            return JSONResponse(
                status_code=500,
                content={"success": False, "detail": f"{type(e).__name__}: {str(e)}"}
            )


@app.get("/")
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>STEP Checker</h1><p>Интерфейс не найден, но API работает</p>")


app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
