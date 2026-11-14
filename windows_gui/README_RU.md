# Audio8Bit GUI — Windows

Русскоязычная графическая оболочка для [audio8bit](https://github.com/yumiaura/audio8bit).
Работает локально. Поддерживает режимы chords/lead/band/NES, распознавание из вокала
или инструментов, битность, частоту, транспонирование, настройку эффекта эхо,
аранжировки, дизеринга, кеширование Demucs и сохранение в WAV/MP3/OGG/FLAC.

## Запуск

1. Скачать **Audio8BitGUI-windows-x64.zip** на странице [Releases](https://github.com/mirivlad/audio8bit/releases).
2. Распаковать, при необходимости запустить `setup-prereqs.ps1` из PowerShell,
   либо самостоятельно установить Python 3.11 x64 и FFmpeg с ffprobe в PATH.
3. Запустить `Audio8BitGUI.exe` и нажать **«Установить движок»**. Для первой установки
   потребуется интернет и несколько гигабайт свободного места (Demucs/PyTorch/Basic Pitch).
4. Выбрать музыку, настройки и нажать **«Преобразовать в 8-bit»**.
5. Первый запуск движка скачает модель. Индикатор показывает активность, а не проценты.

Движок помещается в `%LOCALAPPDATA%\Audio8BitGUI\engine`; настройки — в
`%LOCALAPPDATA%\Audio8BitGUI\settings.json`.
Оболочка не содержит сторонний движок, модели ИИ, FFmpeg или PyTorch внутри EXE.

## Сборка

GitHub Actions → **Windows GUI** → Run workflow. Результат — artifact ZIP.
При изменениях в `main` workflow также создаёт GUI-релиз `gui-v0.1.0`.

Локальная сборка (Python 3.11 x64):

```powershell
python -m pip install "pyinstaller>=6.12,<7"
python -m PyInstaller --onefile --noconsole --name Audio8BitGUI --clean windows_gui/app.py
```

## Лицензия

Исходники **оболочки** в папке `windows_gui` под MIT — см. `windows_gui/LICENSE`.
Исходный audio8bit под **PolyForm Noncommercial 1.0.0**, а не OSI open-source.
Коммерческое использование движка требует отдельной лицензии автора. Лицензия
в корне репозитория относится к исходному движку.
