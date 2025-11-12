# Video Codec Support Guide for QtWebEngine

## The Problem

QtWebEngine (used by PySide6) **does not include proprietary codecs** (H.264, MP3) by default due to licensing restrictions. This means:

- **MP4 videos with H.264 codec** may not play
- **MP3 audio** may not work
- Videos may appear to load but never actually play

## Solutions

### Solution 1: Convert to WebM Format (Recommended) ✅

**WebM uses open-source codecs** that work without proprietary codec support:
- **VP9 or VP8** for video (open source)
- **Opus** for audio (open source)

#### Quick Conversion

Use the provided conversion script:

```bash
# Convert single video
python scripts/convert_video_to_webm.py "docs/videos/selective attention test.mp4"

# Convert all MP4 files in a directory
python scripts/convert_video_to_webm.py "docs/videos/" --all
```

#### Manual Conversion with FFmpeg

If you prefer to convert manually:

```bash
# High quality (larger file)
ffmpeg -i "selective attention test.mp4" -c:v libvpx-vp9 -c:a libopus -crf 18 -b:v 0 "selective attention test.webm"

# Medium quality (balanced)
ffmpeg -i "selective attention test.mp4" -c:v libvpx-vp9 -c:a libopus -crf 28 -b:v 0 "selective attention test.webm"

# Lower quality (smaller file)
ffmpeg -i "selective attention test.mp4" -c:v libvpx-vp9 -c:a libopus -crf 35 -b:v 0 "selective attention test.webm"
```

**Install FFmpeg:**
- **Windows**: Download from https://ffmpeg.org/download.html or use `choco install ffmpeg`
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt-get install ffmpeg` (Debian/Ubuntu) or `sudo yum install ffmpeg` (RHEL/CentOS)

#### Update HTML

The HTML file (`BridgeExampleVideo.html`) has been updated to try WebM first, then fall back to MP4:

```html
<video id="attentionVideo" controls playsinline preload="auto">
  <!-- Try WebM first (works without proprietary codecs) -->
  <source src="../videos/selective attention test.webm" type="video/webm">
  <!-- Fallback to MP4 (requires H.264 codec support) -->
  <source src="../videos/selective attention test.mp4" type="video/mp4">
  Your browser does not support the video tag.
</video>
```

### Solution 2: Build QtWebEngine with Proprietary Codecs (Advanced) ⚠️

**Warning**: This is complex and may require licensing considerations.

#### Steps to Build PySide6 with Codec Support

1. **Get Qt Source Code:**
   ```bash
   git clone https://code.qt.io/qt/qt5.git
   cd qt5
   ```

2. **Configure Qt with Proprietary Codecs:**
   ```bash
   ./configure -webengine-proprietary-codecs
   ```

3. **Build Qt:**
   ```bash
   cmake --build . --parallel
   ```

4. **Rebuild PySide6** against the custom Qt build

**Note**: This is a complex process and may take hours. You also need to consider licensing requirements for H.264/MP3 distribution.

#### Check if Your QtWebEngine Has Codec Support

You can test if your current QtWebEngine installation supports H.264 by checking the browser's codec support. However, the easiest way is to try playing an MP4 video - if it doesn't work, you likely don't have codec support.

## Recommendation

**Use Solution 1 (WebM conversion)** - it's:
- ✅ Quick and easy
- ✅ No licensing concerns
- ✅ Works immediately
- ✅ Open source codecs
- ✅ Good quality and file size

WebM is widely supported and is the standard format for web video when you want to avoid proprietary codecs.

## Current Status

The `BridgeExampleVideo.html` file has been updated to:
1. Try WebM format first (works without codecs)
2. Fall back to MP4 if WebM is not available
3. Show standard video controls for manual playback

After converting your video to WebM, it should play correctly in QtWebEngine.

