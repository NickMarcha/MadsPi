import sys
import logging
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Ensure package root (src) is on sys.path when running this file directly
_package_root = Path(__file__).resolve().parents[1]
if str(_package_root) not in sys.path:
    sys.path.insert(0, str(_package_root))

# Import via package so relative imports in submodules work
from madspipeline.main_window import MainWindow

def main():
    # Configure logging: write to console and per-launch log file in `logs/`
    try:
        repo_root = Path(__file__).resolve().parents[2]
        log_dir = repo_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"madspipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # Redirect stdout/stderr to logger so print() also ends up in log file
        class StreamToLogger:
            def __init__(self, logger, level=logging.INFO):
                self.logger = logger
                self.level = level

            def write(self, buf):
                for line in buf.rstrip().splitlines():
                    self.logger.log(self.level, line.rstrip())

            def flush(self):
                pass

        sys.stdout = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
        sys.stderr = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR)

        logging.info("Starting MadsPipeline")
    except Exception:
        # Do not fail startup purely because logging setup had an unexpected error
        pass

    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("MadsPipeline")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("MadsPipeline")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
