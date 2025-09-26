# core/orchestrator.py
from pathlib import Path
from .dvd_orchestrator import DVDOrchestrator

class MasterOrchestrator:
    """
    Master orchestrator that delegates to specific sub-orchestrators
    based on the source type (DVD, Blu-ray, etc.)
    """

    def __init__(self, config, temp_dir: Path):
        self.config = config
        self.temp_dir = temp_dir

        # Initialize sub-orchestrators
        self.dvd_orchestrator = DVDOrchestrator(config, temp_dir)
        # Future: self.bluray_orchestrator = BlurayOrchestrator(config, temp_dir)

    def analyze_disc(self, path: Path, source_type: str, log_emitter, stop_event) -> tuple[list, str]:
        """
        Analyze a disc by delegating to the appropriate sub-orchestrator.

        Args:
            path: Path to the disc/ISO
            source_type: Type of source ('dvd' or 'bluray')
            log_emitter: Function to emit log messages
            stop_event: Threading event to stop processing

        Returns:
            Tuple of (titles list, message string)
        """
        if source_type == 'dvd':
            return self.dvd_orchestrator.analyze_disc(path, log_emitter, stop_event)
        elif source_type == 'bluray':
            # Future implementation
            log_emitter("Blu-ray support coming soon!")
            return [], "Blu-ray analysis not yet implemented"
        else:
            return [], f"Unknown source type: {source_type}"

    def run_pipeline(self, context: dict, log_emitter, stop_event):
        """
        Run the processing pipeline by delegating to the appropriate sub-orchestrator.

        Args:
            context: Processing context with source_type, paths, etc.
            log_emitter: Function to emit log messages
            stop_event: Threading event to stop processing

        Yields:
            Progress updates (0-100)
        """
        source_type = context.get('source_type', 'dvd')

        if source_type == 'dvd':
            yield from self.dvd_orchestrator.run_pipeline(context, log_emitter, stop_event)
        elif source_type == 'bluray':
            # Future implementation
            log_emitter("Blu-ray processing coming soon!")
            yield 100
        else:
            log_emitter(f"Unknown source type: {source_type}")
            yield 100
