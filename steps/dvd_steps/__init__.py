# steps/dvd_steps/__init__.py
"""DVD-specific processing steps."""

# Note: The actual step files would be renamed versions of the original files
# with DVD prefix. Since they're too large to recreate here, you would:
# 1. Move all current step files to steps/dvd_steps/
# 2. Rename them with dvd_ prefix (e.g., demux.py -> dvd_demux.py)
# 3. Update class names to have DVD prefix (e.g., DemuxStep -> DVDDemuxStep)

# For now, create placeholder imports that would work after renaming:

from .dvd_demux import DVDDemuxStep
from .dvd_ccextract import DVDCCExtractStep
from .dvd_chapters import DVDChaptersStep
from .dvd_finalize import DVDFinalizeStep
from .dvd_disc_analysis import DVDDiscAnalysisStep
from .dvd_metadata_analysis import DVDMetadataAnalysisStep
from .dvd_telecine_detection import DVDTelecineDetectionStep
from .dvd_ifo_parser import DVDIfoParserStep
from .dvd_timing_analysis import DVDTimingAnalysisStep
from .dvd_chapter_normalization import DVDChapterNormalizationStep

__all__ = [
    "DVDDemuxStep",
    "DVDCCExtractStep",
    "DVDChaptersStep",
    "DVDFinalizeStep",
    "DVDDiscAnalysisStep",
    "DVDMetadataAnalysisStep",
    "DVDTelecineDetectionStep",
    "DVDIfoParserStep",
    "DVDTimingAnalysisStep",
    "DVDChapterNormalizationStep",
]
