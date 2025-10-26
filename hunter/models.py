# ==========================================================
# Hunter's Command Console - Definitive Data Models
# Copyright (c) 2025, M. Stilson & Codex
#
# This file serves as the single source of truth for the
# data structures passed between different parts of the app.
# ==========================================================

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any, Dict


# ==========================================================
# METADATA BLUEPRINTS
# These provide the structure and validation for the 'metadata' field
# in the main LeadData object. This solves the "what keys are in there"
# problem by creating a formal, validated contract for each source's
# unique data points.
# ==========================================================

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
