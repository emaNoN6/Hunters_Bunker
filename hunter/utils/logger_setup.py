# ==========================================================
# Hunter's Command Console - Centralized Logger Setup
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import logging
import sys
import queue
from colorlog import ColoredFormatter
from .. import config_manager  # Use relative import


class QueueHandler(logging.Handler):
	"""
	A custom logging handler that puts messages into a queue,
	used to safely pass log messages to the GUI.
	"""

	def __init__(self, log_queue):
		super().__init__()
		self.log_queue = log_queue

	def emit(self, record):
		self.log_queue.put(self.format(record))


def setup_logging():
	"""
	Configures the root logger for the entire application based on settings
	in config.ini. Returns the queue for the GUI handler.
	"""
	log_config = config_manager.get_logging_config()
	log_queue = queue.Queue()

	# --- Configure the Root Logger ---
	# Set the root logger's level to the most verbose level we might use.
	# The handlers will then filter messages down from here.
	root_logger = logging.getLogger()

	if root_logger.hasHandlers():
		# Find the existing QueueHandler to return its queue
		for handler in root_logger.handlers:
			if isinstance(handler, QueueHandler):
				return handler.log_queue
		# If for some reason there's no queue handler, create a dummy one
		return queue.Queue()

	root_logger.setLevel(logging.DEBUG)

	# --- Console Handler (with color!) ---
	if log_config.get('enable_console_logging', 'true').lower() == 'true':
		console_formatter = ColoredFormatter(
				'%(log_color)s[%(levelname)-8s]%(reset)s %(blue)s[%(name)-15.15s]%(reset)s %(message)s',
				log_colors={
					'DEBUG':    'cyan',
					'INFO':     'green',
					'WARNING':  'yellow',
					'ERROR':    'red',
					'CRITICAL': 'red,bg_white',
				}
		)
		console_handler = logging.StreamHandler(sys.stdout)
		console_handler.setFormatter(console_formatter)
		console_level = log_config.get('log_level_console', 'DEBUG').upper()
		console_handler.setLevel(getattr(logging, console_level, logging.DEBUG))
		root_logger.addHandler(console_handler)

	# --- File Handler ---
	if log_config.get('enable_file_logging', 'true').lower() == 'true':
		file_formatter = logging.Formatter(
				'%(asctime)s [%(levelname)-8s] [%(name)-20.20s] [%(funcName)s:%(lineno)d] %(message)s'
		)
		file_handler = logging.FileHandler("bunker.log")
		file_handler.setFormatter(file_formatter)
		file_level = log_config.get('log_level_file', 'INFO').upper()
		file_handler.setLevel(getattr(logging, file_level, logging.INFO))
		root_logger.addHandler(file_handler)

	# --- GUI Handler (via Queue) ---
	if log_config.get('enable_gui_logging', 'true').lower() == 'true':
		gui_formatter = logging.Formatter('[%(levelname)s] [%(name)s] %(message)s')
		gui_handler = QueueHandler(log_queue)
		gui_handler.setFormatter(gui_formatter)
		gui_level = log_config.get('log_level_gui', 'INFO').upper()
		gui_handler.setLevel(getattr(logging, gui_level, logging.INFO))
		root_logger.addHandler(gui_handler)

	ignore_libs = {'urllib3', 'prawcore', 'praw'}
	for lib in ignore_libs:
		logging.getLogger(lib).setLevel(logging.ERROR)

	# Return the queue so the GUI can consume it
	return log_queue
