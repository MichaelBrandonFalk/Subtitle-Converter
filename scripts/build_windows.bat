@echo off
setlocal

python -m pip install --upgrade pip
pip install pyinstaller
pyinstaller --noconfirm --windowed --onefile --name Subtitle-Converter --paths src app.py

echo Windows build created in dist\Subtitle-Converter.exe
