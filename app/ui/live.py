import threading
import time
from typing import Callable, Optional
from app.llm_engine.hybrid import HybridCompiler
from app.llm_engine.schemas import WorkerResponse

class LiveModeManager:
    def __init__(self, root, on_result: Callable[[WorkerResponse], None], on_start: Callable[[], None], on_error: Callable[[str], None]):
        self.root = root  # Tkinter root for thread-safe callbacks
        self.on_result = on_result
        self.on_start = on_start
        self.on_error = on_error
        self.compiler: Optional[HybridCompiler] = None
        self._timer: Optional[threading.Timer] = None
        self._last_text = ""
        self._lock = threading.Lock()
        self._latest_request_id = 0
        self.enabled = False
        # Initialize lazily or pass in constructor

    def set_compiler(self, compiler: HybridCompiler):
        self.compiler = compiler

    def schedule(self, text: str, delay_ms: int = 1500):
        if not self.enabled:
            return
        
        # Critical: Error out if compiler not initialized, don't silently return
        if not self.compiler:
            self.root.after(0, lambda: self.on_error("HybridCompiler not initialized. Check API Key."))
            return

        text = text.strip()
        if text == self._last_text:
            return
        
        self._last_text = text
        
        with self._lock:
            if self._timer:
                self._timer.cancel()
            
            # Start debounce timer
            self._timer = threading.Timer(delay_ms / 1000.0, self._worker, args=[text])
            self._timer.start()

    def _worker(self, text: str):
        # Generate a request ID to handle race conditions
        with self._lock:
            self._latest_request_id += 1
            current_id = self._latest_request_id
        
        # Notify UI: Thinking...
        self.root.after(0, self.on_start)

        try:
            if not self.compiler:
                 raise RuntimeError("Compiler not initialized")

            # Run Hybrid Compiler (Slow)
            response = self.compiler.compile(text)

            # Check if this is still the latest request
            with self._lock:
                if current_id != self._latest_request_id:
                    # Stale result, ignore
                    return

            # Update UI on main thread
            self.root.after(0, lambda: self.on_result(response))
        
        except Exception as e:
            with self._lock:
                if current_id != self._latest_request_id:
                    return
            self.root.after(0, lambda err=e: self.on_error(str(err)))
