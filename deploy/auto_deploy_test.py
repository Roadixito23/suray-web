"""
Auto-deploy script para test.suray.cl y suray.cl (el mismo archivo sirve para ambos).

Corre periodicamente via Cron Job en el servidor. Revisa el ultimo commit
de la rama configurada (main para test, produccion para suray.cl) del repo publico en GitHub, y si cambio respecto al
ultimo despliegue, descarga el tarball y sincroniza los archivos
versionados sobre el document root de la app, sin tocar archivos que no
estan en git (db.sqlite3, staticfiles/, .htaccess, tmp/, etc).

Despues de sincronizar ejecuta (con el mismo Python que corre este script):
pip install (solo si cambio requirements.txt), collectstatic y migrate. Si
alguno falla no se reinicia la app ni se guarda el SHA, y el siguiente
intento reintenta.

Se lanza desde el webhook de GitHub (suray_web/deploy_hook.py), desde un cron
de respaldo, o desde un cron que solo corre si existe deploy.flag. Un cron NO
tiene las variables de entorno de cPanel (Setup Python App): se pueden poner
en deploy.env (lineas KEY=VALUE).

Solo usa la libreria estandar de Python (sin requests/GitPython) para no
depender de que esas librerias esten instaladas en el venv de la app.
"""

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from datetime import datetime, timezone

# Cada sitio se configura por variables de entorno (en la app de cPanel, o delante del
# comando en el cron). Sin definirlas se despliega test.suray.cl, como antes.
#   DEPLOY_NAME   nombre del sitio: prefijo de log/estado/lock/flag/env ("test" o "produccion")
#   DEPLOY_BRANCH rama de GitHub a desplegar
#   DEPLOY_TARGET carpeta de la app
#   DEPLOY_DIR    carpeta de scripts y estado
REPO = "Roadixito23/suray-web"
NAME = os.environ.get("DEPLOY_NAME", "test")
BRANCH = os.environ.get("DEPLOY_BRANCH", "main")
DEPLOY_TARGET = os.environ.get("DEPLOY_TARGET", "/home/suraycl1/public_html/test.suray.cl")
DEPLOY_DIR = os.environ.get("DEPLOY_DIR", "/home/suraycl1/deploy_scripts")


def _archivo(nombre_test, nombre):
    """test conserva los nombres historicos; los demas sitios llevan su prefijo."""
    return os.path.join(DEPLOY_DIR, nombre_test if NAME == "test" else f"{NAME}_{nombre}")


STATE_FILE = os.path.join(DEPLOY_DIR, f"{NAME}_deploy_state.json")
LOG_FILE = os.path.join(DEPLOY_DIR, f"{NAME}_deploy.log")
LOCK_FILE = _archivo("deploy.lock", "deploy.lock")
FLAG_FILE = _archivo("deploy.flag", "deploy.flag")
ENV_FILE = _archivo("deploy.env", "deploy.env")

API_COMMIT_URL = f"https://api.github.com/repos/{REPO}/commits/{BRANCH}"
TARBALL_URL = f"https://api.github.com/repos/{REPO}/tarball/{BRANCH}"


def log(msg):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_latest_sha():
    req = urllib.request.Request(API_COMMIT_URL, headers={"User-Agent": "suray-auto-deploy"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    return data["sha"]


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"sha": None}


def save_state(sha, requirements_hash):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "sha": sha,
                "requirements_hash": requirements_hash,
                "deployed_at": datetime.now(timezone.utc).isoformat(),
            },
            f,
        )


