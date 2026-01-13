
import os
import time
import re
from PySide6.QtCore import QThread, Signal

class StatusMonitor(QThread):
    """
    Monitor thread that watches log files and database for updates.
    """
    progress_updated = Signal(float, str, str)  # percent, status, eta
    metrics_updated = Signal(float, int, float) # score, allocations, improvement
    
    def __init__(self, log_file="pipeline_run.log", progress_file="PROGRESS.txt"):
        super().__init__()
        self.log_file = log_file
        self.progress_file = progress_file
        self.running = True
        self.start_time = None  # Track when monitoring started
        
    def run(self):
        import time
        self.start_time = time.time()
        
        while self.running:
            try:
                self._check_logs()
                # self._check_database() # TODO: Implement DB polling
            except Exception as e:
                print(f"Monitor error: {e}")
            
            time.sleep(0.5)  # Check every 0.5 seconds
            
    def stop(self):
        self.running = False
        self.wait()
        
    def _check_logs(self):
        import time
        
        # 1. Parse PROGRESS.txt for high-level status
        status = None  # Will be set based on conditions
        percent = 0.0
        eta = "--"
        
        # Grace period: Don't show "Idle" in first 5 seconds
        time_since_start = time.time() - self.start_time if self.start_time else 0
        in_grace_period = time_since_start < 5.0
        
        # Check staleness: if file hasn't been updated in 30 seconds, it's not running
        is_stale = False
        if os.path.exists(self.progress_file):
            mtime = os.path.getmtime(self.progress_file)
            if time.time() - mtime > 30: # 30 seconds threshold
                is_stale = True
        
        if os.path.exists(self.progress_file) and not is_stale:
            with open(self.progress_file, 'r') as f:
                content = f.read()
                
                # Extract Status
                m_status = re.search(r"Status: (.*)", content)
                if m_status:
                    status = m_status.group(1).strip()
                    
                # Extract Progress
                m_prog = re.search(r"Current Progress: ([\d.]+)%", content)
                if m_prog:
                    percent = float(m_prog.group(1))
                    
                # Extract ETA
                m_eta = re.search(r"ETA: (.*)", content)
                if m_eta:
                    eta = m_eta.group(1).strip()
        
        # If we found it was stale, explicitly mark as stopped if it looked like it was running
        if is_stale:
            status = "Stopped (Stale)"
            # Use percent=0 only if previously 0, otherwise keep last known percent but show stopped?
            # Actually, user prefers not seeing "Running".
            if percent > 0 and percent < 100:
                 status = f"Stopped at {percent}%"
        
        # Set default status if not set yet
        if status is None:
            if in_grace_period:
                status = "Starting..."
            else:
                status = "Idle"
                    
        # 2. Parse pipeline_run.log for more granular details (fallback)
        if percent == 0 and os.path.exists(self.log_file) and not is_stale:
            # Read last few lines
            try:
                with open(self.log_file, 'r') as f:
                    # Seek to end
                    f.seek(0, 2)
                    size = f.tell()
                    # Read last 2KB
                    f.seek(max(0, size - 2048))
                    lines = f.readlines()
                    
                    for line in reversed(lines):
                        # Look for progress bar pattern: [███...] 50.3%
                        if "%" in line and "|" in line:
                            m = re.search(r"([\d.]+)%", line)
                            if m:
                                percent = float(m.group(1))
                                status = "Running (Log)"
                                break
            except Exception:
                pass
                
        self.progress_updated.emit(percent, status, eta)

    def _check_database(self):
        # Placeholder for DB checking logic
        # Would query 'optimization_results' table for max(objective_value)
        pass
