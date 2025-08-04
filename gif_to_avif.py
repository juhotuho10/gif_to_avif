#!/usr/bin/env python3
"""
simple GIF to AVIF Converter that keeps transparency and frame durations intact
the default avifenc settings are lossy, but that can be changed
Requires: avifenc to be callable from command line, PIL (Pillow) for GIF processing
"""

import glob
import os
import shutil
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path
from typing import List

try:
    from PIL import Image

except ImportError:
    print("Error: PIL (Pillow) is required. Install it with: pip install Pillow")
    sys.exit(1)


def run_command(cmd: str | List[str], *, check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    # run a command and return the result
    try:
        result = subprocess.run(cmd, shell=False, check=check, capture_output=capture_output, text=True)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {cmd}")
        print(f"Error: {e.stderr}")
        raise


def check_dependencies():
    # checks that the required tools are available
    tools = ["avifenc"]
    missing: List[str] = []

    for tool in tools:
        if shutil.which(tool) is None:
            missing.append(tool)

    if missing:
        print(f"Error: Missing required tools: {', '.join(missing)}")
        print("Please either:")
        print("1. Install them and ensure they're in your PATH (executable from shell / command line), or")
        print("2. Place the executables in the same folder as this script")
        sys.exit(1)


def handle_single_frame(temp_dir: Path) -> None:
    # duplicate single frame if only one frame exists
    # this keeps the .avif file animated instead of turning it into a static image
    png_files = glob.glob(os.path.join(temp_dir, "*.png"))

    if len(png_files) == 1:
        print("duplicating single frame")
        source = png_files[0]
        duplicate = os.path.join(temp_dir, "duplicate.png")
        shutil.copy2(source, duplicate)


def gif_to_frames(input_path: Path, temp_dir: Path) -> List[int]:
    # get all the gif frames and durations with PIL

    durations_ms: List[int] = []
    frame_index = 0

    with Image.open(input_path) as gif:
        while True:
            try:
                gif.seek(frame_index)
            except EOFError:
                # No more frames
                break

            # get duration or default 40 ms (25 fps)
            duration = gif.info.get("duration", 40)
            durations_ms.append(max(1, duration))

            frame = gif.convert("RGBA")
            output_path = os.path.join(temp_dir, f"{frame_index:05d}.png")
            frame.save(output_path, "PNG")
            frame_index += 1

    print(f"Found {len(durations_ms)} frames with individual durations")
    return durations_ms


def convert_png_to_avif(temp_dir: Path, output_file: Path, durations: List[int], quality: int | None = None) -> None:
    # Convert PNG frames to animated AVIF using avifenc

    png_files = sorted(temp_dir.glob("*.png"))
    if not png_files:
        raise RuntimeError("No PNG files found in temporary directory")
    if len(durations) != len(png_files):
        raise ValueError("Mismatch between frame count and durations")

    # adjust the frame duration based on gif frame durations
    last_dur = None
    file_args = ""
    for dur, f in zip(durations, png_files):
        if dur != last_dur:
            file_args += f"--duration:u {dur} "
            last_dur = dur
        file_args += f"{f} "

    if quality is None:
        # defualty
        quality = 60

    # see: https://man.archlinux.org/man/avifenc.1.en
    # pretty good and tested lossy avifenc settings for good quality / file size
    cmd = (
        "avifenc --yuv 420 --nclx 1/13/1 "
        "--codec aom "  # has extra options
        f"--qcolor {quality} --qalpha 95 "  # configuable 0-100
        "--jobs 8 "  # 8 threads
        "--speed 5 "  # good speed and quality compromise
        "--autotiling "  # seems to get better quality for variety of gifs
        "-a enable-qm=1 "  # smaller file size
        "-a end-usage=vbr "  # usually better quality and smaller file size
        "-a tune=ssim "  # better quality, small increase in file size
        "--depth 8 "  # gifs already limited to 8 bit color
        "--timescale 1000 "
        f'{file_args} "{output_file}"'
    )

    print("Converting PNG frames to AVIF...")
    try:
        run_command(cmd, capture_output=False)
    except:
        print("error creating the animated avif file")
        print("this probably means that the original gif is corrupted / non standard")
        raise


def convert_gif_to_avif(input_path: Path, quality: int | None = None) -> bool:
    # Validate input file
    if not os.path.exists(input_path):
        print(f"Error: File not found - {input_path}")
        return False

    # Get base filename for output
    output_file = input_path.with_suffix(".avif")
    print(f"Converting: {input_path} -> {output_file}")

    try:
        with tempfile.TemporaryDirectory(prefix="Gif2Avif_") as temp_dir:
            temp_path = Path(temp_dir)
            # Extract frame durations
            frame_durations_ms = gif_to_frames(input_path, temp_path)

            # Ensure at least two frames
            if len(frame_durations_ms) == 1:
                handle_single_frame(temp_path)
                first_duration = frame_durations_ms[0]
                frame_durations_ms.append(first_duration)

            # Create animated AVIF
            convert_png_to_avif(temp_path, output_file, frame_durations_ms, quality)

            print(f"Conversion complete: {output_file}")
            return True

    except Exception as e:
        print(f"Error during conversion: {e}")
        return False


def main() -> None:
    check_dependencies()

    if len(sys.argv) != 2 and len(sys.argv) != 4:
        print('Usage: python gif_to_avif.py "gif_file.gif" [--quality N]')
        print("--quality N: (optional, default 60) (int: 0<=N<=100)")
        sys.exit(1)

    # execute in the .py file directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    input_path = Path(sys.argv[1])
    quality = None

    if len(sys.argv) == 4:
        if sys.argv[2] == "--quality":
            try:
                quality = int(sys.argv[3])
                if not (0 <= quality <= 100):
                    raise ValueError()
                elif quality > 90:
                    warnings.warn("Quality above 90 can generate file sizes larger than the original GIF with little visual benefit")
            except ValueError:
                print("Error: --quality must be an integer between 0 and 100")
                sys.exit(1)
        else:
            print(f"Error: Unknown option: {sys.argv[2]}")
            sys.exit(1)

    # Convert a single .gif
    if input_path.is_file():
        if input_path.suffix.lower() != ".gif":
            print("Program currently only supports converting .gif files")
            print("If you want to convert an image instead, it's better to use avifenc for that")
            print(f'Error: Input file must be a .gif file, got: "{input_path.name}"')
            sys.exit(1)

        success = convert_gif_to_avif(input_path, quality)
        if not success:
            sys.exit(1)

    # Convert all .gifs in a directory
    elif input_path.is_dir():
        gif_files = list(input_path.glob("*.gif"))

        if not gif_files:
            print(f"No .gif files found in directory: {input_path}")
            sys.exit(1)

        print(f"Found {len(gif_files)} .gif files in folder '{input_path}'")

        failed_files = []

        for gif_file in gif_files:
            print(f"\nProcessing: {gif_file.name}")
            success = convert_gif_to_avif(gif_file, quality)
            if not success:
                failed_files.append(gif_file.name)

        print("\nBatch conversion complete.")
        if failed_files:
            print("The following files failed to convert:")
            for name in failed_files:
                print(f" - {name}")
            sys.exit(1)
    else:
        print(f"Error: Invalid input path: {input_path}")
        print("the input path must be a .gif file or a folder that has .gif files in it")
        sys.exit(1)


if __name__ == "__main__":
    main()
