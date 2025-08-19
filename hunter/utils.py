# hunter/utils.py

import queue
import threading
import time

def console_log_consumer(log_queue: queue.Queue):
    """
    A simple worker function that runs in a thread, pulling
    log messages from a queue and printing them to the console.
    """
    while True:
        try:
            # Wait for a message to appear in the queue
            message = log_queue.get(timeout=1)
            print(message)
            log_queue.task_done()
        except queue.Empty:
            # If the queue is empty, just continue waiting
            continue
        except Exception as e:
            print(f"[LOG CONSUMER ERROR]: {e}")

def start_console_log_consumer(log_queue: queue.Queue):
    """
    Starts the console log consumer in a background daemon thread.
    """
    consumer_thread = threading.Thread(
        target=console_log_consumer,
        args=(log_queue,),
        daemon=True # Daemon thread will exit when the main script finishes
    )
    consumer_thread.start()
    return consumer_thread