import sys
import logging
import os
import threading
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

        ch = logging.StreamHandler(sys.__stdout__)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # Capture native C-level stdout/stderr (e.g., OpenCV, pylsl native logs)
        try:
            # Create a pipe to capture FD writes
            r_fd, w_fd = os.pipe()

            # Save original fds for console
            orig_stdout_fd = os.dup(1)
            orig_stderr_fd = os.dup(2)

            # Duplicate write end of pipe onto stdout and stderr so native libs write into it
            os.dup2(w_fd, 1)
            os.dup2(w_fd, 2)

            # Open a binary file handle for the log file to write native bytes
            log_file_bin = open(log_file, 'ab', buffering=0)

            def _reader_thread(fd, orig_out_fd, logger_instance):
                """Read from pipe and write bytes to both original stdout and log file."""
                try:
                    with os.fdopen(fd, 'rb', closefd=True) as reader:
                        while True:
                            chunk = reader.read(1024)
                            if not chunk:
                                break
                            # Write to original console
                            try:
                                os.write(orig_out_fd, chunk)
                            except Exception:
                                pass
                            # Also write to the log file (binary)
                            try:
                                log_file_bin.write(chunk)
                                log_file_bin.flush()
                            except Exception:
                                pass
                            # Also log decoded text via logging to keep consistency
                            try:
                                text = chunk.decode('utf-8', errors='replace')
                                for line in text.rstrip().splitlines():
                                    logger_instance.info(line)
                            except Exception:
                                pass
                except Exception:
                    pass

            # Start reader thread to tee pipe contents
            t = threading.Thread(target=_reader_thread, args=(r_fd, orig_stdout_fd, logger), daemon=True)
            t.start()

        except Exception:
            # If FD-level redirect fails, fall back to Python-level redirection
            sys.stdout = logging.StreamHandler(sys.__stdout__)
            sys.stderr = logging.StreamHandler(sys.__stderr__)

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
