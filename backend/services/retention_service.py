import os
import time
import threading
import logging
from pathlib import Path

from backend.config.settings import settings
from backend.services.inference_service import STORAGE_DIR

logger = logging.getLogger(__name__)

_retention_thread = None
_stop_event = threading.Event()

def get_directory_size(path: Path) -> int:
    """Returns the total size of a directory in bytes."""
    total_size = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def _cleanup_worker():
    """Background thread to enforce storage limits and retention policies."""
    logger.info("Storage retention policy active: KEEP %d days, MAX %d GB.", 
                settings.RETENTION_DAYS, settings.MAX_STORAGE_GB)
                
    while not _stop_event.is_set():
        try:
            now = time.time()
            cutoff = now - (settings.RETENTION_DAYS * 86400)
            
            # Phase 1: Age-based cleanup
            deleted_count = 0
            for file_path in STORAGE_DIR.rglob('*'):
                if file_path.is_file():
                    stat = file_path.stat()
                    # Use modification time (or creation time where available)
                    if stat.st_mtime < cutoff:
                        file_path.unlink(missing_ok=True)
                        deleted_count += 1
            
            if deleted_count > 0:
                logger.info("Retention policy: deleted %d expired evidence files.", deleted_count)

            # Phase 2: Size-based cleanup (Emergency Cap)
            max_bytes = settings.MAX_STORAGE_GB * 1024 * 1024 * 1024
            current_size = get_directory_size(STORAGE_DIR)
            
            if current_size > max_bytes:
                logger.warning("Storage limit exceeded (%.2f GB / %d GB). Triggering emergency cleanup.", 
                               current_size / 1e9, settings.MAX_STORAGE_GB)
                
                # Gather all files with their mtime
                all_files = []
                for file_path in STORAGE_DIR.rglob('*'):
                    if file_path.is_file():
                        all_files.append((file_path, file_path.stat().st_mtime))
                
                # Sort by oldest first
                all_files.sort(key=lambda x: x[1])
                
                bytes_freed = 0
                files_removed = 0
                for file_path, _ in all_files:
                    size = file_path.stat().st_size
                    file_path.unlink(missing_ok=True)
                    bytes_freed += size
                    files_removed += 1
                    
                    if (current_size - bytes_freed) <= max_bytes:
                        break
                        
                logger.info("Emergency cleanup freed %.2f MB (%d files).", bytes_freed / 1e6, files_removed)

        except Exception as e:
            logger.exception("Error during storage retention cleanup.")
            
        # Sleep for 1 hour before checking again, interruptible by shutdown
        if _stop_event.wait(3600):
            break
            
    logger.info("Storage retention thread stopped.")

def start_retention_service():
    """Start the background retention task if enabled."""
    global _retention_thread
    if not settings.ENABLE_AUTO_CLEANUP:
        logger.info("Storage auto-cleanup is disabled.")
        return
        
    if _retention_thread is None or not _retention_thread.is_alive():
        _stop_event.clear()
        _retention_thread = threading.Thread(target=_cleanup_worker, daemon=True, name="RetentionService")
        _retention_thread.start()

def stop_retention_service():
    """Cleanly shutdown the retention thread."""
    global _retention_thread
    if _retention_thread and _retention_thread.is_alive():
        _stop_event.set()
        _retention_thread.join(timeout=2.0)
