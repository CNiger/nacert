from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from main import app as cut_app   
import uvicorn
from pathlib import Path

app = FastAPI(title="CAD Tools Suite")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
            <a href="/cut" class="tool-card">
                <div class="tool-icon">🔧</div>
                <div class="tool-title">CAD Cut Service</div>
                <div class="tool-desc">Профилирование деталей с вырезом. STEP, STL, SVG, DXF.</div>
            </a>
            <a href="/epure" class="tool-card">
                <div class="tool-icon">📏</div>
                <div class="tool-title">Эпюр Монжа</div>
                <div class="tool-desc">Трёхпроекционное черчение. Линии, прямоугольники, эллипсы.</div>
            </a>
            <a href="/ask" class="tool-card">
                <div class="tool-icon">📐</div>
                <div class="tool-title">Аксонометрия</div>
                <div class="tool-desc">Построение отрезков в косоугольной проекции. Координаты X Y Z.</div>
            </a>
        </div>
        <footer>CAD Tools Suite | injgaf.ru</footer>
    </div>
</body>
</html>
'''

@app.get("/step-viewer", response_class=HTMLResponse)
async def step_viewer():
    return HTMLResponse('''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STEP 3D Viewer</title>
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <style>
        body { margin: 0; overflow: hidden; font-family: monospace; }
        #info {
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(0,0,0,0.7);
            color: #ff5500;
            padding: 10px 20px;
            border-radius: 8px;
            pointer-events: none;
            z-index: 100;
        }
        #upload-btn {
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: #ff5500;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-family: monospace;
            font-weight: bold;
            z-index: 100;
        }
        #upload-btn:hover {
            background: #ff7700;
        }
        .status {
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: rgba(0,0,0,0.7);
            color: #0f0;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 12px;
            z-index: 100;
        }
    </style>
