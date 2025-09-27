# remux_toolkit/tools/ffmpeg_dvd_remuxer/steps/dvd_steps/dvd_demux.py
import re
from pathlib import Path
from utils.helpers import run_stream, time_str_to_seconds

class DVDDemuxStep:
    def __init__(self, config):
        self.config = config

    def run(self, context: dict, log_emitter, stop_event):
        """Extract streams using proper DVD-Video demuxing with NAV timing preserved."""
        step_info = context.get('step_info', '[STEP]')
        log_emitter(f"{step_info} Extracting streams with DVD NAV timing preserved...")

        input_path = context['input_path']
        title_num = context['title_num']
        out_folder = context['out_folder']

        metadata = context.get('title_metadata')
        if not metadata:
            log_emitter("!! ERROR: No metadata found. MetadataAnalysisStep must run first.")
            yield False
            return

        context['extracted_streams'] = []
        title_info = context.get('title_info', {})
        duration_s = time_str_to_seconds(title_info.get('length'))

        total_streams = len(metadata['streams'])
        current_stream = 0

        for stream_meta in metadata['streams']:
            current_stream += 1
            stream_idx = stream_meta['index']
            stream_type = stream_meta['type']
            codec = stream_meta.get('codec', 'unknown')
            extension = stream_meta.get('extract_extension', '.bin')

            # Build output filename
            output_file = out_folder / f"title_{title_num}_s{stream_idx}_{stream_type}{extension}"

            log_emitter(f"  [{current_stream}/{total_streams}] Extracting {stream_type} stream #{stream_idx} ({codec}) -> {output_file.name}")

            # CRITICAL DVD FLAGS:
            # 1. Use -preindex 1 to read NAV packets for proper timing
            # 2. Do NOT use -fflags +genpts (destroys NAV timing)
            # 3. Use -avoid_negative_ts make_zero for consistent start
            # 4. Do NOT use -copyts (dvdvideo demuxer handles timing)

            ffmpeg_cmd = [
                "ffmpeg", "-y", "-hide_banner",
                "-progress", "-", "-nostats",
                "-probesize", "100M",
                "-analyzeduration", "100M",
                "-preindex", "1",  # CRITICAL: Read NAV packets for timing
                "-avoid_negative_ts", "make_zero",  # Shift to start at 0
                "-fflags", "+discardcorrupt",  # Only discard corrupt packets
            ]

            # Trim padding cells if configured
            if self.config.get("ffmpeg_trim_padding", True):
                ffmpeg_cmd.extend(["-trim", "1"])
            else:
                ffmpeg_cmd.extend(["-trim", "0"])

            # DVD input
            ffmpeg_cmd.extend([
                "-f", "dvdvideo",
                "-title", str(title_num),
                "-i", str(input_path),
                "-map", f"0:{stream_idx}",
            ])

            # Video extraction
            if stream_type == "video":
                ffmpeg_cmd.extend(["-c:v", "copy"])

                if self.config.get("remove_eia_608", True):
                    ffmpeg_cmd.extend(["-bsf:v", "filter_units=remove_types=178"])

                if extension == ".m2v":
                    ffmpeg_cmd.extend(["-f", "mpeg2video"])
                elif extension == ".264":
                    ffmpeg_cmd.extend(["-f", "h264"])

            # Audio extraction - NAV timing preserved
            elif stream_type == "audio":
                ffmpeg_cmd.extend(["-c:a", "copy"])

                if extension == ".ac3":
                    ffmpeg_cmd.extend(["-f", "ac3"])
                elif extension == ".eac3":
                    ffmpeg_cmd.extend(["-f", "eac3"])
                elif extension == ".dts":
                    ffmpeg_cmd.extend(["-f", "dts"])
                elif extension == ".mp2":
                    ffmpeg_cmd.extend(["-f", "mp2"])
                elif extension == ".wav":
                    ffmpeg_cmd.extend(["-c:a", "pcm_s16le", "-f", "wav"])

            # Subtitle extraction as VOBSUB
            elif stream_type == "subtitle":
                if codec in ["dvd_subtitle", "dvdsub"]:
                    # Extract as VOBSUB format (.idx/.sub pair)
                    idx_file = output_file.with_suffix('.idx')
                    sub_file = output_file.with_suffix('.sub')

                    ffmpeg_cmd.extend([
                        "-c:s", "copy",
                        "-f", "vobsub",
                        str(output_file.with_suffix(''))  # Base name without extension
                    ])

                    stream_meta['idx_file'] = idx_file
                    stream_meta['sub_file'] = sub_file
                    output_file = sub_file  # Check .sub exists later
                else:
                    ffmpeg_cmd.extend(["-c:s", "copy"])
                    ffmpeg_cmd.append(str(output_file))

            # Add output file for non-VOBSUB
            if stream_type != "subtitle" or codec not in ["dvd_subtitle", "dvdsub"]:
                ffmpeg_cmd.append(str(output_file))

            # Execute extraction
            stream_duration_us = duration_s * 1_000_000 / total_streams if duration_s > 0 else 0
            base_progress = (current_stream - 1) * 100 / total_streams

            for line in run_stream(ffmpeg_cmd, stop_event):
                if line.strip().startswith("out_time_us="):
                    try:
                        current_us = int(line.strip().split('=')[1])
                        if stream_duration_us > 0:
                            stream_percent = (current_us / stream_duration_us) * (100 / total_streams)
                            total_percent = int(base_progress + stream_percent)
                            yield min(100, max(0, total_percent))
                    except (ValueError, IndexError):
                        pass
                elif "timestamp" in line.lower() or "nav" in line.lower():
                    continue  # Expected with NAV processing
                elif "invalid" not in line.lower():
                    log_emitter(line)

            if stop_event.is_set():
                yield False
                return

            # Verify extraction
            if not output_file.exists() or output_file.stat().st_size < 1024:
                log_emitter(f"!! WARNING: Failed to extract stream #{stream_idx}")
                continue

            # For VOBSUB, check both files exist
            if stream_type == "subtitle" and codec in ["dvd_subtitle", "dvdsub"]:
                idx_file = stream_meta.get('idx_file')
                sub_file = stream_meta.get('sub_file')
                if not (idx_file and idx_file.exists() and sub_file and sub_file.exists()):
                    log_emitter(f"!! WARNING: VOBSUB extraction incomplete for stream #{stream_idx}")
                    continue

            context['extracted_streams'].append({
                'index': stream_idx,
                'type': stream_type,
                'file': output_file,
                'metadata': stream_meta
            })

            log_emitter(f"     -> Extracted: {output_file.stat().st_size / 1024 / 1024:.1f} MB")

        if not context['extracted_streams']:
            log_emitter("!! ERROR: No streams extracted.")
            yield False
            return

        log_emitter(f"  -> Extracted {len(context['extracted_streams'])} streams with NAV timing preserved.")
        yield True
