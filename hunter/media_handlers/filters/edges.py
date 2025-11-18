#  ==========================================================
#   Hunter's Command Console
#
#   File: filters/edges.py
#   Last modified: 2025-11-16
#
#  ==========================================================
import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


def nothing(x):
	"""
	Dummy callback function.
	cv2.createTrackbar requires a function, even if it does nothing.
	"""
	pass


def apply(img):
	"""
	Interactive Edge Detection Filter.
	Controls:
	  't'   : Toggle Black/White edges
	  ENTER : Save and Apply
	  ESC   : Cancel (Return original)
	  'X'   : Cancel (Return original)
	  SLIDERS: Adjust Canny edge thresholds
	"""

	# 1. Pre-process (can be done once)
	gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
	blurred = cv2.GaussianBlur(gray, (5, 5), 0)
	dimmed = cv2.addWeighted(img, 0.5, np.zeros_like(img), 0.5, 0)

	window_name = "Adjust Edges (Enter=Save, Esc=Cancel)"
	cv2.namedWindow(window_name)

	# 2. CREATE THE TRACKBARS
	# We attach them to 'window_name'
	# Format: (SliderName, WindowName, StartValue, MaxValue, Callback)
	cv2.createTrackbar("Threshold 1", window_name, 50, 255, nothing)
	cv2.createTrackbar("Threshold 2", window_name, 150, 255, nothing)

	use_white = True
	result = img  # Default to cancel

	# 3. The Loop
	while True:
		# 4. READ SLIDER VALUES (every loop)
		# Format: (SliderName, WindowName)
		t1 = cv2.getTrackbarPos("Threshold 1", window_name)
		t2 = cv2.getTrackbarPos("Threshold 2", window_name)

		# 5. RE-CALCULATE EDGES (every loop)
		# This is the key: we use the live slider values
		edges = cv2.Canny(blurred, t1, t2)

		# --- (Rest of your logic is the same) ---

		# Draw logic
		overlay = dimmed.copy()
		color = (255, 255, 255) if use_white else (0, 0, 0)
		overlay[edges > 0] = color

		cv2.imshow(window_name, overlay)

		# Wait for input
		key = cv2.waitKey(10) & 0xFF

		# Check if user clicked 'X'
		if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1.0:
			result = img
			break
		# Key Logic
		if key == 27:  # ESC
			result = img
			break
		elif key == 13:  # ENTER
			result = overlay
			break
		elif key == ord('t'):
			use_white = not use_white

	# Cleanup
	try:
		cv2.destroyWindow(window_name)
	except cv2.error as e:
		# This catches the error if the window was already closed (e.g., by 'X' button)
		logger.debug(f"Filter window '{window_name}' already closed, skipping destroy: {e}")
	except Exception as e:
		logger.warning(f"An unexpected error occurred during filter window destroy: {e}")

	return result