def load_env_file(path=ENV_FILE):
    """Carga KEY=VALUE de un archivo opcional, sin pisar variables ya definidas."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key.strip(), value)


def acquire_lock():
    """Bloqueo no bloqueante; devuelve el archivo abierto (mantenerlo vivo) o None."""
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        return None
    return lock


def file_hash(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def download_and_extract(tmp_dir):
    tarball_path = os.path.join(tmp_dir, "repo.tar.gz")
    req = urllib.request.Request(TARBALL_URL, headers={"User-Agent": "suray-auto-deploy"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(tarball_path, "wb") as out:
        shutil.copyfileobj(resp, out)

    with tarfile.open(tarball_path) as tar:
        tar.extractall(tmp_dir)

    # El tarball trae una unica carpeta raiz tipo "Roadixito23-suray-web-<sha>"
    entries = [e for e in os.listdir(tmp_dir) if os.path.isdir(os.path.join(tmp_dir, e))]
    return os.path.join(tmp_dir, entries[0])


SKIP_ENTRIES = {"deploy", ".github", ".git"}


def sync_files(src_root, dest_root):
    copied = 0
    for entry in os.listdir(src_root):
        if entry in SKIP_ENTRIES:
            continue
        src = os.path.join(src_root, entry)
        dest = os.path.join(dest_root, entry)
        if os.path.isdir(src):
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dest)
        copied += 1
    return copied


def trigger_restart():
    tmp_dir = os.path.join(DEPLOY_TARGET, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    restart_file = os.path.join(tmp_dir, "restart.txt")
    with open(restart_file, "w") as f:
        f.write(datetime.now(timezone.utc).isoformat())


def run_step(label, args, timeout=600):
    """Ejecuta un comando en DEPLOY_TARGET registrando su salida. True si termino bien."""
    log(f"Ejecutando: {label}")
    try:
        result = subprocess.run(
            args, cwd=DEPLOY_TARGET, capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log(f"ERROR en {label}: {exc}")
        return False
    output = (result.stdout + result.stderr).strip()
    if output:
        log(f"Salida de {label}:\n{output}")
    if result.returncode != 0:
        log(f"ERROR: {label} termino con codigo {result.returncode}.")
        return False
    return True


def database_engine():
    """Motor de BD efectivo segun la configuracion de Django, o None si no se pudo leer."""
    code = (
        "from django.conf import settings; "
        "print('ENGINE=' + settings.DATABASES['default']['ENGINE'])"
    )
    try:
        result = subprocess.run(
            [sys.executable, "manage.py", "shell", "-c", code],
            cwd=DEPLOY_TARGET, capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log(f"ERROR al leer la configuracion de BD: {exc}")
        return None
    for line in result.stdout.splitlines():
        if line.startswith("ENGINE="):
            return line[len("ENGINE="):]
    log(f"ERROR: no se pudo determinar el motor de BD.\n{result.stdout}{result.stderr}")
    return None


def post_sync_steps(previous_requirements_hash, requirements_hash):
    """pip (si cambio), collectstatic y migrate. False si algo fallo."""
    manage = [sys.executable, "manage.py"]

    if requirements_hash != previous_requirements_hash:
        if not run_step(
            "pip install -r requirements.txt",
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        ):
            return False
    else:
        log("requirements.txt sin cambios; se omite pip install.")

    if not run_step("collectstatic", manage + ["collectstatic", "--noinput"]):
        return False

    engine = database_engine()
    if engine is None:
        return False
    if "mysql" not in engine:
        log(
            f"ADVERTENCIA: la configuracion efectiva usa {engine}, no MySQL; se OMITE migrate. "
            "Si corre desde el cron, define DEBUG/DB_* en deploy.env."
        )
        return True
    return run_step("migrate", manage + ["migrate", "--noinput"])


def main():
    lock = acquire_lock()
    if lock is None:
        log("Ya hay un despliegue en curso; se omite esta ejecucion.")
        # Deja el marcador para que el cron por minuto reintente cuando termine.
        open(FLAG_FILE, "a").close()
        return

    load_env_file()
    if os.path.exists(FLAG_FILE):
        os.remove(FLAG_FILE)

    state = load_state()
    latest_sha = get_latest_sha()

    if latest_sha == state.get("sha"):
        log(f"Sin cambios (sha actual {latest_sha[:8]}).")
        return

    log(f"Nuevo commit detectado: {state.get('sha')} -> {latest_sha[:8]}. Desplegando...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        extracted_root = download_and_extract(tmp_dir)
        copied = sync_files(extracted_root, DEPLOY_TARGET)

    requirements_hash = file_hash(os.path.join(DEPLOY_TARGET, "requirements.txt"))
    if not post_sync_steps(state.get("requirements_hash"), requirements_hash):
        log(f"Despliegue FALLIDO (sha {latest_sha[:8]}): no se reinicia la app; se reintentara.")
        sys.exit(1)

    trigger_restart()
    save_state(latest_sha, requirements_hash)
    log(f"Despliegue completo: {copied} elementos sincronizados, sha {latest_sha[:8]}.")


if __name__ == "__main__":
    main()
