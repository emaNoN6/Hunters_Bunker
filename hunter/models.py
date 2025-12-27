# ==========================================================
# Hunter's Command Console - Definitive Data Models
# Copyright (c) 2025, M. Stilson & Codex
#
# This file serves as the single source of truth for the
# data structures passed between different parts of the app.
# ==========================================================
import base64
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Any, Dict, List
from logging import getLogger

logger = getLogger(__name__)

# ==========================================================
# METADATA BLUEPRINTS
# These provide the structure and validation for the 'metadata' field
# in the main LeadData object. This solves the "what keys are in there"
# problem by creating a formal, validated contract for each source's
# unique data points.
# ==========================================================

@dataclass
class RedditMedia:
	"""A validated container for Reddit-specific media information."""
	url: Optional[str] = None
	type: Optional[str] = None
	duration: Optional[int] = None

@dataclass
class RedditMetadata:
	"""A validated container for Reddit-specific metadata."""
	score: Optional[int] = None
	author: Optional[str] = None
	subreddit: Optional[str] = None
	num_comments: Optional[int] = None
	post_id: Optional[str] = None
	is_self: Optional[bool] = None  # Indicates if a post is a text-only "self" post.

@dataclass
class GNewsMetadata:
	"""A validated container for GNews.io-specific metadata."""
	# GNews.io provides a 'source' object with its own details.
	# We capture them here to maintain a complete record.
	# Including a link to the original article, and an image URL.
	article_url: Optional[str] = None
	article_image: Optional[str] = None
	source_name: Optional[str] = None
	source_url: Optional[str] = None


# ==========================================================
# THE MASTER FIELD REPORT (LEAD DATA)
# ==========================================================

@dataclass
class LeadData:
	"""
	The one, standardized, universal container for a piece of intel (a lead).
	This object is the standard format for all data passed from the foremen
	to the rest of the application pipeline. It includes built-in validation
	to ensure data integrity at the point of creation.
	"""
	# === Universal Fields (MUST be provided by every source) ===
	title: str
	url: str
	source_name: str  # The high-level source name, e.g., "Reddit" or "GNews.io"
	publication_date: datetime

	# === Content Fields (at least one of these SHOULD be present) ===
	text: Optional[str] = None
	html: Optional[str] = None

	# === Optional Universal Metadata ===
	image_url: Optional[str] = None

	# === The Cargo Hold for Source-Specific Extras ===
	# This field will hold a validated metadata object, like an instance
	# of RedditMetadata or GNewsMetadata.
	metadata: Optional[Dict[str, Any]] = field(default_factory=dict)

	# === Internal Tracking (added later in the pipeline) ===
	lead_uuid: Optional[str] = None

	def __post_init__(self):
		"""
		Performs validation automatically after the object has been initialized.
		This is our primary defense against bad data entering the pipeline.
		It will "fail loud and fail fast" if a contract is violated.
		"""
		# 1. Check that required string fields are not empty or just whitespace
		if not self.title or not self.title.strip():
			raise ValueError("LeadData 'title' cannot be empty.")
		if not self.url or not self.url.strip():
			raise ValueError("LeadData 'url' cannot be empty.")
		if not self.source_name or not self.source_name.strip():
			raise ValueError("LeadData 'source_name' cannot be empty.")

		# 2. Check that we have at least one form of content
		if (not self.text or not self.text.strip()) and \
				(not self.html or not self.html.strip()):
			raise ValueError("LeadData must have either 'text' or 'html' content.")


@dataclass
class SourceConfig:
	"""Configuration and state for a content source."""
	# === Identity ===
	id: int  # Database PK from sources table
	source_name: str
	agent_type: str
	target: str
	domain_id: int
	purpose: str

	# === State Tracking ===
	is_active: bool
	consecutive_failures: int
	last_checked_date: Optional[datetime] = None
	last_success_date: Optional[datetime] = None
	last_failure_date: Optional[datetime] = None
	last_known_item_id: Optional[str] = None

	# === Configuration ===
	strategy: Optional[str] = None
	keywords: Optional[str] = None
	next_release_date: Optional[datetime] = None
	has_standard_foreman: bool = True


@dataclass
class Asset:
	"""Represents a media/document asset"""
	asset_id: Optional[str] = None
	file_path: Optional[str] = None
	file_type: Optional[str] = 'unknown'  # 'image', 'video', 'audio', 'document'
	mime_type: Optional[str] = None
	file_size: Optional[int] = None
	created_at: Optional[datetime] = None

	source_type: Optional[str] = None  # 'lead', 'case', 'investigation', 'manual'
	source_uuid: Optional[uuid.UUID] = None
	original_url: Optional[str] = None

	related_cases: Optional[List[uuid.UUID]] = None
	related_investigations: Optional[List[uuid.UUID]] = None

	is_enhanced: Optional[Dict] = None

	notes: Optional[str] = None
	metadata: Optional[Dict] = None

	# Class-level constants for validation
	VALID_FILE_TYPES = {'image', 'video', 'audio', 'document', 'unknown'}
	VALID_SOURCE_TYPES = {'lead', 'case', 'investigation', 'manual'}

	def __post_init__(self):
		"""Initialize defaults and validate"""
		# Initialize empty collections
		if self.related_cases is None:
			self.related_cases = []
		if self.related_investigations is None:
			self.related_investigations = []
		if self.metadata is None:
			self.metadata = {}

		# Normalize and validate file_type
		if self.file_type:
			self.file_type = self.file_type.lower()
			if self.file_type not in self.VALID_FILE_TYPES:
				logger.error(f"Invalid file_type: {self.file_type}. Must be one of {self.VALID_FILE_TYPES}")
				raise ValueError(f"Invalid file_type: {self.file_type}")

		# Normalize and validate source_type
		if self.source_type:
			self.source_type = self.source_type.lower()
			if self.source_type not in self.VALID_SOURCE_TYPES:
				logger.error(f"Invalid source_type: {self.source_type}. Must be one of {self.VALID_SOURCE_TYPES}")
				raise ValueError(f"Invalid source_type: {self.source_type}")


@dataclass
class ImageMetadata:
	mime: Optional[str]
	format: Optional[str]
	width: int
	height: int
	mode: Optional[str]
	dpi: Optional[tuple]
	exif: Optional[Dict]
	icc_profile: Optional[bytes]

	def to_dict(self):
		d = asdict(self)
		if self.icc_profile:
			d["icc_profile"] = base64.b64encode(self.icc_profile).decode("ascii")
		if self.exif:
			# EXIF values can be bytes, need to handle those too
			d["exif"] = {k: v if not isinstance(v, bytes) else base64.b64encode(v).decode("ascii")
			             for k, v in self.exif.items()}
		return d

# ==========================================================
# METADATA REHYDRATION MAP
# This is the crucial directory that allows the db_manager to
# intelligently reconstruct the correct metadata object when
# pulling data from the database.
# ==========================================================

METADATA_CLASS_MAP = {
	'GNews.io':          GNewsMetadata,
	'Reddit Ghosts':     RedditMetadata,
	'Reddit Paranormal': RedditMetadata,
	# Add new source names and their corresponding metadata classes here
}

# Extra fields that should only appear if populated.
METADATA_EXTRA_FIELDS = {
	'Reddit Ghosts':     ['flair', 'media'],
	'Reddit Paranormal': ['flair', 'media'],
	# Other sources probably don't have extra fields
}
