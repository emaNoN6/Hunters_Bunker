#  ==========================================================
#   Hunter's Command Console
#
#   File: high_pass.py
#   Last modified: 2025-11-16 17:46:34
#
#   Copyright (c) 2025 emaNoN & Codex
#
#  ==========================================================
#  ==========================================================
#   Filter: High-Pass
#   Usage: Shows only fine details, edges, and texture.
#          Useful for spotting anomalies.
#  ==========================================================
import cv2
import logging

logger = logging.getLogger(__name__)


def nothing(x):
	pass


def apply(img):
	"""
	Interactive High-Pass filter.
	Controls:
	  Kernel Size: How much of the "low frequency" info to remove.
				   Higher values = smoother image, so more is removed.
	  ENTER: Apply
	  ESC/X: Cancel
	"""

	window_name = "Adjust High-Pass (Enter=Save, Esc=Cancel)"
	cv2.namedWindow(window_name)

	# We'll make a slider from 0-30, then calculate (val*2)+1
	cv2.createTrackbar("Detail Level (Kernel)", window_name, 5, 30, nothing)

	result = img

	while True:
		# Read slider value
		k_val = cv2.getTrackbarPos("Detail Level (Kernel)", window_name)

		# Kernel size must be ODD and positive
		k_size = (k_val * 2) + 1

		# --- High-Pass Logic ---
		# 1. Create a low-pass (blurred) version of the image
		low_pass = cv2.GaussianBlur(img, (k_size, k_size), 0)

		# 2. Subtract the low-pass from the original.
		#    We add 128 to "center" the result around gray,
		#    which is the standard way to view a high-pass filter.
		overlay = cv2.addWeighted(img, 1.0, low_pass, -1.0, 128)
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
