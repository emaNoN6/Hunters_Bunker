#  ==========================================================
#   Hunter's Command Console
#
#   File: false_color.py
#   Last modified: 2025-11-16 17:45:37
#
#   Copyright (c) 2025 emaNoN & Codex
#
#  ==========================================================
#  ==========================================================
#   Filter: False Color (Heatmap)
#   Usage: Applies a colormap to brightness levels to show
#          subtle variations.
#  ==========================================================
import cv2
import logging

logger = logging.getLogger(__name__)


def nothing(x):
	pass


def apply(img):
	"""
	Interactive False Color filter.
	Controls:
	  Colormap: Which heatmap to use (0-21)
	  Intensity: How much to blend the heatmap (0-100%)
	  ENTER: Apply
	  ESC/X: Cancel
	"""

	window_name = "Adjust False Color (Enter=Save, Esc=Cancel)"
	cv2.namedWindow(window_name)

	# OpenCV has 22 colormaps
	cv2.createTrackbar("Colormap", window_name, 0, 21, nothing)
	# Blend intensity (0-100%)
	cv2.createTrackbar("Intensity", window_name, 50, 100, nothing)

	result = img
	gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  # Need grayscale for this

	while True:
		# Read slider values
		colormap_index = cv2.getTrackbarPos("Colormap", window_name)
		intensity_percent = cv2.getTrackbarPos("Intensity", window_name)

		# Convert intensity to alpha/beta for blending
		alpha = intensity_percent / 100.0  # Heatmap's strength
		beta = 1.0 - alpha  # Original image's strength

		# --- False Color Logic ---
		# 1. Apply the colormap to the grayscale image
		heatmap = cv2.applyColorMap(gray, colormap_index)

		# 2. Blend the original image with the heatmap
		overlay = cv2.addWeighted(img, beta, heatmap, alpha, 0)
		# --- End Logic ---

		cv2.imshow(window_name, overlay)

		key = cv2.waitKey(10) & 0xFF

		if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
			result = img
			break
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
