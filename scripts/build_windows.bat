@echo off
setlocal

python -m pip install --upgrade pip
pip install pyinstaller
pyinstaller --noconfirm --windowed --onefile --name "Subtitle Converter" --paths src app.py

powershell -Command "Compress-Archive -Path 'dist/Subtitle Converter.exe' -DestinationPath 'dist/Subtitle-Converter-windows-x64.zip' -Force"
echo Windows build created in dist\Subtitle-Converter-windows-x64.zip
