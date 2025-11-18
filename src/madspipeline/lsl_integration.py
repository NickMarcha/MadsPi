"""
LSL (Lab Streaming Layer) integration for MadsPipeline.
Handles streaming bridge events to LSL and recording LSL streams during sessions.
"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_streams, local_clock
    LSL_AVAILABLE = True
except ImportError:
    LSL_AVAILABLE = False
    print("Warning: pylsl not available. LSL integration will be disabled.")


class LSLBridgeStreamer:
    """Streams bridge events to LSL."""
    
    def __init__(self, session_id: str):
        """Initialize LSL stream outlet for bridge events.
        
        Args:
            session_id: Session ID for stream identification
        """
        if not LSL_AVAILABLE:
            raise RuntimeError("pylsl is not available. Cannot create LSL stream.")
        
        self.session_id = session_id
        self.outlet: Optional[StreamOutlet] = None
        self._create_stream()
    
    def _create_stream(self):
        """Create LSL stream outlet for bridge events."""
        # Create stream info
        info = StreamInfo(
            name='MadsPipeline_BridgeEvents',
            type='Markers',
            channel_count=1,
            nominal_srate=0,  # Irregular rate (event-based)
            channel_format='string',
            source_id=f'session_{self.session_id}'
        )
        
        # Add metadata
        info.desc().append_child_value("session_id", self.session_id)
        info.desc().append_child_value("source", "MadsPipeline_HTML_Bridge")
        info.desc().append_child_value("description", "Events from HTML pages via Python bridge")
        
        # Create outlet
        self.outlet = StreamOutlet(info)
    
    def push_event(self, event_data: Dict[str, Any]):
        """Push an event to the LSL stream.
        
        Args:
            event_data: Event dictionary with type, data, timestamp
        """
        if not self.outlet:
            return
        
        try:
            # Convert event to JSON string for LSL
            event_str = json.dumps(event_data)
            # Push to LSL stream with current LSL timestamp
            self.outlet.push_sample([event_str], local_clock())
        except Exception as e:
            print(f"Error pushing event to LSL: {e}")
    
    def close(self):
        """Close the LSL stream outlet."""
        if self.outlet:
            # LSL outlets are automatically closed when the object is deleted
            self.outlet = None


class LSLMouseTrackingStreamer:
    """Streams mouse tracking data to LSL."""
    
    def __init__(self, session_id: str):
        """Initialize LSL stream outlet for mouse tracking.
        
        Args:
            session_id: Session ID for stream identification
        """
        if not LSL_AVAILABLE:
            raise RuntimeError("pylsl is not available. Cannot create LSL stream.")
        
        self.session_id = session_id
        self.outlet: Optional[StreamOutlet] = None
        self._create_stream()
    
    def _create_stream(self):
        """Create LSL stream outlet for mouse tracking."""
        # Create stream info - 3 channels: x, y, event_type (as string)
        info = StreamInfo(
            name='MadsPipeline_MouseTracking',
            type='Mouse',
            channel_count=3,  # x, y, event_type
            nominal_srate=10,  # 10 Hz (matches tracking timer)
            channel_format='float32',
            source_id=f'session_{self.session_id}'
        )
        
        # Add channel labels
        chns = info.desc().append_child("channels")
        chns.append_child("channel").append_child_value("label", "mouse_x")
        chns.append_child("channel").append_child_value("label", "mouse_y")
        chns.append_child("channel").append_child_value("label", "event_type")
        
        # Add metadata
        info.desc().append_child_value("session_id", self.session_id)
        info.desc().append_child_value("source", "MadsPipeline_MouseTracking")
        info.desc().append_child_value("description", "Mouse position and event tracking")
        
        # Create outlet
        self.outlet = StreamOutlet(info)
    
    def push_tracking_data(self, tracking_data: Dict[str, Any]):
        """Push mouse tracking data to the LSL stream.
        
        Args:
            tracking_data: Tracking data dictionary with mouse_position, event_type, etc.
        """
        if not self.outlet:
            return
        
        try:
            # Extract mouse position
            mouse_pos = tracking_data.get('mouse_position', (0, 0))
            x = float(mouse_pos[0]) if isinstance(mouse_pos, (tuple, list)) and len(mouse_pos) >= 2 else 0.0
            y = float(mouse_pos[1]) if isinstance(mouse_pos, (tuple, list)) and len(mouse_pos) >= 2 else 0.0
            
            # Extract event type (encode as float: 0=position, 1=press, 2=release, 3=move, 4=scroll)
            event_type_str = tracking_data.get('event_type', '')
            if event_type_str == 'mouse_press':
                event_type = 1.0
            elif event_type_str == 'mouse_release':
                event_type = 2.0
            elif event_type_str == 'mouse_move':
                event_type = 3.0
            elif event_type_str == 'mouse_scroll':
                event_type = 4.0
            else:
                event_type = 0.0  # Regular position tracking
            
            # Push to LSL stream with current LSL timestamp
            self.outlet.push_sample([x, y, event_type], local_clock())
        except Exception as e:
            print(f"Error pushing mouse tracking to LSL: {e}")
    
    def close(self):
        """Close the LSL stream outlet."""
        if self.outlet:
            # LSL outlets are automatically closed when the object is deleted
            self.outlet = None


class LSLRecorder:
    """Records LSL streams during a session."""
    
    def __init__(self, session_id: str):
        """Initialize LSL recorder.
        
        Args:
            session_id: Session ID for recording identification
        """
        if not LSL_AVAILABLE:
            raise RuntimeError("pylsl is not available. Cannot create LSL recorder.")
        
        self.session_id = session_id
        self.recorded_data: List[Dict[str, Any]] = []
        self.inlets: List[StreamInlet] = []
        self.stream_info: List[Dict[str, Any]] = []
        self.is_recording = False
        self.session_start_time: Optional[float] = None
    
    def start_recording(self, wait_time: float = 1.0, stream_name_filters: Optional[List[str]] = None):
        """Start recording LSL streams.
        
        Args:
            wait_time: Time in seconds to wait for resolving streams
        """
        if self.is_recording:
            return
        
        try:
            # Resolve available LSL streams
            # Note: resolve_streams() takes wait_time as positional argument, not keyword
            print(f"Resolving LSL streams for session {self.session_id}...")
            streams = resolve_streams(wait_time)

            if not streams:
                print("No LSL streams found.")
                return

            # Optionally filter streams by name (exact or substring match, case-insensitive)
            filtered_streams = []
            if stream_name_filters:
                lower_filters = [f.lower() for f in stream_name_filters if f]
                for s in streams:
                    name = s.name() or ''
                    lname = name.lower()
                    if any(f == lname or f in lname for f in lower_filters):
                        filtered_streams.append(s)
            else:
                filtered_streams = streams

            if not filtered_streams:
                print("No LSL streams matched the provided filters.")
                return

            # Create inlets for each selected stream
            for stream in filtered_streams:
                inlet = StreamInlet(stream)
                self.inlets.append(inlet)

                # Store stream info
                info = {
                    'name': stream.name(),
                    'type': stream.type(),
                    'channel_count': stream.channel_count(),
                    'source_id': stream.source_id(),
                    'session_id': self.session_id
                }
                self.stream_info.append(info)
                print(f"Recording stream: {stream.name()} ({stream.type()})")
            
            self.session_start_time = local_clock()
            self.is_recording = True
            print(f"Started recording {len(self.inlets)} LSL stream(s)")
            
        except Exception as e:
            print(f"Error starting LSL recording: {e}")
            self.is_recording = False
    
    def record_sample(self):
        """Pull and record samples from all LSL streams."""
        if not self.is_recording:
            return
        
        for i, inlet in enumerate(self.inlets):
            try:
                # Pull sample with no timeout (non-blocking)
                # Use try-except to handle cases where no sample is available
                try:
                    sample, timestamp = inlet.pull_sample(timeout=0.0)
                except Exception:
                    # No sample available or stream closed - this is normal
                    continue
                
                if sample:
                    # Calculate relative timestamp from session start
                    relative_time = timestamp - self.session_start_time if self.session_start_time else 0.0
                    
                    # Get clock offset for synchronization (CRITICAL for multi-device alignment)
                    # The clock offset represents the difference between the remote device's clock
                    # and the local machine's clock. This is essential for proper synchronization.
                    clock_offset = inlet.time_correction()  # Returns offset in seconds
                    
                    # Record the sample
                    recorded_sample = {
                        'timestamp': timestamp,
                        'relative_time': relative_time,
                        'data': sample,
                        'stream_index': i,
                        'stream_info': self.stream_info[i],
                        'session_id': self.session_id,
                        'recorded_at': datetime.now().isoformat(),
                        'clock_offset': clock_offset,  # NEW: For post-hoc synchronization
                        'local_time_when_recorded': local_clock()  # NEW: Reference for offset measurement timing
                    }
                    self.recorded_data.append(recorded_sample)
                    
            except Exception as e:
                # Continue with other streams if one fails - don't print every error
                # Only log if it's a real error (not just "no sample available")
                if "timeout" not in str(e).lower() and "no sample" not in str(e).lower():
                    # Suppress frequent error messages
                    pass
                continue
    
    def get_recorded_data(self) -> List[Dict[str, Any]]:
        """Get all recorded LSL data.
        
        Returns:
            List of recorded samples
        """
        return self.recorded_data.copy()
    
    def stop_recording(self):
        """Stop recording LSL streams."""
        self.is_recording = False
        
        # Close all inlets
        for inlet in self.inlets:
            try:
                inlet.close_stream()
            except Exception:
                pass
        
        self.inlets.clear()
        print(f"Stopped recording. Captured {len(self.recorded_data)} samples.")
    
    def save_to_file(self, filepath: str, additional_tracking_data: Optional[List[Dict[str, Any]]] = None):
        """Save recorded data to a JSON file, including additional tracking data.
        
        Args:
            filepath: Path to save the JSON file
            additional_tracking_data: Optional list of tracking data to include (e.g., non-LSL tracked data)
        """
        import json
        from pathlib import Path
        
        # Parse LSL samples to extract structured data
        parsed_samples = []
        for sample in self.recorded_data:
            try:
                # Try to parse JSON data from string samples (bridge events)
                if isinstance(sample['data'], list) and len(sample['data']) > 0:
                    data_item = sample['data'][0]
                    if isinstance(data_item, str):
                        try:
                            parsed_data = json.loads(data_item)
                            parsed_samples.append({
                                'timestamp': sample['timestamp'],
                                'relative_time': sample['relative_time'],
                                'stream_name': sample['stream_info']['name'],
                                'stream_type': sample['stream_info']['type'],
                                'data': parsed_data,
                                'raw_data': sample['data'],
                                'clock_offset': sample.get('clock_offset'),  # PRESERVE: Clock offset for sync
                                'local_time_when_recorded': sample.get('local_time_when_recorded')  # PRESERVE: Timing reference
                            })
                        except json.JSONDecodeError:
                            # Not JSON, keep as raw
                            parsed_samples.append({
                                'timestamp': sample['timestamp'],
                                'relative_time': sample['relative_time'],
                                'stream_name': sample['stream_info']['name'],
                                'stream_type': sample['stream_info']['type'],
                                'data': sample['data'],
                                'raw_data': sample['data'],
                                'clock_offset': sample.get('clock_offset'),  # PRESERVE: Clock offset for sync
                                'local_time_when_recorded': sample.get('local_time_when_recorded')  # PRESERVE: Timing reference
                            })
                    else:
                        # Numeric data (mouse tracking, etc.)
                        parsed_samples.append({
                            'timestamp': sample['timestamp'],
                            'relative_time': sample['relative_time'],
                            'stream_name': sample['stream_info']['name'],
                            'stream_type': sample['stream_info']['type'],
                            'data': sample['data'],
                            'raw_data': sample['data'],
                            'clock_offset': sample.get('clock_offset'),  # PRESERVE: Clock offset for sync
                            'local_time_when_recorded': sample.get('local_time_when_recorded')  # PRESERVE: Timing reference
                        })
                else:
                    parsed_samples.append({
                        'timestamp': sample['timestamp'],
                        'relative_time': sample['relative_time'],
                        'stream_name': sample.get('stream_info', {}).get('name', 'unknown'),
                        'stream_type': sample.get('stream_info', {}).get('type', 'unknown'),
                        'data': sample['data'],
                        'clock_offset': sample.get('clock_offset'),  # PRESERVE: Clock offset for sync
                        'local_time_when_recorded': sample.get('local_time_when_recorded')  # PRESERVE: Timing reference
                    })
            except Exception as e:
                # Keep original sample if parsing fails
                parsed_samples.append(sample)
        
        output_data = {
            'session_id': self.session_id,
            'stream_info': self.stream_info,
            'session_start_time': self.session_start_time,
            'total_samples': len(self.recorded_data),
            'lsl_samples': parsed_samples,
            'synchronization_info': {  # NEW: Synchronization metadata
                'sync_method': 'LSL_local_clock',
                'clock_offset_type': 'offset between local and remote device clocks (seconds)',
                'note': 'Use clock_offset from each sample for post-hoc synchronization with EmotiBit'
            }
        }
        
        # Add additional tracking data if provided (for completeness)
        if additional_tracking_data:
            output_data['additional_tracking_data'] = additional_tracking_data
            output_data['total_tracking_events'] = len(additional_tracking_data)
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)
        
        total_items = len(self.recorded_data)
        if additional_tracking_data:
            total_items += len(additional_tracking_data)
        print(f"Saved {len(self.recorded_data)} LSL samples" + 
              (f" and {len(additional_tracking_data)} additional tracking events" if additional_tracking_data else "") +
              f" to {filepath}")

