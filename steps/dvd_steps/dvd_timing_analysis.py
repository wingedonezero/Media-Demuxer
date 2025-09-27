# remux_toolkit/tools/ffmpeg_dvd_remuxer/steps/dvd_steps/dvd_timing_analysis.py
from pathlib import Path
import json
import subprocess

class DVDTimingAnalysisStep:
    """Analyze DVD timing from extracted streams."""

    def __init__(self, config):
        self.config = config

    def run(self, context: dict, log_emitter, stop_event) -> bool:
        """Analyze timing from extracted streams."""
        step_info = context.get('step_info', '[STEP]')
        log_emitter(f"{step_info} Analyzing extracted stream timing...")

        extracted_streams = context.get('extracted_streams', [])
        if not extracted_streams:
            log_emitter("  -> No extracted streams to analyze")
            return True

        # Probe each extracted file for its start time
        # The dvdvideo demuxer with preindex gives us NAV-accurate timing
        stream_timings = {}

        for stream_info in extracted_streams:
            stream_file = stream_info['file']
            stream_idx = stream_info['index']
            stream_type = stream_info['type']
            metadata = stream_info.get('metadata', {})

            # For VOBSUB, check the .idx file
            if stream_type == 'subtitle' and metadata.get('idx_file'):
                idx_file = metadata['idx_file']
                if idx_file.exists():
                    # Parse .idx for timing
                    start_time = self._parse_vobsub_start(idx_file)
                    stream_timings[stream_idx] = start_time
                    log_emitter(f"  -> Stream #{stream_idx} (VOBSUB): starts at {start_time:.3f}s")
                    continue

            # Probe the file for start time
            probe_cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "stream=start_time,start_pts:format=start_time",
                "-print_format", "json",
                str(stream_file)
            ]

            try:
                result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    data = json.loads(result.stdout)

                    # Try stream start_time first, then format start_time
                    start_time = 0
                    if data.get('streams') and len(data['streams']) > 0:
                        stream = data['streams'][0]
                        start_time = float(stream.get('start_time', 0))
                    elif data.get('format'):
                        start_time = float(data['format'].get('start_time', 0))

                    stream_timings[stream_idx] = start_time
                    log_emitter(f"  -> Stream #{stream_idx} ({stream_type}): starts at {start_time:.3f}s")
            except Exception as e:
                log_emitter(f"  -> Could not probe stream #{stream_idx}: {e}")
                stream_timings[stream_idx] = 0

        # Store timings in context for finalize step
        context['stream_timings'] = stream_timings

        # Find earliest stream (should be 0 with -avoid_negative_ts make_zero)
        if stream_timings:
            earliest = min(stream_timings.values())
            latest = max(stream_timings.values())

            if earliest != 0:
                log_emitter(f"  -> Earliest stream offset: {earliest:.3f}s")
            if latest - earliest > 0.001:
                log_emitter(f"  -> Stream timing spread: {(latest - earliest)*1000:.1f}ms")

        return True

    def _parse_vobsub_start(self, idx_file):
        """Parse VOBSUB .idx file for first timestamp."""
        try:
            with open(idx_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.startswith('timestamp:'):
                        # Format: timestamp: HH:MM:SS:mmm
                        time_str = line.split(':', 1)[1].strip()
                        parts = time_str.split(':')
                        if len(parts) >= 4:
                            hours = int(parts[0])
                            minutes = int(parts[1])
                            seconds = int(parts[2])
                            millis = int(parts[3])
                            return hours * 3600 + minutes * 60 + seconds + millis / 1000
        except:
            pass
        return 0
