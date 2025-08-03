#!/usr/bin/env python3
"""
GIF to AVIF Converter
Requires: avifenc to be callable from command line, PIL (Pillow) for GIF processing
"""

import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Union

try:
    from PIL import Image

except ImportError:
    print("Error: PIL (Pillow) is required. Install it with: pip install Pillow")
    sys.exit(1)


def handle_single_frame(temp_dir: str) -> None:
    # duplicate single frame if only one frame exists
    png_files = glob.glob(os.path.join(temp_dir, "*.png"))

    if len(png_files) == 1:
        print("duplicating single frame")
        source = png_files[0]
        duplicate = os.path.join(temp_dir, "duplicate.png")
        shutil.copy2(source, duplicate)


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
    # checks that the required tools are available and returns their call path
    tools = ["avifenc"]
    missing: List[str] = []

    for tool_name in tools:
        try:
            run_command(f"{tool_name} --version", check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append(tool_name)

    if missing:
        print(f"Error: Missing required tools: {', '.join(missing)}")
        print("Please either:")
        print("1. Install them and ensure they're in your PATH, or")
        print("2. Place the executables in the same folder as this script")
        sys.exit(1)


def gif_to_frames(input_file: str, temp_dir: str) -> List[int]:
    # get all the gif frame durations with PIL

    with Image.open(input_file) as gif:
        durations_ms: List[int] = []
        frame_count = gif.n_frames  # type: ignore

        for i in range(frame_count):
            gif.seek(i)
            # get duration or default 40 ms (25 fps)
            duration = gif.info.get("duration", 40)
            durations_ms.append(max(1, duration))
            frame = gif.convert("RGBA")

            output_path = os.path.join(temp_dir, f"{i + 1:03d}.png")
            frame.save(output_path, "PNG")

        print(f"Found {len(durations_ms)} frames with individual durations")
        return durations_ms


def convert_png_to_avif(temp_dir: str, output_file: Union[str, Path], durations: List[int]) -> None:
    # Convert PNG frames to animated AVIF using avifenc

    # sorted list of PNG files
    png_files = sorted(glob.glob(os.path.join(temp_dir, "*.png")))

    if not png_files:
        raise RuntimeError("No PNG files found in temporary directory")

    assert len(durations) == len(png_files)

    last_dur = None
    file_args = ""
    for dur, f in zip(durations, png_files):
        if dur != last_dur:
            file_args += f"--duration:u {dur} "
            last_dur = dur
        file_args += f"{f} "

    cmd = (
        "avifenc --yuv 420 --nclx 1/13/1 "
        "--codec aom "  # has extra options
        "--qcolor 40 --qalpha 95 "  # configuable 0-100
        "--jobs 8 "  # 8 threads
        "--speed 2 "  # good speed and quality compromise
        "--autotiling "  # seems to get better quality for variety of gifs
        "-a aq-mode=3 "  # better quality
        "-a enable-qm=1 "  # smaller file size
        "-a enable-chroma-deltaq=1 "  # little better on
        "-a end-usage=vbr "  # better quality, small increase in file size
        "-a tune=ssim "  # better quality, small increase in file size
        "-a sharpness=1 "  # seems to give better quality with small size penalty
        "--range limited "  # gifs are already limited in YUV range
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


def convert_gif_to_avif(input_file: str) -> bool:
    # Validate input file
    if not os.path.exists(input_file):
        print(f"Error: File not found - {input_file}")
        return False

    # Get base filename for output
    input_path = Path(input_file)
    script_dir = Path(__file__).parent
    output_file = script_dir / f"{input_path.stem}.avif"
    input_path = Path(input_file)

    print(f"Converting: {input_file} -> {output_file}")

    try:
        with tempfile.TemporaryDirectory(prefix="Gif2Avif_") as temp_dir:
            # Extract frame durations
            frame_durations_ms = gif_to_frames(input_file, temp_dir)

            # Ensure at least two frames
            if len(frame_durations_ms) == 1:
                handle_single_frame(temp_dir)
                first_duration = frame_durations_ms[0]
                frame_durations_ms.append(first_duration)

            # Create animated AVIF
            convert_png_to_avif(temp_dir, output_file, frame_durations_ms)

            print(f"Conversion complete: {output_file}")
            return True

    except Exception as e:
        print(f"Error during conversion: {e}")
        return False


def main() -> None:
    if len(sys.argv) != 2:
        print('Usage: python gif_to_avif.py "gif_file.gif"')
        sys.exit(1)

    input_file = sys.argv[1]

    check_dependencies()

    success = convert_gif_to_avif(input_file)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
