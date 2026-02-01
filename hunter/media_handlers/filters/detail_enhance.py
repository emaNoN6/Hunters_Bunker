#  ==========================================================
#   Hunter's Command Console
#
#   File: filters/detail_enhance.py
#   Last modified: 2025-11-19
#   Updated for GPU/UMat Compatibility (Unsharp Mask)
#  ==========================================================
import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


def nothing(x):
	pass


def apply(img):
	"""
	Interactive Detail Enhancement (GPU Compatible).
	Uses Unsharp Masking (Gaussian Blur + Weighted Add) to sharpen details
	on the GPU without converting to CPU.
	"""

	# "Zombie Window" Fix: Use WINDOW_NORMAL
	window_name = "Adjust Detail (Enter=Save, Esc=Cancel)"
	cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

	# 1. Setup Sliders
	# "Radius": How large the details are (Sigma)
	# "Strength": How strong the sharpening is (Amount)
	cv2.createTrackbar("Radius", window_name, 3, 50, nothing)
	cv2.createTrackbar("Strength", window_name, 10, 100, nothing)  # 10 = 1.0

	result = img

	# --- LETTERBOX SETUP (Reuse from edges.py) ---
	min_width = 700
	img_h, img_w = img.get().shape[:2]

	pad_w = 0
	if img_w < min_width:
		pad_w = (min_width - img_w) // 2

	while True:
		# Check close before imshow
		if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1.0:
			result = img
			break

		# 2. Get Values
		r_val = cv2.getTrackbarPos("Radius", window_name)
		s_val = cv2.getTrackbarPos("Strength", window_name)

		# 3. Math for Unsharp Mask
		# Formula: Sharpened = Original + (Original - Blurred) * Amount
		# Rearranged: Original * (1 + Amount) + Blurred * (-Amount)

		# Ensure radius is odd for GaussianBlur
		sigma = r_val
		k_size = (sigma * 2) + 1
		if k_size < 1: k_size = 1

		amount = s_val / 10.0  # Range 0.0 -> 10.0

		# GPU Accelerated Blur
		blurred = cv2.GaussianBlur(img, (k_size, k_size), 0)

		# GPU Accelerated Weighted Add
		overlay = cv2.addWeighted(img, 1.0 + amount, blurred, -amount, 0)

		# --- DISPLAY LOGIC ---
		display_img = overlay

		if pad_w > 0:
			canvas = np.zeros((img_h, min_width, 3), dtype=np.uint8)
			display_umat = cv2.UMat(canvas)

			roi = cv2.UMat(display_umat, [0, img_h], [pad_w, pad_w + img_w])
			cv2.copyTo(overlay, None, roi)
			display_img = display_umat

		cv2.imshow(window_name, display_img)
		key = cv2.waitKey(10) & 0xFF

		if key == 27:  # ESC
			result = img
			break
		elif key == 13:  # ENTER
			result = overlay
			break

	try:
		cv2.destroyWindow(window_name)
	except Exception as e:
		pass

	return result