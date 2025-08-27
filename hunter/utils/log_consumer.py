# ==========================================================
# Hunter's Command Console - Log Consumer Utility
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import threading
import queue

def _console_log_consumer(log_queue):
    """The worker function that pulls messages from the queue and prints them."""
    while True:
        try:
            message = log_queue.get()
            if message is None:
                break
            print(message)
            log_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            print(f"[LOG_CONSUMER_ERROR]: {e}")

def start_console_log_consumer(log_queue):
    """Starts the log consumer thread."""
    consumer_thread = threading.Thread(target=_console_log_consumer, args=(log_queue,), daemon=True)
    consumer_thread.start()
    return consumer_thread

def stop_console_log_consumer(consumer_thread):
    """Stops the log consumer thread."""
    consumer_thread.join()
