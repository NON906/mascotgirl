@echo off
setlocal

mkdir "%~dp0.installed" > nul 2>&1

if NOT EXIST "%~dp0.installed\.miniconda" (
    powershell -Command "wget -O Miniconda3-latest-Windows-x86_64.exe https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
    start /wait "" Miniconda3-latest-Windows-x86_64.exe /RegisterPython=0 /S /D=%~dp0Miniconda3
    echo f >> "%~dp0.installed\.miniconda"
    del Miniconda3-latest-Windows-x86_64.exe
)

set PATH=%~dp0Miniconda3;%~dp0Miniconda3\condabin;%~dp0Miniconda3\Library\mingw-w64\bin;%~dp0Miniconda3\Library\usr\bin;%~dp0Miniconda3\Library\bin;%~dp0Miniconda3\Scripts;%PATH%

if NOT EXIST "%~dp0.installed\.git" (
    %~dp0Miniconda3\condabin\conda install git wget -y
    git clone --depth 1 --recursive "https://github.com/NON906/mascotgirl.git"
    cd "mascotgirl\talking_head_anime_3_demo"
    %~dp0Miniconda3\condabin\conda env create -n mascotgirl -f environment.yml
    cd "..\.."
    echo f >> "%~dp0.installed\.git"
    install.bat
)

call %~dp0Miniconda3\condabin\conda activate mascotgirl

if NOT EXIST "%~dp0.installed\.others" (
    pip install openai py7zr opencv-python rembg fastapi uvicorn pyngrok qrcode
    echo f >> "%~dp0.installed\.others"
)

python "mascotgirl/install.py"
python "mascotgirl/setting.py"

echo インストール・設定が完了しました。
pause

endlocal