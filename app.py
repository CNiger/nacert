import sys
import traceback

print("=== НАЧАЛО ЗАГРУЗКИ ===")

try:
    print("1. Импортирую FastAPI...")
    from fastapi import FastAPI
    print("   OK")
except Exception as e:
    print(f"   ОШИБКА: {e}")
    traceback.print_exc()

try:
    print("2. Пытаюсь импортировать rot_cut.main...")
    from rot_cut.main import app as rot_cut_app
    print("   OK — rot_cut импортирован")
except Exception as e:
    print(f"   ОШИБКА при импорте rot_cut: {e}")
    traceback.print_exc()

try:
    print("3. Пытаюсь импортировать pol_cut.main...")
    from pol_cut.main import app as pol_cut_app
    print("   OK — pol_cut импортирован")
except Exception as e:
    print(f"   ОШИБКА при импорте pol_cut: {e}")
    traceback.print_exc()

try:
    print("4. Пытаюсь импортировать sek.main...")
    from sek.main import app as sek_app
    print("   OK — sek импортирован")
except Exception as e:
    print(f"   ОШИБКА при импорте sek: {e}")
    traceback.print_exc()

try:
    print("5. Пытаюсь импортировать ras.main...")
    from ras.main import app as ras_app
    print("   OK — ras импортирован")
except Exception as e:
    print(f"   ОШИБКА при импорте ras: {e}")
    traceback.print_exc()

print("=== ВСЕ ИМПОРТЫ ВЫПОЛНЕНЫ ===")
print("Теперь создаю FastAPI приложение...")

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok", "message": "Сервер работает, импорты проверены"}

print("=== СЕРВЕР ГОТОВ К ЗАПУСКУ ===")
