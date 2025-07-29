@echo off
setlocal enabledelayedexpansion

:: Check input file
if not exist "%~1" (
    echo Error: File not found - %~1
    echo Usage: %~nx0 "yourfile.gif"
    pause
    exit /b
)

:: Extract average frame rate as fraction
set "num=25"
set "den=1"
for /f "tokens=1,2 delims=/" %%a in (
    'ffprobe -v error -select_streams v -of default^=noprint_wrappers^=1:nokey^=1 -show_entries stream^=avg_frame_rate "%~1" 2^>^&1'
) do (
    set "num=%%a"
    set "den=%%b"
)
if not defined den set "den=1"
if "!num!"=="0" if "!den!"=="0" set "num=25" & set "den=1"

:: Calculate frame duration in milliseconds (timescale=1000)
set /a "duration=(1000*den)/num"
if !duration! lss 1 set "duration=1"

:: Create unique temp folder
set "tempdir=__tmp"
mkdir "%tempdir%"


:: Get base filename
for %%F in ("%~n1") do set "basename=%%~F"


:: 1. Convert GIF to *lossy* JPEG XL frames (alpha preserved)
ffmpeg -vsync vfr ^
  -color_trc iec61966_2_1 -color_primaries bt709 ^
  -i "%~1" ^
  -vf "format=rgba" ^
  -c:v jpegxl ^
    -distance 0.6 ^
    -effort 9 ^
    -modular 0 ^
  "%tempdir%\%%03d.jxl"

:: 2. Convert JPEG XL frames to PNG
for /f "delims=" %%f in ('dir /b /on "%tempdir%\*.jxl"') do (
    set "jxlfile=%tempdir%\%%f"
    set "pngfile=!jxlfile:.jxl=.png!"
    ffmpeg -i "!jxlfile!" -c:v png -compression_level 3 "!pngfile!" >nul 2>&1
    del "!jxlfile!"
)

:: 3. Build file list
set files=
for /f "delims=" %%f in ('dir /b /on "%tempdir%\*.png"') do set "files=!files! "%tempdir%\%%f""

:: 4. Convert to AVIF with original frame timing
avifenc --yuv 422 --nclx 1/13/1 -q 40 --qalpha 95 -j 8 --speed 1 -a enable-chroma-deltaq=0 -a enable-qm=0 --timescale 1000 --duration !duration! -o "%basename%.avif" %files%


:: 5. Cleanup
rd /s /q "%tempdir%"