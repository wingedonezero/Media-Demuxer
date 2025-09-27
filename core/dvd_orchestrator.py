# remux_toolkit/tools/ffmpeg_dvd_remuxer/core/dvd_orchestrator.py
from pathlib import Path
from steps.dvd_steps import (
    DVDDemuxStep, DVDCCExtractStep, DVDChaptersStep, DVDFinalizeStep,
    DVDDiscAnalysisStep, DVDMetadataAnalysisStep, DVDTelecineDetectionStep,
    DVDIfoParserStep, DVDTimingAnalysisStep, DVDChapterNormalizationStep
)

class DVDOrchestrator:
    """Sub-orchestrator specifically for DVD processing."""

    def __init__(self, config, temp_dir: Path):
        self.config = config
        self.temp_dir = temp_dir

        # Analysis step is separate since it runs during queue addition
        self.analysis_step = DVDDiscAnalysisStep(self.config)

        # Processing pipeline steps (in corrected order)
        self.steps = [
            DVDIfoParserStep(self.config),           # 1. Parse DVD structure from IFO
            DVDMetadataAnalysisStep(self.config),    # 2. Analyze with ffprobe
            DVDDemuxStep(self.config),               # 3. Extract streams with NAV timing
            DVDTimingAnalysisStep(self.config),      # 4. Analyze extracted file timing
            DVDCCExtractStep(self.config),           # 5. Extract closed captions
            DVDChaptersStep(self.config),            # 6. Process chapters
            DVDChapterNormalizationStep(self.config), # 7. Fix chapter issues
            DVDTelecineDetectionStep(self.config),   # 8. Detect telecined content
            DVDFinalizeStep(self.config),            # 9. Mux to final MKV
        ]

    def analyze_disc(self, path: Path, log_emitter, stop_event) -> tuple[list, str]:
        """Analyze a DVD disc and return list of titles."""
        return self.analysis_step.run(path, self.temp_dir, log_emitter, stop_event)

    def run_pipeline(self, context: dict, log_emitter, stop_event):
        """Run the DVD processing pipeline. This is a generator that yields progress updates."""
        title_num = context['title_num']
        log_emitter(f"--- Processing DVD Title {title_num} ---")

        out_folder = context['out_folder']
        context['temp_mkv_path'] = out_folder / f"title_{title_num}_temp.mkv"
        context['cc_srt_path'] = out_folder / f"title_{title_num}_cc.srt"
        context['mod_chap_xml_path'] = out_folder / f"title_{title_num}_chapters_mod.xml"

        files_to_clean = [
            context['temp_mkv_path'],
            context['cc_srt_path'],
            context['mod_chap_xml_path']
        ]

        # Add metadata file to cleanup list if not keeping it
        if not self.config.get("keep_metadata_json", False):
            files_to_clean.append(out_folder / f"title_{title_num}_metadata.json")

        # Get list of enabled steps for accurate numbering
        enabled_steps = []
        for step in self.steps:
            if hasattr(step, 'is_enabled') and not step.is_enabled:
                continue
            enabled_steps.append(step)

        total_steps = len(enabled_steps)

        try:
            step_num = 0
            for step in self.steps:
                if stop_event.is_set():
                    return

                # Check if this step should be counted/numbered
                is_numbered_step = not (hasattr(step, 'is_enabled') and not step.is_enabled)
                if is_numbered_step:
                    step_num += 1
                    context['step_info'] = f"[STEP {step_num}/{total_steps}]"
                else:
                    context['step_info'] = "[OPTIONAL]"

                # Run the step
                step_runner = step.run(context, log_emitter, stop_event)

                # Handle generators and regular returns
                if hasattr(step_runner, '__iter__') or hasattr(step_runner, '__next__'):
                    final_status = False
                    for progress_update in step_runner:
                        if isinstance(progress_update, bool):
                            final_status = progress_update
                        else:
                            yield progress_update
                    success = final_status
                else:
                    success = step_runner

                if not success:
                    log_emitter(f"!! Step {step.__class__.__name__} failed for Title {title_num}. Aborting title.")
                    return

        finally:
            # Clean up temporary files
            if not self.config.get("keep_temp_files", False):
                log_emitter(f"Cleaning up temporary files for Title {title_num}...")
                for f in files_to_clean:
                    if f and f.exists():
                        try:
                            f.unlink()
                        except OSError:
                            pass
