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
from statistics import mean
from typing import Dict, List, Optional, Tuple, Union

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


def run_command(cmd: str, *, check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    # run a command and return the result
    try:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=capture_output, text=True)
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
        subprocess.run([tool_name, "-version"], capture_output=True, check=True)
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


def get_frame_durations_pil(input_file: str) -> Optional[List[int]]:
    # get all the gif frame durations with PIL
    try:
        with Image.open(input_file) as gif:
            durations_ms: List[int] = []
            frame_count = gif.n_frames  # type: ignore

            for i in range(frame_count):
                gif.seek(i)
                # Get duration in milliseconds, default to 100ms if not specified
                duration = gif.info.get("duration", 100)
                durations_ms.append(max(1, duration))

            print(f"Found {len(durations_ms)} frames with individual durations")
            return durations_ms

    except Exception as e:
        print(f"Error reading GIF with PIL: {e}")
        return None


def calculate_timing(durations_ms: Optional[List[int]]) -> Tuple[int, List[int]]:
    # balance all the frame timings to be close enough to eachother
    # we do this because avif doesnt support variable frame durations

    if not durations_ms:
        return 40, []  # Default 25fps (40ms per frame)

    print(f"Original frame durations (ms): {durations_ms}")

    # create frame list with durations
    frames = []  # type: List[Dict[str, int]]
    for duration_ms in durations_ms:
        frames.append({"duration": duration_ms, "subdivisions": 1})

    max_iterations = 12  # Safety limit

    for iteration in range(max_iterations):
        min_duration = min(f["duration"] for f in frames)
        max_duration = max(f["duration"] for f in frames)

        # check if all durations are within 10% of each other or close enough
        if (max_duration <= min_duration * 1.1) or abs(max_duration - min_duration) <= 10:
            break

        longest_frames = [i for i, f in enumerate(frames) if f["duration"] == max_duration]

        # split all longest frames in half
        for frame_idx in longest_frames:
            frame = frames[frame_idx]
            frame["duration"] //= 2
            frame["subdivisions"] *= 2

        print(f"Iteration {iteration}: Split {len(longest_frames)} frame(s) to {max_duration // 2} ms")

    # average duration for uniform playback
    avg_duration = round(mean(f["duration"] for f in frames))

    # Build duplication list for original frames
    duplication_counts = [frame["subdivisions"] for frame in frames]

    print(f"Final frame durations (ms): {[f['duration'] for f in frames]}")
    print(f"Average uniform duration: {avg_duration}ms")
    print(f"Frame duplication counts: {duplication_counts}")
    print(f"Total frames after balancing: {sum(duplication_counts)}")

    return avg_duration, duplication_counts


def optimize_gif_alpha(gifsicle_path: str, input_path: str, ouput_path: str) -> None:
    # removing occasional problems with gifs having weird alpha behavior
    # optimizes the gif a little and then resets the gif with unoptimize
    cmd = f'"{gifsicle_path}" {input_path} --optimize=2 --lossy=1 --output {ouput_path}'
    run_command(cmd, capture_output=False)

    cmd = f'"{gifsicle_path}" -b --unoptimize {ouput_path}'
    run_command(cmd, capture_output=False)


def convert_gif_to_png_pil(input_file: str, temp_dir: str) -> None:
    # convert GIF to PNG frames using PIL
    print("Converting GIF to PNG frames...")

    try:
        with Image.open(input_file) as gif:
            frame_count = getattr(gif, "n_frames", 1)

            for i in range(frame_count):
                gif.seek(i)

                frame = gif.convert("RGBA")

                # Save as PNG
                output_path = os.path.join(temp_dir, f"{i + 1:03d}.png")
                frame.save(output_path, "PNG")

            print(f"Extracted {frame_count} frames as PNG")

    except Exception as e:
        print(f"Error extracting frames with PIL: {e}")
        raise


def duplicate_frames_for_timing(temp_dir: str, duplication_counts: List[int]) -> None:
    # Duplicate frames based on timing requirements and remove the original frames
    original_files = sorted(glob.glob(os.path.join(temp_dir, "*.png")))

    assert len(original_files) == len(duplication_counts)

    print("Duplicating frames for balanced timing...")

    # Create duplicated frames
    frame_counter = 0
    for original_file, count in zip(original_files, duplication_counts):
        for _ in range(count):
            new_name = os.path.join(temp_dir, f"_{frame_counter:04d}.png")
            shutil.copy2(original_file, new_name)
            frame_counter += 1

    # Remove original files
    for original_file in original_files:
        os.remove(original_file)

    print(f"Created {frame_counter} balanced frames from {len(original_files)} original frames")


def convert_png_to_avif(avifenc_path: str, temp_dir: str, output_file: Union[str, Path], duration: int) -> None:
    # Convert PNG frames to animated AVIF using avifenc

    # sorted list of PNG files
    png_files = sorted(glob.glob(os.path.join(temp_dir, "*.png")))

    if not png_files:
        raise RuntimeError("No PNG files found in temporary directory")

    # Build file list for avifenc
    file_args = " ".join(f'"{f}"' for f in png_files)

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
        f"--timescale 1000 --duration {duration} "
        f'-o "{output_file}" {file_args}'
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

    # Use a temporary directory
    try:
        with tempfile.TemporaryDirectory(prefix="Gif2Avif_") as temp_dir:
            # Prepare temp input path
            temp_changed_input = os.path.join(temp_dir, f"temp_{input_path.name}")

            # Extract frame durations
            frame_durations_ms = get_frame_durations_pil(input_file)

            # Calculate balanced timing and duplication counts
            if frame_durations_ms:
                uniform_duration, duplication_counts = calculate_timing(frame_durations_ms)
            else:
                # Fallback to uniform 25fps
                uniform_duration = 40
                duplication_counts = None

            print(f"Using balanced frame duration: {uniform_duration}ms")

            # Optimize alpha channel
            optimize_gif_alpha(tool_paths["gifsicle"], input_file, temp_changed_input)

            # Convert GIF to PNG frames
            convert_gif_to_png_pil(temp_changed_input, temp_dir)

            # Duplicate frames if needed
            if duplication_counts and any(count > 1 for count in duplication_counts):
                duplicate_frames_for_timing(temp_dir, duplication_counts)

            # Ensure at least two frames
            handle_single_frame(temp_dir)

            # Create animated AVIF
            convert_png_to_avif(tool_paths["avifenc"], temp_dir, output_file, uniform_duration)

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
