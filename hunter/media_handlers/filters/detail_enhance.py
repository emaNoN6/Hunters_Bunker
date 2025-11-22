#  ==========================================================
#   Hunter's Command Console
#
#   File: detail_enhance.py
#   Last modified: 2025-11-19 19:47:54
#
#   Copyright (c) 2025 emaNoN & Codex
#
#   Filter: Detail Enhance - Sharpens textures and patterns
#  ==========================================================
import cv2
import logging

logger = logging.getLogger(__name__)


def nothing(x):
	pass


def apply(img):
	"""
	Interactive Detail Enhancement Filter.
	Makes textures and fine details more visible.
	Controls:
	  Sigma S: Spatial filter (5-200)
	  Sigma R: Range filter (0.0-1.0)
	  ENTER: Apply
	  ESC/X: Cancel
	"""
	window_name = "Adjust Detail Enhance (Enter=Save, Esc=Cancel)"
	cv2.namedWindow(window_name)

	# Trackbars (sigma_r will be divided by 100 to get 0.0-1.0 range)
	cv2.createTrackbar("Sigma S", window_name, 10, 200, nothing)
	cv2.createTrackbar("Sigma R x100", window_name, 15, 100, nothing)

	result = img

	while True:
		sigma_s = cv2.getTrackbarPos("Sigma S", window_name)
		sigma_r = cv2.getTrackbarPos("Sigma R x100", window_name) / 100.0

		# Ensure minimum values
		if sigma_s < 1:
			sigma_s = 1
		if sigma_r < 0.01:
			sigma_r = 0.01

		# Apply detail enhancement
		overlay = cv2.detailEnhance(img, sigma_s=float(sigma_s), sigma_r=float(sigma_r))

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
