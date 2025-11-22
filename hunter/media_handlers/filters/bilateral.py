#  ==========================================================
#   Hunter's Command Console
#
#   File: bilateral.py
#   Last modified: 2025-11-19 19:46:15
#
#   Copyright (c) 2025 emaNoN & Codex
#
#   Filter: Bilateral - Smart noise reduction that preserves edges
#  ==========================================================
import cv2
import logging

logger = logging.getLogger(__name__)


def nothing(x):
	pass


def apply(img):
	"""
	Interactive Bilateral Filter.
	Smooths noise while keeping edges sharp.
	Controls:
	  d: Diameter of pixel neighborhood (5-30)
	  Sigma Color: Color space filter (10-150)
	  Sigma Space: Coordinate space filter (10-150)
	  ENTER: Apply
	  ESC/X: Cancel
	"""
	window_name = "Adjust Bilateral (Enter=Save, Esc=Cancel)"
	cv2.namedWindow(window_name)

	# Trackbars
	cv2.createTrackbar("d", window_name, 9, 30, nothing)
	cv2.createTrackbar("Sigma Color", window_name, 75, 150, nothing)
	cv2.createTrackbar("Sigma Space", window_name, 75, 150, nothing)

	result = img

	while True:
		d = cv2.getTrackbarPos("d", window_name)
		sigma_color = cv2.getTrackbarPos("Sigma Color", window_name)
		sigma_space = cv2.getTrackbarPos("Sigma Space", window_name)

		# d must be odd and positive
		if d < 1:
			d = 1
		if d % 2 == 0:  # Make it odd
			d += 1

		# Apply bilateral filter
		overlay = cv2.bilateralFilter(img, d, sigma_color, sigma_space)

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
