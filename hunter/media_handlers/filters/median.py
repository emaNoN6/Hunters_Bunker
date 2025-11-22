#  ==========================================================
#   Hunter's Command Console
#
#   File: median.py
#   Last modified: 2025-11-19 19:47:11
#
#   Copyright (c) 2025 emaNoN & Codex
#
##   Filter: Median Blur - Removes salt & pepper noise
#  ==========================================================
import cv2
import logging

logger = logging.getLogger(__name__)


def nothing(x):
	pass


def apply(img):
	"""
	Interactive Median Blur Filter.
	Removes speckle noise while preserving edges.
	Controls:
	  Kernel Size: Size of blur (1-31, odd numbers only)
	  ENTER: Apply
	  ESC/X: Cancel
	"""
	window_name = "Adjust Median Blur (Enter=Save, Esc=Cancel)"
	cv2.namedWindow(window_name)

	# Trackbar (will be converted to odd numbers)
	cv2.createTrackbar("Kernel Size", window_name, 5, 31, nothing)

	result = img

	while True:
		k_size = cv2.getTrackbarPos("Kernel Size", window_name)

		# Must be odd and at least 1
		if k_size < 1:
			k_size = 1
		if k_size % 2 == 0:  # Make it odd
			k_size += 1

		# Apply median blur
		overlay = cv2.medianBlur(img, k_size)

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
		logger.debug(f"Filter window '{window_name}' already closed, skipping destroy: {e}")
	except Exception as e:
		logger.warning(f"An unexpected error occurred during filter window destroy: {e}")

	return result
