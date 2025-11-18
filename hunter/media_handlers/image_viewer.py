#  ==========================================================
#   Hunter's Command Console
#
#   File: image_viewer.py
#   Purpose: Handles loading and viewing a single image
#  ==========================================================
import logging
import cv2
import numpy as np
import requests
from screeninfo import get_monitors

# Setup logger for this module
logger = logging.getLogger("ImageViewer")

# Import all filters you want to use (for the apply_filter sandbox)
from .filters import CLAHE, edges, false_color, high_pass


class ImageViewer:
	def __init__(self, image_path):
		logger.debug(f"loading image from {image_path}")
		self.image_path = image_path
		self.image = self._load_image()
		self.display_image = None

	def _load_image(self):
		"""Internal helper to load from URL or local file."""
		try:
			if self.image_path.startswith("http"):
				# Download the image
				response = requests.get(self.image_path)
				response.raise_for_status()
				# Convert the raw bytes into a NumPy array
				image_array = np.frombuffer(response.content, np.uint8)
				# Decode the array into an image
				return cv2.imdecode(image_array, cv2.IMREAD_COLOR)
			else:
				# It's a local file, read it directly
				image = cv2.imread(self.image_path)
				if image is None:
					raise FileNotFoundError(f"Image file not found or is invalid: {self.image_path}")
				return image
		except Exception as e:
			logger.error(f"Failed to load image: {e}")
			raise

	def show(self):
		"""
		Shows the image in a self-contained OpenCV window.
		Uses a "hot loop" (waitKey(1)) to prevent the
		OpenCV threading bug.
		"""
		if self.image is None:
			logger.error("No image to show.")
			return

		window_name = self.image_path  # Use path as window title

		# --- THIS IS THE FIX ---
		# We run a "hot loop" just like a video player,
		# but just show the same frame.
		while True:
			# --- Resize logic (from earlier) ---
			try:
				(img_h, img_w) = self.image.shape[:2]
				monitor = get_monitors()[0]
				max_h = int(monitor.height * 0.90)
				max_w = int(monitor.width * 0.90)

				self.display_image = self.image
				if img_h > max_h or img_w > max_w:
					ratio = min(max_w / float(img_w), max_h / float(img_h))
					new_dims = (int(img_w * ratio), int(img_h * ratio))
					self.display_image = cv2.resize(self.image, new_dims, interpolation=cv2.INTER_AREA)
			except Exception as e:
				logger.error(f"Error resizing image: {e}")
				self.display_image = self.image  # Show original on fail
			# --- End Resize logic ---

			cv2.imshow(window_name, self.display_image)

			# Wait 1ms. This keeps the event loop "hot".
			key = cv2.waitKey(1) & 0xFF

			# Check if user clicked 'X' on the window
			if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
				logger.debug("Window 'X' button clicked.")
				break

			# --- Hotkey Logic ---
			# Guard clause: 0xFF (255) is returned when no key is pressed
			if key == 255:
				continue

			key_char = chr(key)
			# Use match-case (Python 3.10+) for cleaner hotkeys
			match key_char:
				case 'q':  # 'q' to Quit
					logger.debug("'q' key pressed. Quitting.")
					break  # This breaks the while True loop

				case 's':  # 's' to Save
					# You'll want to implement a real save path
					self.save("saved_image.png")
					logger.info("Image saved to saved_image.png")

				# --- Filter Hotkeys ---
				case 'e':  # 'e' for Edges
					logger.debug("Applying 'edges' filter...")
					self.apply_filter("edges")
				case 'c':  # 'c' for CLAHE
					logger.debug("Applying 'clahe' filter...")
					self.apply_filter("clahe")
				case 'f':  # 'f' for False Color
					logger.debug("Applying 'false_color' filter...")
					self.apply_filter("false_color")
				case 'h':  # 'h' for High-Pass
					logger.debug("Applying 'high_pass' filter...")
					self.apply_filter("high_pass")

				case _:
					# Other key pressed, do nothing
					pass

		# End of while loop
		logger.debug(f"[{self.image_path}] Window loop broken. Cleaning up.")
		try:
			cv2.destroyWindow(window_name)
		except cv2.error as e:
			# This catches the error if the window was already closed (e.g., by 'X' button)
			logger.debug(f"Filter window '{window_name}' already closed, skipping destroy: {e}")
		except Exception as e:
			logger.warning(f"An unexpected error occurred during filter window destroy: {e}")
		# We must call waitKey *one more time* after destroying
		# to allow OpenCV to process the destroy command.
		cv2.waitKey(1)

	def save(self, output_path):
		"""Saves the image to a file."""
		if self.image is not None:
			cv2.imwrite(output_path, self.image)
			logger.debug(f"Image saved to {output_path}")

	def apply_filter(self, filter_name):
		"""
		Applies a filter by dynamically running its 'apply' function.
		"""
		# Map filter names to their actual module (safer than exec)
		filter_map = {
			"edges":       edges,
			"clahe":       CLAHE,
			"false_color": false_color,
			"high_pass":   high_pass
		}

		module = filter_map.get(filter_name)

		if module and hasattr(module, 'apply'):
			try:
				# A filter might be cancelled, so it returns
				# the original image.
				original_image = self.display_image.copy()
				processed_image = module.apply(original_image)
				self.image = processed_image
				logger.debug(f"Successfully applied filter: {filter_name}")
			except Exception as e:
				logger.error(f"Failed to apply filter '{filter_name}': {e}")
		else:
			logger.error(f"Filter '{filter_name}' not found or has no 'apply' function.")
