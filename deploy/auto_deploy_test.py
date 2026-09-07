"""
Auto-deploy script para test.suray.cl.

Corre periodicamente via Cron Job en el servidor. Revisa el ultimo commit
de la rama 'main' del repo publico en GitHub, y si cambio respecto al
ultimo despliegue, descarga el tarball y sincroniza los archivos
versionados sobre el document root de la app, sin tocar archivos que no
estan en git (db.sqlite3, staticfiles/, .htaccess, tmp/, etc).

Solo usa la libreria estandar de Python (sin requests/GitPython) para no
depender de que esas librerias esten instaladas en el venv de la app.
"""

import json
import os
import shutil
import tarfile
import tempfile
import urllib.request
from datetime import datetime, timezone

REPO = "Roadixito23/suray-web"
BRANCH = "main"
DEPLOY_TARGET = "/home/suraycl1/public_html/test.suray.cl"
STATE_FILE = "/home/suraycl1/deploy_scripts/test_deploy_state.json"
LOG_FILE = "/home/suraycl1/deploy_scripts/test_deploy.log"

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


def save_state(sha):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"sha": sha, "deployed_at": datetime.now(timezone.utc).isoformat()}, f)


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


def main():
    state = load_state()
    latest_sha = get_latest_sha()

    if latest_sha == state.get("sha"):
        log(f"Sin cambios (sha actual {latest_sha[:8]}).")
        return

    log(f"Nuevo commit detectado: {state.get('sha')} -> {latest_sha[:8]}. Desplegando...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        extracted_root = download_and_extract(tmp_dir)
        copied = sync_files(extracted_root, DEPLOY_TARGET)

    trigger_restart()
    save_state(latest_sha)
    log(f"Despliegue completo: {copied} elementos sincronizados, sha {latest_sha[:8]}.")


if __name__ == "__main__":
    main()
