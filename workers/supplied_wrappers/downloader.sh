#!/usr/bin/env bash
set -euo pipefail

# Проверяем наличие параметра
if [ $# -lt 1 ]; then
  echo "Usage: $0 <target_directory>"
  exit 1
fi

TARGET_DIR="$1"

# Массив ссылок на zip-файлы — добавьте свои URL сюда
ZIP_URLS=(
  "https://boinc.berkeley.edu/dl/wrapper_26016_windows_intelx86.zip"
  "https://boinc.berkeley.edu/dl/wrapper_26016_windows_x86_64.zip"
  "https://boinc.berkeley.edu/dl/wrapper_26014_i686-pc-linux-gnu.zip"
  "https://boinc.berkeley.edu/dl/wrapper_26014_x86_64-pc-linux-gnu.zip"
  "https://boinc.berkeley.edu/dl/wrapper_26014_i686-apple-darwin.zip"
  "https://boinc.berkeley.edu/dl/wrapper_26014_x86_64-apple-darwin.zip"
  "https://boinc.berkeley.edu/dl/wrapper_linux_arm64_26018.zip"
)

# Создаём папку, если её нет
mkdir -p "$TARGET_DIR"

# Выбираем инструмент для скачивания
if command -v curl &>/dev/null; then
  DOWNLOADER="curl -L --fail --silent --show-error -o"
elif command -v wget &>/dev/null; then
  DOWNLOADER="wget -qO"
else
  echo "Error: neither curl nor wget found" >&2
  exit 1
fi

for url in "${ZIP_URLS[@]}"; do
  echo "Processing: $url"

  # Получаем имя файла из URL
  filename="${url##*/}"

  # Создаём временный файл
  tmpfile="$(mktemp --suffix=".zip")"

  # Скачиваем
  $DOWNLOADER "$tmpfile" "$url"
  echo "  ↓ Downloaded to $tmpfile"

  # Распаковываем (перезаписываем файлы, если уже есть)
  unzip -o "$tmpfile" -d "$TARGET_DIR"
  echo "  ↳ Unpacked into $TARGET_DIR"

  # Удаляем временный файл
  rm -f "$tmpfile"
done

echo "All archives have been processed."
