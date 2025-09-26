# core/config.py
import json
import os
from pathlib import Path

# Default configuration values
DEFAULTS = {
    "default_output_directory": "",
    "minimum_title_length": 120,

    # Processing options
    "remove_eia_608": True,
    "run_ccextractor": True,
    "ffmpeg_trim_padding": True,
    "keep_metadata_json": False,
    "keep_temp_files": False,

    # Track naming options
    "audio_track_names": True,
    "subtitle_track_names": True,
    "cc_track_names": True,

    # Timing method
    "timing_method": "auto",  # auto, pgc, pts, ffprobe

    # Error handling
    "auto_fix_sync": True,
    "auto_fix_chapters": True,
    "skip_damaged_sectors": True,
    "continue_on_error": False,

    # Telecine detection options
    "telecine_detection_mode": "disabled",  # disabled, auto, force_progressive, force_interlaced
    "telecine_threshold": 85,
    "telecine_sample_duration": 60,
}

class ConfigManager:
    """Manages application configuration with JSON persistence."""

    def __init__(self):
        # Get the application directory (where the script is located)
        self.app_dir = Path(__file__).parent.parent
        self.config_file = self.app_dir / 'config.json'
        self.temp_dir = self.app_dir / 'temp'

        # Set default output directory if not set
        if not DEFAULTS["default_output_directory"]:
            DEFAULTS["default_output_directory"] = str(Path.home() / "Media-Demuxer-Output")

        self.config = self.load_config()
        self._ensure_dirs_exist()

    def _ensure_dirs_exist(self):
        """Creates necessary directories."""
        self.temp_dir.mkdir(exist_ok=True)
        output_dir = Path(self.config["default_output_directory"])
        output_dir.mkdir(parents=True, exist_ok=True)

    def load_config(self) -> dict:
        """Loads configuration from JSON file, creating with defaults if needed."""
        if not self.config_file.exists():
            print(f"Config file not found. Creating with defaults at: {self.config_file}")
            self.save_config(DEFAULTS)
            return DEFAULTS.copy()

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # Merge with defaults to ensure all keys exist
                for key, default_value in DEFAULTS.items():
                    if key not in loaded:
                        loaded[key] = default_value
                return loaded
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading config: {e}. Using defaults.")
            return DEFAULTS.copy()

    def save_config(self, config_dict=None):
        """Saves configuration to JSON file."""
        if config_dict is None:
            config_dict = self.config

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=4)
            self.config = config_dict
        except IOError as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        """Get a config value."""
        return self.config.get(key, default)

    def set(self, key, value):
        """Set a config value."""
        self.config[key] = value

    def update(self, updates: dict):
        """Update multiple config values."""
        self.config.update(updates)
        self.save_config()

    def get_temp_dir(self) -> Path:
        """Get the temporary directory path."""
        return self.temp_dir

    def clean_temp_dir(self):
        """Clean the temporary directory."""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(exist_ok=True)
