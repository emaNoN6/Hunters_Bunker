import json
import os
import logging
from hunter.models import SourceConfig

logger = logging.getLogger("TestDataAgent")


def hunt(source: SourceConfig, credentials: dict):
	"""
	Mock agent that reads leads from a local JSON file.
	"""
	# FIX: Access attribute directly from SourceConfig dataclass
	# The dispatcher passes a SourceConfig object, not a dict.
	target_file = source.target

	logger.info(f"[{source.source_name}]: Mocking hunt from file: {target_file}")

	if not os.path.exists(target_file):
		logger.error(f"[{source.source_name}]: Test data file not found at: {target_file}")
		return [], None

	try:
		with open(target_file, 'r', encoding='utf-8') as f:
			data = json.load(f)

		logger.info(f"[{source.source_name}]: Loaded {len(data)} items from disk.")

		# If the file contains a list, return it.
		# If it has a 'leads' key, return that.
		if isinstance(data, list):
			return data, None
		elif isinstance(data, dict) and 'leads' in data:
			return data['leads'], None

		return [], None

	except Exception as e:
		logger.error(f"[{source.source_name}]: Failed to load test data: {e}")
		return [], None