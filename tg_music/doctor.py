from __future__ import annotations

import shutil
import sys

from .config import CACHE_DIR, CONFIG_FILE, DATA_DIR, load_config
from .shared import format_bytes


def run_doctor() -> int:
    print("\n🔍 Comprobando diagnóstico del sistema para tg-music...\n")

    all_good = True

    # 1. Versión de Python
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 11):
        print(f"  [OK] Python {py_ver} (>= 3.11)")
    else:
        print(f"  [ERROR] Python {py_ver} es menor que 3.11. Se requiere Python >= 3.11.")
        all_good = False

    # 2. mpv (Obligatorio para reproducción)
    mpv_path = shutil.which("mpv")
    if mpv_path:
        print(f"  [OK] mpv encontrado: {mpv_path}")
    else:
        all_good = False
        print("  [ERROR] 'mpv' NO está instalado o no se encuentra en el PATH.")
        print("          tg-music requiere mpv para reproducir audio.")
        if sys.platform == "win32":
            print("          -> Instálalo con: winget install mpv.mpv  (o scoop install mpv)")
        elif sys.platform == "darwin":
            print("          -> Instálalo con: brew install mpv")
        else:
            print("          -> Instálalo con: sudo apt install mpv (Debian/Ubuntu) o sudo pacman -S mpv (Arch)")

    # 3. chafa (Opcional - carátulas en terminal)
    chafa_path = shutil.which("chafa")
    if chafa_path:
        print(f"  [OK] chafa encontrado: {chafa_path} (carátulas en alta resolución activadas)")
    else:
        print("  [INFO] 'chafa' no está instalado (Opcional).")
        print("         Las carátulas usarán modo de caracteres. Para alta resolución:")
        if sys.platform == "win32":
            print("         -> Instálalo con: winget install chafa  (o scoop install chafa)")
        elif sys.platform == "darwin":
            print("         -> Instálalo con: brew install chafa")
        else:
            print("         -> Instálalo con: sudo apt install chafa o sudo pacman -S chafa")

    # 4. playerctl (Opcional - Linux MPRIS2)
    if sys.platform.startswith("linux"):
        playerctl_path = shutil.which("playerctl")
        if playerctl_path:
            print(f"  [OK] playerctl encontrado: {playerctl_path} (control multimedia de escritorio activo)")
        else:
            print("  [INFO] 'playerctl' no encontrado (Opcional).")
            print("         Permite pausar/cambiar canciones desde la terminal o widgets del sistema:")
            print("         -> Instálalo con: sudo apt install playerctl o sudo pacman -S playerctl")

    # 5. Credenciales y Sesión de Telegram
    print("\n  Autenticación de Telegram:")
    try:
        cfg = load_config()
        if cfg.api_id and cfg.api_hash:
            print(f"  [OK] Credenciales api_id y api_hash configuradas en {CONFIG_FILE}")
        else:
            print(f"  [AVISO] Credenciales incompletas en {CONFIG_FILE}.")
            print("          Ejecuta: tg-music init")
    except Exception:
        print(f"  [AVISO] Configuración en {CONFIG_FILE} no encontrada.")
        print("          Ejecuta: tg-music init")

    session_path = DATA_DIR / "session.session"
    if session_path.exists():
        print(f"  [OK] Archivo de sesión de Telegram encontrado: {session_path}")
    else:
        print("  [AVISO] No se ha iniciado sesión de Telegram aún.")
        print("          Ejecuta: tg-music login (o inicia la TUI con :login)")

    # 6. Base de datos y Almacenamiento
    print("\n  Almacenamiento y Rutas:")
    db_path = DATA_DIR / "library.sqlite3"
    if db_path.exists():
        size = db_path.stat().st_size
        print(f"  [OK] Base de datos SQLite: {db_path} ({format_bytes(size)})")
    else:
        print(f"  [INFO] Base de datos SQLite se inicializará en: {db_path}")

    audio_cache = CACHE_DIR / "audio"
    if audio_cache.exists():
        cached_files = [f for f in audio_cache.glob("*") if f.is_file()]
        total_cache_size = sum(f.stat().st_size for f in cached_files)
        print(f"  [OK] Caché de audio: {audio_cache} ({len(cached_files)} pistas, {format_bytes(total_cache_size)})")
    else:
        print(f"  [INFO] Directorio de caché de audio listo en: {audio_cache}")

    print("\n" + "=" * 65)
    if all_good:
        print("🎉 ¡Todo listo! Tu sistema cumple con los requisitos para tg-music.\n")
        return 0
    else:
        print("⚠️  Hay dependencias obligatorias faltantes. Revisa los mensajes de arriba.\n")
        return 1
