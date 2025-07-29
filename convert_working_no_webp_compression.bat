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
set "tempdir=temp_frames_%random%"
mkdir "%tempdir%"

:: Get base filename
for %%F in ("%~n1") do set "basename=%%~F"

:: 1. Convert GIF to WebP frames in temp folder
ffmpeg -vsync vfr -i "%~1" -vf "premultiply=inplace=1,split[v],alphaextract[a],[v][a]alphamerge" -c:v libwebp -lossless 1 "%tempdir%\frame-%%04d.webp"


:: 2. Convert WebP frames to PNG for avifenc compatibility
for /f "delims=" %%f in ('dir /b /on "%tempdir%\frame-*.webp"') do (
    set "webpfile=%tempdir%\%%f"
    set "pngfile=!webpfile:.webp=.png!"
    ffmpeg -i "!webpfile!" -c:v png -compression_level 1 -pred mixed "!pngfile!" >nul 2>&1
    del "!webpfile!"
)

:: 3. Build file list
set files=
for /f "delims=" %%f in ('dir /b /on "%tempdir%\frame-*.png"') do set "files=!files! "%tempdir%\%%f""

:: 4. Convert to AVIF with original frame timing
avifenc --yuv 422 --nclx 1/13/1 -q 20 --qalpha 95 -j 4 --speed 1 -a enable-chroma-deltaq=0 -a enable-qm=0 --timescale 1000 --duration !duration! -o "%basename%.avif" %files%

:: 5. Cleanup
rd /s /q "%tempdir%"