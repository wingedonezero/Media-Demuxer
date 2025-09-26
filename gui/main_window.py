# gui/main_window.py
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidgetItem, QHeaderView, QProgressBar, QTextEdit, QCheckBox,
    QDialog, QSplitter, QFileDialog, QMenuBar, QMenu, QStatusBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction

from core.config import ConfigManager
from models.job import Job
from workers.processing_worker import ProcessingThread, AnalysisThread
from .prefs_dialog import PrefsDialog
from .queue_tree import DropTree
from .details_panel import DetailsPanel
from utils.paths import find_dvd_sources, detect_source_type
from utils.helpers import time_str_to_seconds

class MainWindow(QMainWindow):
    """Main application window for Media-Demuxer."""

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        self.jobs = []
        self.active_analysis_threads = []
        self.processing_thread = None
        self._updating_checks = False

        self._init_statusbar()
        self._init_ui()
        self._init_menu()

    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Media-Demuxer")
        self.setMinimumSize(1200, 800)

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Action buttons
        action_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Source(s)...")
        self.clear_btn = QPushButton("Clear Queue")
        self.process_btn = QPushButton("Process Queue")
        self.prefs_btn = QPushButton("Preferences…")
        self.stop_btn = QPushButton("Stop Process")

        action_layout.addWidget(self.add_btn)
        action_layout.addWidget(self.clear_btn)
        action_layout.addWidget(self.process_btn)
        action_layout.addWidget(self.prefs_btn)
        action_layout.addStretch()
        action_layout.addWidget(self.stop_btn)

        # Queue tree widget
        self.queue_tree = DropTree()
        self.queue_tree.setColumnCount(6)
        self.queue_tree.setHeaderLabels(["Source / Title", "Length", "Chapters", "Video", "Audio", "Progress"])
        header = self.queue_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        # Details panel
        self.details_panel = DetailsPanel()

        # Log output
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        # Overall progress bar
        self.overall_progress_bar = QProgressBar()

        # Layout splitters
        center_splitter = QSplitter(Qt.Orientation.Horizontal)
        center_splitter.addWidget(self.queue_tree)
        center_splitter.addWidget(self.details_panel)
        center_splitter.setSizes([700, 300])

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(center_splitter)
        main_splitter.addWidget(self.log_box)
        main_splitter.setSizes([500, 200])

        # Add to main layout
        main_layout.addLayout(action_layout)
        main_layout.addWidget(main_splitter)
        main_layout.addWidget(self.overall_progress_bar)

        # Connect signals
        self.add_btn.clicked.connect(self.add_source)
        self.clear_btn.clicked.connect(self.clear_queue)
        self.queue_tree.pathsDropped.connect(self.handle_drop)
        self.prefs_btn.clicked.connect(self.open_prefs)
        self.process_btn.clicked.connect(self.start_processing)
        self.stop_btn.clicked.connect(self.stop_processing)
        self.queue_tree.itemChanged.connect(self._on_item_checked)
        self.queue_tree.currentItemChanged.connect(self._on_item_selected)

        # Set initial button states
        self.set_controls_enabled()

        # Welcome message
        self.log_box.append("=== Media-Demuxer Started ===")
        self.log_box.append("Ready to process DVD sources. Blu-ray support coming soon!")
        self.log_box.append("")

    def _init_menu(self):
        """Initialize the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        add_action = QAction("&Add Source...", self)
        add_action.triggered.connect(self.add_source)
        file_menu.addAction(add_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        prefs_action = QAction("&Preferences...", self)
        prefs_action.triggered.connect(self.open_prefs)
        edit_menu.addAction(prefs_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        clear_temp_action = QAction("Clear &Temp Files", self)
        clear_temp_action.triggered.connect(self.clear_temp_files)
        tools_menu.addAction(clear_temp_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _init_statusbar(self):
        """Initialize the status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Ready")

    def set_controls_enabled(self):
        """Enable/disable controls based on processing state."""
        is_busy = bool(self.active_analysis_threads) or (self.processing_thread is not None)
        self.add_btn.setEnabled(not is_busy)
        self.clear_btn.setEnabled(not is_busy)
        self.process_btn.setEnabled(not is_busy and len(self.jobs) > 0)
        self.prefs_btn.setEnabled(not is_busy)
        self.stop_btn.setEnabled(is_busy)

        # Update status bar
        if is_busy:
            if self.processing_thread:
                self.statusbar.showMessage("Processing...")
            else:
                self.statusbar.showMessage("Analyzing...")
        else:
            job_count = len(self.jobs)
            if job_count > 0:
                self.statusbar.showMessage(f"Ready - {job_count} source(s) in queue")
            else:
                self.statusbar.showMessage("Ready")

    def handle_drop(self, paths: list[str]):
        """Handle files dropped onto the queue."""
        group_name = Path(paths[0]).parent.name if len(paths) > 1 and len(set(Path(p).parent for p in paths)) == 1 else None
        all_sources = [source for p_str in paths for source in find_dvd_sources(Path(p_str))]

        if not all_sources:
            self.log_box.append("No valid DVD sources (ISO/VIDEO_TS) found.")
            return

        self.set_controls_enabled()

        for source_path in all_sources:
            if any(j.source_path == source_path for j in self.jobs):
                continue

            # Detect source type (DVD/Blu-ray)
            source_type = detect_source_type(source_path)

            job = Job(source_path=source_path, source_type=source_type, group_name=group_name)
            self._add_job_to_queue(job)
            self._run_analysis(job)

    def add_source(self):
        """Open file dialog to add a source."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Media Source",
            str(Path.home()),
            "Media Sources (*.iso);;All Files (*)"
        )

        if path:
            p = Path(path)
            source_dir = p.parent.parent if p.parent.name.lower() == 'video_ts' else p
            self.handle_drop([str(source_dir)])

    def clear_queue(self):
        """Clear the entire queue."""
        self.stop_processing()
        self.jobs.clear()
        self.queue_tree.clear()
        self.details_panel.clear_panel()
        self.log_box.append("Queue cleared.")
        self.set_controls_enabled()

    def _add_job_to_queue(self, job: Job):
        """Add a job to the queue tree."""
        self.jobs.append(job)

        item = QTreeWidgetItem([job.base_name, "", "", "", "", ""])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Unchecked)
        job._gui_item = item
        item.setData(0, Qt.ItemDataRole.UserRole, job)
        self.queue_tree.addTopLevelItem(item)

        # Add progress bar widget
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        progress_bar.setTextVisible(False)
        self.queue_tree.setItemWidget(item, 5, progress_bar)

    def _run_analysis(self, job: Job):
        """Run analysis on a job in a separate thread."""
        job.status = "Analyzing..."
        job._gui_item.setText(0, f"{job.base_name} [Analyzing...]")

        # Create and start analysis thread
        thread = AnalysisThread(job, self.config, self.config_manager.get_temp_dir())
        thread.log.connect(self.log_box.append)
        thread.analysis_finished.connect(self.on_analysis_finished)
        thread.finished.connect(lambda: self._on_analysis_thread_finished(thread))

        self.active_analysis_threads.append(thread)
        thread.start()

        self.set_controls_enabled()

    def on_analysis_finished(self, job: Job, titles: list):
        """Handle analysis completion."""
        job.titles_info = titles
        item = job._gui_item
        if not item:
            return

        self._updating_checks = True
        try:
            item.takeChildren()
            min_len = self.config.get("minimum_title_length", 120)

            if not titles:
                job.status = "Analysis Failed"
                item.setText(0, f"{job.base_name} [Failed]")
                item.setCheckState(0, Qt.CheckState.Unchecked)
                item.setDisabled(True)
                return

            job.status = "Ready"
            item.setText(0, job.base_name)

            # Find titles that meet minimum length
            long_title_nums = {t['title'] for t in titles if time_str_to_seconds(t['length']) >= min_len}

            for title_data in titles:
                child = QTreeWidgetItem([
                    f"  - Title {title_data['title']}",
                    title_data['length'],
                    title_data['chapters'],
                    title_data.get('v_codecs', ''),
                    title_data.get('a_codecs', '')
                ])

                child.setData(0, Qt.ItemDataRole.UserRole, title_data)
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)

                if title_data['title'] in long_title_nums:
                    child.setCheckState(0, Qt.CheckState.Checked)
                else:
                    child.setCheckState(0, Qt.CheckState.Unchecked)

                item.addChild(child)

            item.setExpanded(True)
            self._set_parent_check_from_children(item)
        finally:
            self._updating_checks = False

    def _on_analysis_thread_finished(self, thread):
        """Clean up after analysis thread finishes."""
        if thread in self.active_analysis_threads:
            self.active_analysis_threads.remove(thread)
        thread.deleteLater()
        self.set_controls_enabled()

    def start_processing(self):
        """Start processing the queue."""
        self.stop_processing()

        jobs_to_run = []
        for job in self.jobs:
            job.selected_titles.clear()
            item = job._gui_item
            if not item:
                continue

            for i in range(item.childCount()):
                child = item.child(i)
                if child.checkState(0) == Qt.CheckState.Checked:
                    title_data = child.data(0, Qt.ItemDataRole.UserRole)
                    job.selected_titles.add(int(title_data['title']))

            if job.selected_titles:
                jobs_to_run.append(job)

        if not jobs_to_run:
            self.log_box.append("No titles selected for processing.")
            return

        # Create and start processing thread
        self.processing_thread = ProcessingThread(
            jobs_to_run,
            self.config,
            self.config_manager.get_temp_dir()
        )

        self.processing_thread.log.connect(self.log_box.append)
        self.processing_thread.title_progress.connect(self.on_title_progress)
        self.processing_thread.queue_progress.connect(
            lambda cur, tot: self.overall_progress_bar.setValue(int(cur / tot * 100) if tot > 0 else 0)
        )
        self.processing_thread.processing_finished.connect(self.on_processing_finished)

        self.processing_thread.start()
        self.set_controls_enabled()

    def on_title_progress(self, job, percent):
        """Update progress bar for a specific job."""
        if item := job._gui_item:
            if pbar := self.queue_tree.itemWidget(item, 5):
                pbar.setValue(percent)

    def on_processing_finished(self):
        """Handle processing completion."""
        self.processing_thread = None
        self.set_controls_enabled()
        self.overall_progress_bar.setValue(0)

        # Reset progress bars
        for job in self.jobs:
            if item := job._gui_item:
                if pbar := self.queue_tree.itemWidget(item, 5):
                    pbar.setValue(0)

        self.log_box.append("\n=== Processing Complete ===\n")

    def stop_processing(self):
        """Stop current processing."""
        # Stop analysis threads
        for thread in self.active_analysis_threads:
            thread.stop()

        # Stop processing thread
        if self.processing_thread:
            self.log_box.append("[ACTION] Stop requested...")
            self.processing_thread.stop()
            self.processing_thread.wait(5000)  # Wait up to 5 seconds
            self.processing_thread = None

    def _on_item_checked(self, item, column):
        """Handle item check state changes."""
        if self._updating_checks:
            return

        self._updating_checks = True
        try:
            if item.parent():
                self._set_parent_check_from_children(item.parent())
            else:
                for i in range(item.childCount()):
                    item.child(i).setCheckState(0, item.checkState(0))
        finally:
            self._updating_checks = False

    def _set_parent_check_from_children(self, parent_item):
        """Update parent check state based on children."""
        child_count = parent_item.childCount()
        if child_count == 0:
            parent_item.setCheckState(0, Qt.CheckState.Unchecked)
            return

        checked_count = sum(1 for i in range(child_count) if parent_item.child(i).checkState(0) == Qt.CheckState.Checked)

        if checked_count == 0:
            parent_item.setCheckState(0, Qt.CheckState.Unchecked)
        elif checked_count == child_count:
            parent_item.setCheckState(0, Qt.CheckState.Checked)
        else:
            parent_item.setCheckState(0, Qt.CheckState.PartiallyChecked)

    def _on_item_selected(self, current, previous):
        """Handle item selection in queue tree."""
        if not current:
            self.details_panel.clear_panel()
            return

        if current.parent():
            title_data = current.data(0, Qt.ItemDataRole.UserRole)
            disc_job = current.parent().data(0, Qt.ItemDataRole.UserRole)
            self.details_panel.show_title_info(disc_job, title_data)
        else:
            job = current.data(0, Qt.ItemDataRole.UserRole)
            self.details_panel.show_disc_info(job)

    def open_prefs(self):
        """Open preferences dialog."""
        dialog = PrefsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config_manager.update(dialog.get_values())
            self.log_box.append("[INFO] Settings saved.")

    def clear_temp_files(self):
        """Clear temporary files."""
        self.config_manager.clean_temp_dir()
        self.log_box.append("[INFO] Temporary files cleared.")

    def show_about(self):
        """Show about dialog."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "About Media-Demuxer",
            "Media-Demuxer\n\n"
            "A powerful tool for demuxing DVD and Blu-ray media.\n\n"
            "DVD support: Complete\n"
            "Blu-ray support: Coming soon!"
        )

    def closeEvent(self, event):
        """Handle application close."""
        self.stop_processing()

        # Clean up temp files if configured
        if not self.config.get("keep_temp_files", False):
            try:
                self.config_manager.clean_temp_dir()
            except:
                pass

        event.accept()
