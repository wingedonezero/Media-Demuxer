# workers/processing_worker.py
import threading
import time
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from core.orchestrator import MasterOrchestrator
from utils.paths import create_output_folder

class ProcessingThread(QThread):
    """Separate thread for heavy processing to prevent GUI freezing."""

    # Signals for communication with GUI
    log = pyqtSignal(str)
    title_progress = pyqtSignal(object, int)  # job, percent
    queue_progress = pyqtSignal(int, int)  # current_job, total_jobs
    processing_finished = pyqtSignal()

    def __init__(self, jobs_to_run, config, temp_dir):
        super().__init__()
        self.jobs_to_run = jobs_to_run
        self.config = config
        self.temp_dir = temp_dir
        self.stop_event = threading.Event()
        self.orchestrator = MasterOrchestrator(config, temp_dir)

    def run(self):
        """Run processing in separate thread."""
        total_jobs = len(self.jobs_to_run)
        self.queue_progress.emit(0, total_jobs)

        try:
            output_root = Path(self.config.get("default_output_directory"))
            if not output_root:
                raise ValueError("Output directory is not set.")

            for i, job in enumerate(self.jobs_to_run):
                self.queue_progress.emit(i, total_jobs)
                if self.stop_event.is_set():
                    self.log.emit("\n>> Processing stopped by user. <<")
                    break

                output_folder = create_output_folder(output_root, job.base_name, job.group_name)
                log_file_path = output_folder / f"{job.base_name}_process_{time.strftime('%Y%m%d-%H%M%S')}.log"

                with open(log_file_path, "w", encoding="utf-8", buffering=1) as log_fh:
                    def log_and_write(message: str):
                        self.log.emit(message)
                        log_fh.write(message + '\n')

                    log_and_write(f"▶ Starting job for '{job.base_name}'. Output: {output_folder}")

                    for title_num in sorted(list(job.selected_titles)):
                        if self.stop_event.is_set():
                            break

                        title_info = next((t for t in job.titles_info if t['title'] == str(title_num)), None)
                        context = {
                            'input_path': job.source_path,
                            'source_type': job.source_type,  # 'dvd' or 'bluray'
                            'title_num': title_num,
                            'out_folder': output_folder,
                            'config': self.config,
                            'field_order': title_info.get('field_order') if title_info else None,
                            'title_info': title_info,
                        }

                        # Process through master orchestrator
                        for progress_update in self.orchestrator.run_pipeline(context, log_and_write, self.stop_event):
                            if isinstance(progress_update, int):
                                self.title_progress.emit(job, progress_update)

                self.title_progress.emit(job, 100)
                self.queue_progress.emit(i + 1, total_jobs)

            if not self.stop_event.is_set():
                self.log.emit("\n🎉 All jobs finished. 🎉")

        except Exception as e:
            self.log.emit(f"!! PROCESSING ERROR: {e}")
        finally:
            self.processing_finished.emit()

    def stop(self):
        """Stop processing."""
        self.stop_event.set()


class AnalysisThread(QThread):
    """Separate thread for disc analysis."""

    log = pyqtSignal(str)
    analysis_finished = pyqtSignal(object, list)  # job, titles

    def __init__(self, job, config, temp_dir):
        super().__init__()
        self.job = job
        self.config = config
        self.temp_dir = temp_dir
        self.stop_event = threading.Event()
        self.orchestrator = MasterOrchestrator(config, temp_dir)

    def run(self):
        """Run analysis in separate thread."""
        try:
            titles, message = self.orchestrator.analyze_disc(
                self.job.source_path,
                self.job.source_type,
                self.log.emit,
                self.stop_event
            )
            self.log.emit(f"For '{self.job.base_name}': {message}")
            self.analysis_finished.emit(self.job, titles)
        except Exception as e:
            self.log.emit(f"!! ANALYSIS ERROR for '{self.job.base_name}': {e}")
            self.analysis_finished.emit(self.job, [])

    def stop(self):
        """Stop analysis."""
        self.stop_event.set()
