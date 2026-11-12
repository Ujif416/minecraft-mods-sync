#!/usr/bin/env python3
"""
Minecraft Mods Sync Script
Синхронизирует локальную папку с модами с GitHub.

Логика:
- Новые файлы из локальной папки → New mods/
- Файлы в New mods/ старше 7 дней → Serwer mods/ (и удаляются из New mods/)
- Можно принудительно залить всё текущее в Serwer mods/

Требования:
  pip install requests

Настройка:
  1. Создай Personal Access Token на GitHub (repo scope)
  2. Задай переменные окружения или отредактируй CONFIG ниже
  3. Укажи LOCAL_MODS_PATH
"""

import os
import sys
import base64
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("Установи requests: pip install requests")
    sys.exit(1)

# ===================== КОНФИГУРАЦИЯ =====================
CONFIG = {
    "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", "ghp_xxxxxxxxxxxxxxxxxxxx"),  # ← ЗАМЕНИ
    "REPO_OWNER": "Ujif416",
    "REPO_NAME": "minecraft-mods-sync",
    "BRANCH": "main",
    "LOCAL_MODS_PATH": r"C:\Path\To\Your\Mods",  # ← УКАЖИ СВОЙ ПУТЬ
    "NEW_MODS_DIR": "New mods",
    "SERVER_MODS_DIR": "Serwer mods",
    "MAX_AGE_DAYS": 7,
    "MANIFEST_FILE": "mods_manifest.json",  # хранит время загрузки
}

HEADERS = {
    "Authorization": f"token {CONFIG['GITHUB_TOKEN']}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "ModsSyncScript",
}

API_BASE = f"https://api.github.com/repos/{CONFIG['REPO_OWNER']}/{CONFIG['REPO_NAME']}"


def github_request(method, endpoint, data=None):
    url = f"{API_BASE}{endpoint}"
    resp = requests.request(method, url, headers=HEADERS, json=data)
    if resp.status_code >= 400:
        print(f"GitHub API ошибка {resp.status_code}: {resp.text}")
        return None
    return resp.json() if resp.content else {}


def get_file_sha(path):
    """Получить SHA файла, если он существует."""
    data = github_request("GET", f"/contents/{path}?ref={CONFIG['BRANCH']}")
    return data.get("sha") if data else None


def upload_file(local_path: Path, remote_path: str, message: str):
    """Загрузить или обновить файл на GitHub."""
    content = local_path.read_bytes()
    b64 = base64.b64encode(content).decode()

    sha = get_file_sha(remote_path)
    payload = {
        "message": message,
        "content": b64,
        "branch": CONFIG["BRANCH"],
    }
    if sha:
        payload["sha"] = sha

    result = github_request("PUT", f"/contents/{remote_path}", payload)
    if result:
        print(f"  ✓ {remote_path}")
        return True
    return False


def delete_file(remote_path: str, message: str):
    sha = get_file_sha(remote_path)
    if not sha:
        return False
    payload = {
        "message": message,
        "sha": sha,
        "branch": CONFIG["BRANCH"],
    }
    result = github_request("DELETE", f"/contents/{remote_path}", payload)
    if result:
        print(f"  ✗ удалён {remote_path}")
        return True
    return False


def load_manifest():
    """Загрузить или создать манифест с датами добавления."""
    data = github_request("GET", f"/contents/{CONFIG['MANIFEST_FILE']}?ref={CONFIG['BRANCH']}")
    if data and "content" in data:
        content = base64.b64decode(data["content"]).decode()
        return json.loads(content)
    return {}


def save_manifest(manifest: dict):
    content = json.dumps(manifest, indent=2, ensure_ascii=False)
    b64 = base64.b64encode(content.encode()).decode()
    sha = get_file_sha(CONFIG["MANIFEST_FILE"])
    payload = {
        "message": "Update mods manifest",
        "content": b64,
        "branch": CONFIG["BRANCH"],
    }
    if sha:
        payload["sha"] = sha
    github_request("PUT", f"/contents/{CONFIG['MANIFEST_FILE']}", payload)


def list_remote_files(directory: str):
    """Список файлов в папке на GitHub."""
    data = github_request("GET", f"/contents/{directory}?ref={CONFIG['BRANCH']}")
    if not data or not isinstance(data, list):
        return []
    return [item["name"] for item in data if item["type"] == "file"]


