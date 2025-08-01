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
from typing import Dict, List, Optional, Union

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


def find_tool(tool_name: str) -> Optional[str]:
    # find tool and call path from name
    script_dir = Path(__file__).parent

    # Check local folder first (with .exe extension on Windows)
    local_paths = [script_dir / tool_name, script_dir / f"{tool_name}.exe"]

    for local_path in local_paths:
        if local_path.exists() and local_path.is_file():
            print(f"Using local {tool_name}: {local_path}")
            return str(local_path)

    # Check if tool is in PATH
    try:
        run_command([tool_name, "-version"], check=True, capture_output=True)
        print(f"Using system {tool_name} from PATH")
        return tool_name
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def check_dependencies() -> Dict[str, str]:
    # checks that the required tools are available and returns their call path
    tools = ["avifenc", "gifsicle"]
    tool_paths: Dict[str, str] = {}
    missing: List[str] = []

    for tool in tools:
        tool_path = find_tool(tool)
        if tool_path:
            tool_paths[tool] = tool_path
        else:
            missing.append(tool)

    if missing:
        print(f"Error: Missing required tools: {', '.join(missing)}")
        print("Please either:")
        print("1. Install them and ensure they're in your PATH, or")
        print("2. Place the executables in the same folder as this script")
        sys.exit(1)

    return tool_paths


def gif_to_frames(input_file: str, temp_dir: str) -> List[int]:
    # get all the gif frame durations with PIL

    with Image.open(input_file) as gif:
        durations_ms: List[int] = []
        frame_count = gif.n_frames  # type: ignore

        for i in range(frame_count):
            gif.seek(i)
            # Get duration in milliseconds, default to 100ms if not specified
            duration = gif.info.get("duration", 100)
            durations_ms.append(max(1, duration))
            frame = gif.convert("RGBA")

            output_path = os.path.join(temp_dir, f"{i + 1:03d}.png")
            frame.save(output_path, "PNG")

        print(f"Found {len(durations_ms)} frames with individual durations")
        return durations_ms


def optimize_gif_alpha(gifsicle_path: str, input_path: str, ouput_path: str) -> None:
    # removing occasional problems with gifs having weird alpha behavior
    # optimizes the gif a little and then resets the gif with unoptimize
    png_files = glob.glob(os.path.join(input_path, "*.png"))

    if len(png_files) > 1:
        # optimization fails if we only have 1 file
        cmd = f'"{gifsicle_path}" {input_path} --optimize=2 --lossy=1 --output {ouput_path}'
        run_command(cmd, capture_output=False)

        cmd = f'"{gifsicle_path}" -b --unoptimize {ouput_path}'
        run_command(cmd, capture_output=False)
    else:
        # Fallback: copy GIF from input to output
        shutil.copy(input_path, ouput_path)


def convert_png_to_avif(avifenc_path: str, temp_dir: str, output_file: Union[str, Path], durations: List[int]) -> None:
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
        f'"{avifenc_path}" --yuv 420 --nclx 1/13/1 '
        f"--codec aom "
        f"--qcolor 30 --qalpha 95 "
        f"--jobs 8 --speed 2 "
        f"--autotiling "
        f"-a aq-mode=3 "
        f"-a enable-qm=1 "
        f"-a enable-chroma-deltaq=1 "
        f"-a enable-tpl-model=1 "
        f"-a end-usage=vbr "
        f"-a tune=ssim "
        f"--timescale 1000 "
        f'{file_args} "{output_file}"'
    )

    print("Converting PNG frames to AVIF...")
    run_command(cmd, capture_output=False)


def convert_gif_to_avif(input_file: str, tool_paths: Dict[str, str]) -> bool:
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
            # Prepare temp input path
            changed_input_file = os.path.join(temp_dir, f"temp_{input_path.name}")

            # Optimize alpha channel
            optimize_gif_alpha(tool_paths["gifsicle"], input_file, changed_input_file)

            # Extract frame durations
            frame_durations_ms = gif_to_frames(changed_input_file, temp_dir)

            # Ensure at least two frames
            if len(frame_durations_ms) == 1:
                handle_single_frame(temp_dir)
                first_duration = frame_durations_ms[0]
                frame_durations_ms.append(first_duration)

            # Create animated AVIF
            convert_png_to_avif(tool_paths["avifenc"], temp_dir, output_file, frame_durations_ms)

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

    tool_paths = check_dependencies()

    success = convert_gif_to_avif(input_file, tool_paths)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
