@echo off
setlocal enabledelayedexpansion

:: Set paths
set "input_folder=Discord_gifs"
set "output_folder=avif_gifs"
set "converter_script=convert.bat"

:: Verify input folder exists
if not exist "%input_folder%" (
    echo Error: Input folder not found - %input_folder%
    pause
    exit /b
)

:: Create output folder if needed
if not exist "%output_folder%" (
    mkdir "%output_folder%"
)

:: Process all GIF files
for %%g in ("%input_folder%\*.gif") do (
    set "input_file=%%~ng"
    
    :: Check if AVIF already exists
    if not exist "%output_folder%\!input_file!.avif" (
        :: Run conversion script
        call "%converter_script%" "%%g"
        
        :: Move result to output folder
        if exist "!input_file!.avif" (
            move "!input_file!.avif" "%output_folder%\" >nul
            echo Converted to %output_folder%\!input_file!.avif
        ) else (
            echo Failed to convert %%g
        )
    ) 
)

echo All conversions complete!