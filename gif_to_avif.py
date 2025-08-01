#!/usr/bin/env python3
"""
GIF to AVIF Converter
Converts GIF files to AVIF format while preserving animation timing and quality.
Requires: ffmpeg, ffprobe, and avifenc to be installed and available in PATH.
"""

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path


def handle_single_frame(temp_dir):
    """Duplicate single frame if only one frame exists."""
    png_files = glob.glob(os.path.join(temp_dir, "*.png"))

    if len(png_files) == 1:
        print("Duplicating single frame for AVIF animation...")
        source = png_files[0]
        duplicate = os.path.join(temp_dir, "duplicate.png")
        shutil.copy2(source, duplicate)


def run_command(cmd, check=True, capture_output=True):
    """Run a command and return the result."""
    try:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=capture_output, text=True)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {cmd}")
        print(f"Error: {e.stderr}")
        raise


def find_tool(tool_name):
    """Find tool in local folder first, then in PATH."""
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


def check_dependencies():
    """Check if required tools are available in local folder or PATH."""
    tools = ["ffmpeg", "ffprobe", "avifenc"]
    tool_paths = {}
    missing = []

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


def get_frame_durations(ffprobe_path, input_file):
    """Extract individual frame durations from GIF using ffprobe."""
    cmd = f'"{ffprobe_path}" -v error -select_streams v:0 -show_entries packet=duration_time -of csv=p=0 "{input_file}"'

    try:
        result = run_command(cmd)
        durations = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    duration = float(line.strip())
                    durations.append(duration)
                except ValueError:
                    continue

        if not durations:
            print("Warning: Could not extract frame durations, using uniform timing")
            return None

        print(f"Found {len(durations)} frames with individual durations")
        return durations

    except subprocess.CalledProcessError:
        print("Warning: Could not extract frame durations, using uniform timing")
        return None


def calculate_timing(durations):
    """Balance frame durations by subdividing longest frames until within 10% tolerance."""
    if not durations:
        return 40, []  # Default 25fps (40ms per frame)

    print(f"Original frame durations (ms): {durations}")

    # Convert to milliseconds and create frame list with durations
    frames = []
    for duration in durations:
        duration_ms = max(1, round(duration * 1000))  # min 1 millisecond
        frames.append({"duration": duration_ms, "subdivisions": 1})

    iteration = 0
    max_iterations = 10  # Safety limit

    for iteration in range(max_iterations):
        # Find min and max durations
        min_duration = min(f["duration"] for f in frames)
        max_duration = max(f["duration"] for f in frames)

        # Check if all durations are within 10% of each other or close enough
        if (max_duration <= min_duration * 1.1) or abs(max_duration - min_duration) <= 10:
            break

        longest_frames = [i for i, f in enumerate(frames) if f["duration"] == max_duration]

        # Split all longest frames in half
        split_count = 0
        for frame_idx in longest_frames:
            frame = frames[frame_idx]
            frame["duration"] //= 2
            frame["subdivisions"] *= 2
            split_count += 1

        print(f"Iteration {iteration}: Split {split_count} frame(s) to {max_duration // 2} ms")

    # Calculate average duration for uniform playback
    avg_duration = round(sum(f["duration"] for f in frames) / len(frames))

    # Build duplication list for original frames
    duplication_counts = [frame["subdivisions"] for frame in frames]

    print(f"Final frame durations (ms): {[f['duration'] for f in frames]}")
    print(f"Average uniform duration: {avg_duration}ms")
    print(f"Frame duplication counts: {duplication_counts}")
    print(f"Total frames after balancing: {sum(duplication_counts)}")

    return avg_duration, duplication_counts


def convert_gif_to_png(ffmpeg_path, input_file, temp_dir):
    """Convert GIF to PNG frames using ffmpeg."""
    output_pattern = os.path.join(temp_dir, "%03d.png")

    cmd = f'"{ffmpeg_path}" -vsync vfr -i "{input_file}" "{output_pattern}"'

    print("Converting GIF to PNG frames...")
    run_command(cmd, capture_output=False)


def duplicate_frames_for_timing(temp_dir, duplication_counts):
    """Duplicate frames based on timing requirements and remove the original frames"""
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

    # Remove original numbered files
    for original_file in original_files:
        os.remove(original_file)

    print(f"Created {frame_counter - 1} balanced frames from {len(original_files)} original frames")


def convert_png_to_avif(avifenc_path, temp_dir, output_file, duration):
    """Convert PNG frames to AVIF using avifenc."""
    # Get sorted list of PNG files
    png_files = sorted(glob.glob(os.path.join(temp_dir, "*.png")))

    if not png_files:
        raise RuntimeError("No PNG files found in temporary directory")

    # Build file list for avifenc
    file_args = " ".join(png_files)

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


def convert_gif_to_avif(input_file, tool_paths):
    """Main conversion function."""
    # Validate input file
    if not os.path.exists(input_file):
        print(f"Error: File not found - {input_file}")
        return False

    # Get base filename for output
    input_path = Path(input_file)
    script_dir = Path(__file__).parent
    output_file = script_dir / f"{input_path.stem}.avif"

    print(f"Converting: {input_file} -> {output_file}")

    # Create temporary directory
    temp_dir = "__tmp"

    try:
        # Clean and create temp directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)

        try:
            # Extract individual frame durations
            frame_durations = get_frame_durations(tool_paths["ffprobe"], input_file)

            # Calculate balanced timing and duplication counts
            if frame_durations:
                uniform_duration, duplication_counts = calculate_timing(frame_durations)
            else:
                # Fallback to uniform 25fps
                uniform_duration = 40
                duplication_counts = None

            print(f"Using balanced frame duration: {uniform_duration}ms")

            # Convert GIF to PNG frames
            convert_gif_to_png(tool_paths["ffmpeg"], input_file, temp_dir)

            # Duplicate frames for balanced timing if needed
            if duplication_counts and any(count > 1 for count in duplication_counts):
                duplicate_frames_for_timing(temp_dir, duplication_counts)

            # Duplicate if there is only single frame
            handle_single_frame(temp_dir)

            # Convert PNG frames to animated AVIF
            convert_png_to_avif(tool_paths["avifenc"], temp_dir, output_file, uniform_duration)

            print(f"Conversion complete: {output_file}")
            return True

        except Exception as e:
            print(f"Error during conversion: {e}")
            return False

    finally:
        # Always clean up temp directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def main():
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