def sync_new_files():
    """Залить новые локальные файлы в New mods/."""
    local_dir = Path(CONFIG["LOCAL_MODS_PATH"])
    if not local_dir.exists():
        print(f"Локальная папка не найдена: {local_dir}")
        return

    manifest = load_manifest()
    remote_new = set(list_remote_files(CONFIG["NEW_MODS_DIR"]))
    remote_server = set(list_remote_files(CONFIG["SERVER_MODS_DIR"]))
    already_uploaded = remote_new | remote_server

    print("\n=== Загрузка новых файлов в 'New mods' ===")
    now = datetime.now(timezone.utc).isoformat()

    for file in local_dir.iterdir():
        if not file.is_file() or file.name.startswith("."):
            continue
        if file.name in already_uploaded:
            continue

        remote_path = f"{CONFIG['NEW_MODS_DIR']}/{file.name}"
        if upload_file(file, remote_path, f"Add new mod: {file.name}"):
            manifest[file.name] = {
                "added": now,
                "location": "new",
            }

    save_manifest(manifest)


def promote_old_mods():
    """Переместить моды старше MAX_AGE_DAYS из New mods в Serwer mods."""
    print("\n=== Проверка возраста модов в 'New mods' ===")
    manifest = load_manifest()
    cutoff = datetime.now(timezone.utc) - timedelta(days=CONFIG["MAX_AGE_DAYS"])
    changed = False

    for name, info in list(manifest.items()):
        if info.get("location") != "new":
            continue
        added = datetime.fromisoformat(info["added"])
        if added < cutoff:
            print(f"Перемещаю {name} (добавлен {added.date()}) → Serwer mods")
            # Скачиваем содержимое
            data = github_request("GET", f"/contents/{CONFIG['NEW_MODS_DIR']}/{name}?ref={CONFIG['BRANCH']}")
            if not data or "content" not in data:
                continue
            content = base64.b64decode(data["content"])

            # Загружаем в Serwer mods
            b64 = base64.b64encode(content).decode()
            server_path = f"{CONFIG['SERVER_MODS_DIR']}/{name}"
            sha = get_file_sha(server_path)
            payload = {
                "message": f"Promote {name} to server mods (aged {CONFIG['MAX_AGE_DAYS']} days)",
                "content": b64,
                "branch": CONFIG["BRANCH"],
            }
            if sha:
                payload["sha"] = sha
            if github_request("PUT", f"/contents/{server_path}", payload):
                # Удаляем из New mods
                delete_file(f"{CONFIG['NEW_MODS_DIR']}/{name}", f"Remove {name} from New mods after promotion")
                info["location"] = "server"
                info["promoted"] = datetime.now(timezone.utc).isoformat()
                changed = True

    if changed:
        save_manifest(manifest)


def force_upload_to_server():
    """Принудительно залить все локальные файлы в Serwer mods (первый запуск)."""
    local_dir = Path(CONFIG["LOCAL_MODS_PATH"])
    if not local_dir.exists():
        print(f"Локальная папка не найдена: {local_dir}")
        return

    print("\n=== Принудительная загрузка в 'Serwer mods' ===")
    for file in local_dir.iterdir():
        if not file.is_file() or file.name.startswith("."):
            continue
        remote_path = f"{CONFIG['SERVER_MODS_DIR']}/{file.name}"
        upload_file(file, remote_path, f"Initial upload to server mods: {file.name}")


def ensure_folders():
    """Создать папки, если их нет (через .gitkeep)."""
    for folder in [CONFIG["NEW_MODS_DIR"], CONFIG["SERVER_MODS_DIR"]]:
        gitkeep = f"{folder}/.gitkeep"
        if not get_file_sha(gitkeep):
            payload = {
                "message": f"Create {folder} folder",
                "content": base64.b64encode(b"").decode(),
                "branch": CONFIG["BRANCH"],
            }
            github_request("PUT", f"/contents/{gitkeep}", payload)
            print(f"Создана папка: {folder}/")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--init":
        ensure_folders()
        force_upload_to_server()
        return

    ensure_folders()
    sync_new_files()
    promote_old_mods()
    print("\nГотово.")


if __name__ == "__main__":
    main()
