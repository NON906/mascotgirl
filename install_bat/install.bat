@echo off
setlocal

mkdir "%~dp0.installed" > nul 2>&1

if NOT EXIST "%~dp0.installed\.miniconda" (
    mkdir "%~dp0bin" > nul 2>&1
    powershell -Command "wget -O Miniconda3-latest-Windows-x86_64.exe https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
    start /wait "" Miniconda3-latest-Windows-x86_64.exe /RegisterPython=0 /S /D=%~dp0bin\Miniconda3
    echo f >> "%~dp0.installed\.miniconda"
    del Miniconda3-latest-Windows-x86_64.exe
)

if NOT EXIST "%~dp0.installed\.wget" (
    mkdir "%~dp0bin\wget" > nul 2>&1
    powershell -Command "wget -O %~dp0bin\wget\wget.exe https://eternallybored.org/misc/wget/1.21.4/64/wget.exe"
    echo f >> "%~dp0.installed\.wget"
)

set PATH=%~dp0bin\wget;%~dp0bin\Miniconda3;%~dp0bin\Miniconda3\condabin;%~dp0bin\Miniconda3\Library\mingw-w64\bin;%~dp0bin\Miniconda3\Library\usr\bin;%~dp0bin\Miniconda3\Library\bin;%~dp0bin\Miniconda3\Scripts

if NOT EXIST "%~dp0.installed\.git" (
    %~dp0bin\Miniconda3\condabin\conda install git -y
    git clone --depth 1 --recursive "https://github.com/NON906/mascotgirl.git"
    cd "mascotgirl\talking_head_anime_3_demo"
    %~dp0bin\Miniconda3\condabin\conda env create -n mascotgirl -f environment.yml
    cd "..\.."
    echo f >> "%~dp0.installed\.git"
    install.bat
)

call %~dp0bin\Miniconda3\condabin\conda activate mascotgirl

if NOT EXIST "%~dp0.installed\.others" (
    pip install openai py7zr opencv-python rembg fastapi uvicorn pyngrok qrcode
    echo f >> "%~dp0.installed\.others"
)

python "mascotgirl/install.py"
python "mascotgirl/setting.py"

echo インストール・設定が完了しました。
pause

endlocal