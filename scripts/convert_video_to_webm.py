#!/usr/bin/env python3
"""
Script to convert MP4 videos to WebM format for QtWebEngine compatibility.

WebM uses open-source codecs (VP9/VP8 for video, Opus for audio) that work
without proprietary codec support in QtWebEngine.

Usage:
    python scripts/convert_video_to_webm.py "docs/videos/selective attention test.mp4"
    
Or convert all MP4 files in a directory:
    python scripts/convert_video_to_webm.py "docs/videos/" --all
"""

import subprocess
import sys
from pathlib import Path


def check_ffmpeg():
    """Check if ffmpeg is available."""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def convert_to_webm(input_path: Path, output_path: Path = None, quality: str = "high"):
    """
    Convert MP4 video to WebM format using ffmpeg.
    
    Args:
        input_path: Path to input MP4 file
        output_path: Path to output WebM file (default: same name with .webm extension)
        quality: Quality preset - "high", "medium", or "low"
    """
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return False
    
    if output_path is None:
        output_path = input_path.with_suffix('.webm')
    
    # Quality presets for VP9
    quality_presets = {
        "high": "-crf 18 -b:v 0",      # High quality, larger file
        "medium": "-crf 28 -b:v 0",    # Medium quality, balanced
        "low": "-crf 35 -b:v 0"        # Lower quality, smaller file
    }
    
    preset = quality_presets.get(quality, quality_presets["medium"])
    
    # FFmpeg command to convert MP4 to WebM
    # -c:v libvpx-vp9: Use VP9 video codec (open source)
    # -c:a libopus: Use Opus audio codec (open source)
    # -crf: Constant Rate Factor (lower = higher quality, 18-35 range)
    # -b:v 0: Use CRF mode (variable bitrate)
    # -row-mt 1: Enable row-based multithreading for faster encoding
    cmd = [
        'ffmpeg',
        '-i', str(input_path),
        '-c:v', 'libvpx-vp9',
        '-c:a', 'libopus',
        '-row-mt', '1',
        *preset.split(),
        '-y',  # Overwrite output file if it exists
        str(output_path)
    ]
    
    print(f"Converting {input_path.name} to WebM format...")
    print(f"Output: {output_path}")
    print(f"Quality: {quality}")
    print(f"Command: {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✓ Successfully converted to: {output_path}")
        print(f"  Original size: {input_path.stat().st_size / (1024*1024):.2f} MB")
        print(f"  WebM size: {output_path.stat().st_size / (1024*1024):.2f} MB")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error during conversion:")
        print(e.stderr)
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    if not check_ffmpeg():
        print("Error: ffmpeg is not installed or not in PATH.")
        print("\nTo install ffmpeg:")
        print("  Windows: Download from https://ffmpeg.org/download.html")
        print("           Or use: choco install ffmpeg")
        print("  macOS:   brew install ffmpeg")
        print("  Linux:   sudo apt-get install ffmpeg  (Debian/Ubuntu)")
        print("           sudo yum install ffmpeg      (RHEL/CentOS)")
        sys.exit(1)
    
    input_arg = Path(sys.argv[1])
    convert_all = '--all' in sys.argv
    
    if input_arg.is_file():
        # Convert single file
        convert_to_webm(input_arg)
    elif input_arg.is_dir() and convert_all:
        # Convert all MP4 files in directory
        mp4_files = list(input_arg.glob('*.mp4'))
        if not mp4_files:
            print(f"No MP4 files found in {input_arg}")
            sys.exit(1)
        
        print(f"Found {len(mp4_files)} MP4 file(s) to convert:")
        for f in mp4_files:
            print(f"  - {f.name}")
        print()
        
        for mp4_file in mp4_files:
            convert_to_webm(mp4_file)
            print()
    else:
        print(f"Error: {input_arg} is not a valid file or directory")
        sys.exit(1)


if __name__ == '__main__':
    main()

