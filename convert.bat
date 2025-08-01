@echo off
setlocal enabledelayedexpansion


:: ================================== SETUP CODE ================================

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
if exist "%tempdir%" rd /s /q "%tempdir%"
mkdir "%tempdir%"

:: Get base filename
for %%F in ("%~n1") do set "basename=%%~F"

:: ================================== GIF -> PNG ================================

:: 1. Convert GIF to png
ffmpeg -vsync vfr ^
  -i "%~1" ^
  "%tempdir%\%%03d.png"

:: ================================== DUPLICATE FRAME IF WE ONLY HAVE 1 ================================


set /a file_count=0
for /f %%f in ('dir /b /a-d "%tempdir%\*.png" 2^>nul ^| find /c /v ""') do set /a file_count=%%f

if !file_count! equ 1 (
    set "frame1="
    for %%f in ("%tempdir%\*.png") do (
        if not defined frame1 set "frame1=%%f"
    )
    echo Duplicating single frame for AVIF animation...
    copy /y "!frame1!" "%tempdir%\duplicate.png" >nul
)

:: ================================== PNG -> AVIF ================================
:: 3. Build file list
set files=
for /f "delims=" %%f in ('dir /b /on "%tempdir%\*.png"') do set "files=!files! "%tempdir%\%%f""
echo %files%
:: 4. Convert to AVIF with original frame timing
avifenc --yuv 420 --nclx 1/13/1 ^
--codec aom ^
--qcolor 30 --qalpha 95 ^
--jobs 8 --speed 2 ^
--autotiling ^
-a aq-mode=3 ^
-a enable-qm=1 ^
-a enable-chroma-deltaq=1 ^
-a enable-tpl-model=1 ^
-a end-usage=vbr ^
-a tune=ssim ^
--timescale 1000 --duration !duration! -o "%basename%.avif" %files%


:: 5. Cleanup
rd /s /q "%tempdir%"