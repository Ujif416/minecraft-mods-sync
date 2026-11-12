# Minecraft Mods Sync

Автоматическая синхронизация локальной папки с модами и GitHub.

## Папки на GitHub

- `New mods/` — сюда попадают новые моды
- `Serwer mods/` — стабильные серверные моды (после 7 дней)

## Быстрый старт

1. Склонируй репозиторий или скачай `sync_mods.py`
2. Установи зависимости:
   ```bash
   pip install requests
   ```
3. Создай GitHub Personal Access Token (scope: `repo`)
4. Открой `sync_mods.py` и измени:
   - `GITHUB_TOKEN`
   - `LOCAL_MODS_PATH` — путь к твоей папке с модами
5. Первый запуск (залить всё текущее в Serwer mods + создать папки):
   ```bash
   python sync_mods.py --init
   ```
6. Обычный запуск (новые → New mods, старые → Serwer mods):
   ```bash
   python sync_mods.py
   ```

## Автоматизация

Можно поставить в планировщик (Windows Task Scheduler / cron) и запускать раз в день.

## Codex

Можешь дать Codex задачу:
> «Запусти sync_mods.py, укажи локальную папку C:\Minecraft\mods и токен ...»

Скрипт сам всё сделает.
