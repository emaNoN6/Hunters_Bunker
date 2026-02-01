#  ==========================================================
#   Hunter's Command Console
#
#   File: filters/edges.py
#   Last modified: 2025-11-16
#   Updated for GPU/UMat Compatibility
#  ==========================================================
import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


def nothing(x):
	pass


def apply(img):
	"""
	Interactive Edge Detection Filter (GPU Compatible).
	"""

	# 1. Pre-process
	# cv2 functions work fine on UMat automatically
	gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
	blurred = cv2.GaussianBlur(gray, (5, 5), 0)

	# FIX 1: 'addWeighted' requires two UMats.
	# Instead of making a new black UMat, we just use 'img' as the second source
	# but multiply it by 0.0.
	# Formula: img * 0.5 + img * 0.0 + 0
	dimmed = cv2.addWeighted(img, 0.5, img, 0.0, 0)

	window_name = "Adjust Edges (Enter=Save, Esc=Cancel)"
	cv2.namedWindow(window_name)

	cv2.createTrackbar("Threshold 1", window_name, 50, 255, nothing)
	cv2.createTrackbar("Threshold 2", window_name, 150, 255, nothing)

	use_white = True
	result = img  # Default to cancel

	# 3. The Loop
	while True:
		t1 = cv2.getTrackbarPos("Threshold 1", window_name)
		t2 = cv2.getTrackbarPos("Threshold 2", window_name)

		edges = cv2.Canny(blurred, t1, t2)

		# Create base overlay (deep copy)
		overlay = cv2.copyTo(dimmed, None)

		color = (255, 255, 255) if use_white else (0, 0, 0)

		# --- FIX START: The "Stencil" Method ---

		# 1. Create a "Solid Color" UMat on the GPU
		#    (Take the overlay, multiply by 0 to get black, then add the color scalar)
		solid_color_umat = cv2.addWeighted(overlay, 0, overlay, 0, 0)
		solid_color_umat = cv2.add(solid_color_umat, color)

		# 2. Apply the "paint" using the edge mask
		#    This is the GPU equivalent of: overlay[edges > 0] = color
		cv2.copyTo(solid_color_umat, edges, overlay)

		# --- FIX END ---

		cv2.imshow(window_name, overlay)

		key = cv2.waitKey(10) & 0xFF

		if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1.0:
			result = img
			break

		if key == 27:  # ESC
			result = img
			break
		elif key == 13:  # ENTER
			result = overlay
			break
		elif key == ord('t'):
			use_white = not use_white
	try:
		cv2.destroyWindow(window_name)
	except Exception as e:
		pass

	return result