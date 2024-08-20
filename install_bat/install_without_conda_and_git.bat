@echo off

setlocal

mkdir "%~dp0.installed" > nul 2>&1

if NOT EXIST "%~dp0.installed\.wget" (
    mkdir "%~dp0bin\wget" > nul 2>&1
    powershell -Command "wget -O %~dp0bin\wget\wget.exe https://eternallybored.org/misc/wget/1.21.4/64/wget.exe"
    echo f >> "%~dp0.installed\.wget"
)

set PATH=%~dp0bin\wget;%PATH%

if NOT EXIST "%~dp0.installed\.environment" (
    git clone --depth 1 --recursive "https://github.com/NON906/mascotgirl.git"
    cd "mascotgirl"
    conda env create -n mascotgirl -f environment.yml
    cd %~dp0
    echo f >> "%~dp0.installed\.environment"
    install_without_conda_and_git.bat
)

cd "mascotgirl"
git pull
cd %~dp0

call conda activate mascotgirl

python "mascotgirl/install.py"
python "mascotgirl/setting.py"

echo インストール・設定が完了しました。
pause

endlocal