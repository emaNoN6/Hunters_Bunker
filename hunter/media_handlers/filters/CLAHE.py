#  ==========================================================
#   Hunter's Command Console
#
#   File: CLAHE.py
#   Last modified: 2025-11-16 17:39:46
#
#   Copyright (c) 2025 emaNoN & Codex
#
#  ==========================================================
#  ==========================================================
#   Filter: CLAHE (Contrast Limited Adaptive Histogram Equalization)
#   Usage: Brings out detail in shadows and highlights.
#  ==========================================================
import cv2
import logging

logger = logging.getLogger(__name__)


def nothing(x):
	# Dummy callback for trackbars
	pass


def apply(img):
	"""
	Interactive CLAHE filter.
	Controls:
	  Clip Limit: How much to boost contrast. (1-20 is a good range)
	  Grid Size:  Size of the area to analyze. (2-32 is a good range)
	  ENTER: Apply
	  ESC/X: Cancel
	"""

	window_name = "Adjust CLAHE (Enter=Save, Esc=Cancel)"
	cv2.namedWindow(window_name)

	# Create trackbars
	# Clip Limit (as float, so we divide by 10)
	cv2.createTrackbar("Clip Limit", window_name, 20, 100, nothing)  # 2.0
	# Grid Size (as integer)
	cv2.createTrackbar("Grid Size", window_name, 8, 32, nothing)  # 8x8

	result = img  # Default to cancel

	while True:
		# Read slider values
		clip_limit = cv2.getTrackbarPos("Clip Limit", window_name) / 10.0
		grid_size = cv2.getTrackbarPos("Grid Size", window_name)

		# Grid size must be at least 1
		if grid_size < 1:
			grid_size = 1

		# --- CLAHE Logic ---
		# 1. Convert to LAB color space
		lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

		# 2. Split channels
		l, a, b = cv2.split(lab)

		# 3. Create CLAHE object
		clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(grid_size, grid_size))

		# 4. Apply CLAHE to the L (Lightness) channel
		cl = clahe.apply(l)

		# 5. Merge channels back
		merged = cv2.merge((cl, a, b))

		# 6. Convert back to BGR
		overlay = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
		# --- End Logic ---

		cv2.imshow(window_name, overlay)

		key = cv2.waitKey(10) & 0xFF

		# Check for window close ('X')
		if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
			result = img
			break
		# Key Logic
		if key == 27:  # ESC
			result = img
			break
		elif key == 13:  # ENTER
			result = overlay
			break

	try:
		cv2.destroyWindow(window_name)
	except cv2.error as e:
		# This catches the error if the window was already closed (e.g., by 'X' button)
		logger.debug(f"Filter window '{window_name}' already closed, skipping destroy: {e}")
	except Exception as e:
		logger.warning(f"An unexpected error occurred during filter window destroy: {e}")

	return result