</head>
<body>
    <div id="info">
        <strong>STEP 3D Viewer</strong> | Перетащите STEP файл для просмотра
    </div>
    <input type="file" id="upload-btn" accept=".step,.stp">
    <div class="status" id="status">Готов к загрузке</div>

    <script type="importmap">
        {
            "imports": {
                "three": "https://unpkg.com/three@0.128.0/build/three.module.js",
                "three/addons/": "https://unpkg.com/three@0.128.0/examples/jsm/"
            }
        }
    </script>

    <script type="module">
        import * as THREE from 'three';
        import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
        import { STLLoader } from 'three/addons/loaders/STLLoader.js';

        // Инициализация сцены
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x0a0c10);
        scene.fog = new THREE.FogExp2(0x0a0c10, 0.002);

        const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.set(5, 5, 5);
        camera.lookAt(0, 0, 0);

        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.shadowMap.enabled = true;
        document.body.appendChild(renderer.domElement);

        // Освещение
        const ambientLight = new THREE.AmbientLight(0x404060);
        scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
        directionalLight.position.set(1, 2, 1);
        directionalLight.castShadow = true;
        scene.add(directionalLight);
        
        const backLight = new THREE.DirectionalLight(0x88aaff, 0.5);
        backLight.position.set(-1, -1, -0.5);
        scene.add(backLight);
        
        const fillLight = new THREE.PointLight(0x4466cc, 0.3);
        fillLight.position.set(0, 1, 0);
        scene.add(fillLight);

        // Сетка и оси
        const gridHelper = new THREE.GridHelper(20, 20, 0xff5500, 0x333333);
        gridHelper.position.y = -1;
        scene.add(gridHelper);
        
        const axesHelper = new THREE.AxesHelper(5);
        scene.add(axesHelper);

        // Орбит контрол
        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.autoRotate = false;
        controls.enableZoom = true;

        let currentModel = null;

        // Функция загрузки STEP (конвертируем в STL на сервере)
        async function loadSTEP(file) {
            const formData = new FormData();
            formData.append('file', file);
            
            document.getElementById('status').textContent = 'Конвертация STEP → STL...';
            document.getElementById('status').style.color = '#ffaa00';
            
            try {
                // Отправляем на сервер для конвертации
                const response = await fetch('/convert-step', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) throw new Error('Ошибка конвертации');
                
                const stlBlob = await response.blob();
                const stlUrl = URL.createObjectURL(stlBlob);
                
                document.getElementById('status').textContent = 'Загрузка 3D модели...';
                
                // Загружаем STL
                const loader = new STLLoader();
                loader.load(stlUrl, (geometry) => {
                    if (currentModel) scene.remove(currentModel);
                    
                    const material = new THREE.MeshPhongMaterial({ 
                        color: 0xff5500,
                        shininess: 60,
                        side: THREE.DoubleSide
                    });
                    const mesh = new THREE.Mesh(geometry, material);
                    mesh.castShadow = true;
                    mesh.receiveShadow = true;
                    
                    // Центрируем модель
                    geometry.computeBoundingBox();
                    const center = geometry.boundingBox.getCenter(new THREE.Vector3());
                    mesh.position.sub(center);
                    
                    scene.add(mesh);
                    currentModel = mesh;
                    
                    document.getElementById('status').textContent = '✓ Модель загружена';
                    document.getElementById('status').style.color = '#0f0';
                    
                    URL.revokeObjectURL(stlUrl);
                }, undefined, (error) => {
                    console.error(error);
                    document.getElementById('status').textContent = 'Ошибка загрузки STL';
                    document.getElementById('status').style.color = '#f00';
                });
                
            } catch (error) {
                console.error(error);
                document.getElementById('status').textContent = 'Ошибка конвертации STEP';
                document.getElementById('status').style.color = '#f00';
            }
        }

        // Обработчик загрузки файла
        document.getElementById('upload-btn').addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file && (file.name.endsWith('.step') || file.name.endsWith('.stp'))) {
                loadSTEP(file);
            } else {
                document.getElementById('status').textContent = 'Пожалуйста, выберите STEP файл (.step или .stp)';
                document.getElementById('status').style.color = '#f00';
            }
        });

        // Drag & Drop
        document.body.addEventListener('dragover', (e) => {
            e.preventDefault();
            document.body.style.border = '2px dashed #ff5500';
        });
        
        document.body.addEventListener('dragleave', () => {
            document.body.style.border = 'none';
        });
        
        document.body.addEventListener('drop', (e) => {
            e.preventDefault();
            document.body.style.border = 'none';
            const file = e.dataTransfer.files[0];
            if (file && (file.name.endsWith('.step') || file.name.endsWith('.stp'))) {
                loadSTEP(file);
            }
        });

        // Анимация
        function animate() {
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        }
        animate();

        // Адаптация под размер окна
        window.addEventListener('resize', onWindowResize, false);
        function onWindowResize() {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }
        
        // Добавляем звезды для красоты
        const starGeometry = new THREE.BufferGeometry();
        const starCount = 1000;
        const starPositions = new Float32Array(starCount * 3);
        for (let i = 0; i < starCount; i++) {
            starPositions[i*3] = (Math.random() - 0.5) * 200;
            starPositions[i*3+1] = (Math.random() - 0.5) * 100;
            starPositions[i*3+2] = (Math.random() - 0.5) * 100 - 50;
        }
        starGeometry.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
        const starMaterial = new THREE.PointsMaterial({ color: 0xffffff, size: 0.1 });
        const stars = new THREE.Points(starGeometry, starMaterial);
        scene.add(stars);
    </script>
</body>
</html>
    ''')

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML_INDEX

@app.get("/epure", response_class=HTMLResponse)
async def epure_mode():
    return FileResponse("alp.html")

@app.get("/ask", response_class=HTMLResponse)
async def axonometry_mode():
    return FileResponse("aks.html")

# Добавь этот эндпоинт для отдачи фавикона
@app.get("/favicon.ico", include_in_schema=False)
async def get_favicon():
    return FileResponse("favicon.ico")

app.mount("/cut", cut_app)

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
