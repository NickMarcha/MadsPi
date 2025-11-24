"""
LSL (Lab Streaming Layer) integration for MadsPipeline.
Handles streaming bridge events to LSL and recording LSL streams during sessions.
"""
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_streams, local_clock
    LSL_AVAILABLE = True
except ImportError:
    LSL_AVAILABLE = False
    logger.warning("pylsl not available. LSL integration will be disabled.")


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
            logger.error(f"Error pushing event to LSL: {e}")
    
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
            logger.error(f"Error pushing mouse tracking to LSL: {e}")
    
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
        self.stream_channel_filters: Dict[str, List[int]] = {}  # Channel indices to record per stream
    
    def start_recording(self, wait_time: float = 1.0, stream_name_filters: Optional[List[str]] = None, stream_type_filters: Optional[List[str]] = None, stream_channel_filters: Optional[Dict[str, List[int]]] = None):
        """Start recording LSL streams.
        
        Args:
            wait_time: Time in seconds to wait for resolving streams
            stream_name_filters: Optional list of stream names to record (case-insensitive substring match)
            stream_type_filters: Optional list of stream types to record (case-insensitive substring match)
            stream_channel_filters: Optional dict mapping stream names to lists of channel indices to record
                                   e.g., {"EmotiBit_BrainFlow": [0, 1, 2, 5]} - empty list means all channels
        """
        # Store channel filters
        if stream_channel_filters:
            self.stream_channel_filters = stream_channel_filters
        else:
            self.stream_channel_filters = {}
        if self.is_recording:
            return
        
        try:
            # Resolve available LSL streams
            # Note: resolve_streams() takes wait_time as positional argument, not keyword
            logger.info(f"Resolving LSL streams for session {self.session_id} (wait_time={wait_time}s)...")
            try:
                streams = resolve_streams(wait_time)
            except Exception as e:
                logger.error(f"Error during stream resolution: {e}", exc_info=True)
                return

            if not streams:
                logger.info("No LSL streams found.")
                return
            
            logger.info(f"Found {len(streams)} LSL stream(s): {[s.name() for s in streams]}")

            # Filter streams by name and/or type
            filtered_streams = []
            
            # If no filters provided, record all streams
            if not stream_name_filters and not stream_type_filters:
                filtered_streams = streams
                logger.info(f"No filters provided - recording all {len(streams)} streams")
            else:
                # Prepare filters (case-insensitive)
                name_filters = [f.lower() for f in (stream_name_filters or []) if f]
                type_filters = [f.lower() for f in (stream_type_filters or []) if f]
                
                logger.info(f"Filtering streams: name_filters={name_filters}, type_filters={type_filters}")
                logger.info(f"Available streams: {[s.name() for s in streams]}")
                
                for s in streams:
                    name = s.name() or ''
                    stream_type = s.type() or ''
                    lname = name.lower()
                    ltype = stream_type.lower()
                    
                    # Match if name filter matches OR type filter matches (OR logic)
                    # If both filters are provided, stream must match at least one
                    name_match = not name_filters or any(f == lname or f in lname for f in name_filters)
                    type_match = not type_filters or any(f == ltype or f in ltype for f in type_filters)
                    
                    # If only one filter type is provided, use that; if both, match either
                    if name_filters and type_filters:
                        # Both filters: match if name OR type matches
                        if name_match or type_match:
                            filtered_streams.append(s)
                            logger.debug(f"Stream '{name}' matched (name_match={name_match}, type_match={type_match})")
                    elif name_filters:
                        # Only name filter: must match name
                        if name_match:
                            filtered_streams.append(s)
                            logger.debug(f"Stream '{name}' matched name filter")
                        else:
                            logger.debug(f"Stream '{name}' did not match name filter {name_filters}")
                    elif type_filters:
                        # Only type filter: must match type
                        if type_match:
                            filtered_streams.append(s)
                            logger.debug(f"Stream '{name}' matched type filter")
                
                logger.info(f"Filtered {len(streams)} streams down to {len(filtered_streams)} streams")

            if not filtered_streams:
                logger.warning(f"No LSL streams matched the provided filters. Available streams: {[s.name() for s in streams]}")
                logger.info("No LSL streams matched the provided filters.")
                return

            logger.info(f"Creating inlets for {len(filtered_streams)} filtered stream(s): {[s.name() for s in filtered_streams]}")
            
            # Create inlets for each selected stream
            for idx, stream in enumerate(filtered_streams):
                stream_name = stream.name()
                logger.info(f"Processing stream {idx+1}/{len(filtered_streams)}: {stream_name}")
                try:
                    logger.debug(f"Creating StreamInlet for {stream_name}")
                    inlet = StreamInlet(stream)
                    self.inlets.append(inlet)
                    logger.info(f"Inlet created successfully for {stream_name}")
                except Exception as e:
                    logger.error(f"Failed to create inlet for {stream_name}: {e}", exc_info=True)
                    continue

                logger.debug(f"Getting stream info for {stream_name}")
                try:
                    # Get full stream info from inlet (has complete metadata including channel labels)
                    # Note: info() should be fast, but if it hangs, we'll see it in the logs
                    inlet_info = inlet.info()
                    logger.info(f"Got inlet info for {stream_name} (channels: {inlet_info.channel_count()})")
                except Exception as e:
                    logger.error(f"Failed to get inlet info for {stream_name}: {e}", exc_info=True)
                    inlet_info = None
                
                # Extract channel labels from metadata for easy access
                channel_labels = {}
                try:
                    if inlet_info:
                        logger.debug(f"Extracting channel labels for {stream_name}")
                        desc = inlet_info.desc()
                        if desc:
                            chns = desc.child("channels")
                            if chns:
                                ch = chns.child("channel")
                                i = 0
                                max_channels = inlet_info.channel_count()
                                logger.debug(f"Reading up to {max_channels} channel labels for {stream_name}")
                                while ch and i < max_channels:
                                    try:
                                        label = ch.child_value("label") or f"Channel {i}"
                                        channel_labels[i] = label
                                    except Exception as e:
                                        logger.debug(f"Error reading label for channel {i}: {e}")
                                        channel_labels[i] = f"Channel {i}"
                                    try:
                                        ch = ch.next_sibling()
                                    except:
                                        break
                                    i += 1
                                logger.info(f"Extracted {len(channel_labels)} channel labels for {stream_name}")
                            else:
                                logger.debug(f"No channels metadata found for {stream_name}")
                        else:
                            logger.debug(f"No description metadata found for {stream_name}")
                except Exception as e:
                    logger.warning(f"Could not extract channel labels for {stream_name}: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                
                # Store stream info with full metadata
                logger.debug(f"Storing stream info for {stream_name}")
                info = {
                    'name': stream_name,
                    'type': stream.type(),
                    'channel_count': stream.channel_count(),
                    'source_id': stream.source_id(),
                    'session_id': self.session_id,
                    'inlet_info': inlet_info,  # Store full StreamInfo object for metadata access
                    'channel_labels': channel_labels  # Also store as dict for easy access
                }
                self.stream_info.append(info)
                if channel_labels:
                    logger.info(f"Recording stream: {stream_name} ({stream.type()}) with {len(channel_labels)} labeled channels")
                else:
                    logger.info(f"Recording stream: {stream_name} ({stream.type()})")
            
            logger.debug("Setting session start time and is_recording flag")
            self.session_start_time = local_clock()
            self.is_recording = True
            logger.info(f"Started recording {len(self.inlets)} LSL stream(s)")
            
        except Exception as e:
            logger.error(f"Error starting LSL recording: {e}", exc_info=True)
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
                    # Apply channel filtering if configured for this stream
                    stream_name = self.stream_info[i]['name']
                    filtered_sample = sample
                    channel_filter = self.stream_channel_filters.get(stream_name, [])
                    
                    # If channel filter exists and is not empty, filter the sample
                    if channel_filter:
                        try:
                            # Filter sample to only include selected channel indices
                            filtered_sample = [sample[ch_idx] for ch_idx in channel_filter if 0 <= ch_idx < len(sample)]
                            logger.debug(f"Filtered {stream_name}: {len(sample)} -> {len(filtered_sample)} channels")
                        except (IndexError, TypeError) as e:
                            logger.warning(f"Error filtering channels for {stream_name}: {e}, recording all channels")
                            filtered_sample = sample
                    
                    # Calculate relative timestamp from session start
                    relative_time = timestamp - self.session_start_time if self.session_start_time else 0.0
                    
                    # Get clock offset for synchronization (CRITICAL for multi-device alignment)
                    # The clock offset represents the difference between the remote device's clock
                    # and the local machine's clock. This is essential for proper synchronization.
                    clock_offset = inlet.time_correction()  # Returns offset in seconds
                    
                    # Record the sample (with filtered channels if applicable)
                    stream_info_copy = self.stream_info[i].copy()
                    # Include channel_labels in the stream_info for easy access
                    recorded_sample = {
                        'timestamp': timestamp,
                        'relative_time': relative_time,
                        'data': filtered_sample,
                        'stream_index': i,
                        'stream_info': stream_info_copy,  # Includes channel_labels
                        'session_id': self.session_id,
                        'recorded_at': datetime.now().isoformat(),
                        'clock_offset': clock_offset,  # NEW: For post-hoc synchronization
                        'local_time_when_recorded': local_clock(),  # NEW: Reference for offset measurement timing
                        'original_channel_count': len(sample),  # Store original count for reference
                        'filtered_channel_indices': channel_filter if channel_filter else None  # Store which channels were selected
                    }
                    # Update stream_info to reflect filtered channel count
                    if channel_filter:
                        recorded_sample['stream_info']['channel_count'] = len(filtered_sample)
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
        logger.info(f"Stopped recording. Captured {len(self.recorded_data)} samples.")
    
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
        logger.info(f"Saved {len(self.recorded_data)} LSL samples" + 
              (f" and {len(additional_tracking_data)} additional tracking events" if additional_tracking_data else "") +
              f" to {filepath}")

