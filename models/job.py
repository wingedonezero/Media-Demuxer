# models/job.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

@dataclass
class Job:
    """Represents a media source job to be processed."""
    source_path: Path
    source_type: str = "dvd"  # 'dvd' or 'bluray'
    group_name: Optional[str] = None
    base_name: str = ""
    status: str = "Queued"
    titles_info: list[dict] = field(default_factory=list)
    selected_titles: set[int] = field(default_factory=set)

    # Internal reference to GUI item
    _gui_item: Optional[Any] = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if not self.base_name:
            if self.source_path.is_dir() and self.source_path.name.lower() in ("video_ts", "bdmv"):
                self.base_name = self.source_path.parent.name
            else:
                self.base_name = self.source_path.stem
