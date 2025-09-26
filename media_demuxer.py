#!/usr/bin/env python3
"""
Media-Demuxer - Standalone DVD/Blu-ray demuxing application
Main entry point for the application
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from gui.main_window import MainWindow

def main():
    """Application entry point."""
    # High DPI scaling is enabled by default in PyQt6, so the
    # AA_EnableHighDpiScaling and AA_UseHighDpiPixmaps attributes are obsolete.

    app = QApplication(sys.argv)
    app.setApplicationName("Media-Demuxer")
    app.setOrganizationName("MediaDemuxer")

    # Set application style
    app.setStyle("Fusion")

    # Create and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
