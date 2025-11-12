# Screen Recording Implementation Requirements

## Overview
Screen recording is a **core missing feature** that needs to be implemented. According to the TODO and project documentation, this is a high-priority item.

## Requirements from TODO.md

### Section 3: Screen Recording System

**Status:** ❌ **NOT IMPLEMENTED** (0%)

Required features:
1. **Cross-platform screen recording**
   - Windows: Use `pyautogui` + `opencv-python` or `mss`
   - Linux: Use `mss` or `ffmpeg-python`
   - macOS: Use `mss` or `avfoundation`

2. **Recording controls**
   - Start recording
   - Stop recording
   - Pause recording

3. **Recording quality settings**
   - Resolution (configurable, default: fullscreen)
   - FPS (configurable, default: 30)
   - Codec selection
   - Quality levels (low, medium, high)

4. **Recording preview window**
   - Real-time preview of what's being recorded

5. **Fullscreen application recording**
   - Handle recording of fullscreen applications

## Configuration Model

The `ScreenRecordingConfig` class already exists in `models.py`:

```python
@dataclass
class ScreenRecordingConfig:
    recording_quality: str = "high"  # low, medium, high
    fps: int = 30
    resolution: Optional[tuple[int, int]] = None  # None for fullscreen
    include_audio: bool = False
    mouse_tracking: bool = True
```

## Integration Points

### 1. Session Recording
- Screen recording should be integrated into `EmbeddedWebpageSessionWindow` (or a new `ScreenRecordingSessionWindow`)
- Recording should start when session starts
- Recording should stop when session ends
- Video file should be saved to: `{project_path}/tracking_data/{session_id}/screen_recording.mp4` (or similar)

### 2. Session Review & Playback
- **Current Status:** The `SessionReviewWindow` has a placeholder: "Video/Webpage Playback\n(Screen recording not yet implemented)"
- **Required:** Replace placeholder with actual video player that:
  - Loads the recorded screen video
  - Plays video synchronized with LSL data timeline
  - Shows mouse tracking overlays on top of the video
  - Supports play/pause/seek/speed controls (already implemented)

### 3. Data Synchronization
- Screen recording timestamps must be synchronized with:
  - LSL stream timestamps
  - Mouse tracking timestamps
  - Bridge event timestamps
- All data should share the same timeline reference point (session start time)

## Implementation Suggestions

### Recommended Approach

1. **Use `mss` library** (cross-platform, simple API)
   - Install: `pip install mss`
   - Works on Windows, Linux, macOS
   - Can capture screen regions or fullscreen
   - Returns numpy arrays (easy to convert to video)

2. **Use `opencv-python` for video encoding**
   - Install: `pip install opencv-python`
   - Can encode frames to MP4/H.264
   - Good performance
   - Cross-platform

3. **Alternative: Use `ffmpeg-python`**
   - More control over encoding
   - Better codec support
   - Can handle audio if needed

### Implementation Structure

```python
class ScreenRecorder:
    """Records screen during a session."""
    
    def __init__(self, session_id: str, config: ScreenRecordingConfig):
        self.session_id = session_id
        self.config = config
        self.is_recording = False
        self.frames = []
        self.start_time = None
        
    def start_recording(self):
        """Start screen recording."""
        # Capture screen frames at specified FPS
        # Store frames with timestamps
        
    def capture_frame(self):
        """Capture a single frame."""
        # Use mss to capture screen
        # Convert to numpy array
        # Return frame with timestamp
        
    def stop_recording(self):
        """Stop recording and save video."""
        # Encode frames to video file
        # Save to session tracking_data directory
        # Return video file path
```

### Integration with Session Window

1. **In `EmbeddedWebpageSessionWindow` (or new session window):**
   - Create `ScreenRecorder` instance when session starts
   - Start recording when session starts
   - Capture frames at configured FPS (e.g., 30 FPS = every 33ms)
   - Stop recording when session ends
   - Save video file alongside tracking data

2. **In `SessionReviewWindow`:**
   - Load video file from `tracking_data/{session_id}/screen_recording.mp4`
   - Use `QMediaPlayer` or `QVideoWidget` to play video
   - Synchronize video playback with timeline slider
   - Overlay mouse tracking on top of video using `QGraphicsScene` (already set up)

## File Organization

Screen recordings should be saved to:
```
{project_path}/
  tracking_data/
    {session_id}/
      screen_recording.mp4  (or .avi, .webm)
      tracking_data.json
      lsl_recorded_data.json
```

## Synchronization Strategy

1. **Session Start Time:** All timestamps reference `session_start_time`
2. **Video Timestamps:** Each frame should have a timestamp relative to session start
3. **LSL Timestamps:** Already using relative timestamps
4. **Mouse Tracking:** Already using relative timestamps
5. **Playback:** Use relative time to seek to correct frame in video

## Priority

According to `PROJECT_EVALUATION.md`:
- **High Priority:** Screen recording is a core feature that's completely missing
- **Phase 2:** Screen recording and mouse tracking (currently 45% complete - mouse tracking done, screen recording missing)

## Next Steps

1. **Choose recording library** (recommend `mss` + `opencv-python`)
2. **Implement `ScreenRecorder` class**
3. **Integrate into session window** (start/stop with session)
4. **Add video playback to `SessionReviewWindow`**
5. **Synchronize video with timeline and overlays**
6. **Test cross-platform compatibility**

## Notes

- Screen recording may present challenges across platforms (as noted in README.md)
- Consider performance implications of high-FPS recording
- May need to record in a separate thread to avoid blocking UI
- Consider compression/encoding settings for file size management

