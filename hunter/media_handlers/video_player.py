#  ==========================================================
#   Hunter's Command Console
#
#   File: video_player.py
#   Last modified: 2025-11-08 15:40:14
#
#   Copyright (c) 2025 emaNoN & Codex
#
#  ==========================================================

import cv2
import os
import logging
import numpy as np
from .image_viewer import ImageViewer

loggings = logging.getLogger("Video Player")


class VideoPlayer:
	def __init__(self, video_path):
		self.video_path = video_path
		self.video = cv2.VideoCapture(video_path)

	def show_controls_help(self):
		"""Create a static window showing keyboard controls"""
		help_window = np.zeros((300, 450, 3), dtype=np.uint8)

		cv2.putText(help_window, "VIDEO PLAYER CONTROLS",
		            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

		controls = [
			"SPACE - Pause/Resume",
			"A / <- - Step Back (paused)",
			"D / -> - Step Forward (paused)",
			"S - Save Current Frame",
			"T - Generate Thumbnail",
			"F - Apply Denoise (paused)",
			"Q - Quit"
		]

		y_pos = 70
		for control in controls:
			cv2.putText(help_window, control,
			            (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
			y_pos += 30

		cv2.imshow('Controls', help_window)

	def play(self):
		self.show_controls_help()  # Show controls window once

		paused = False
		status_message = ""
		status_timer = 0

		# Get FPS for timing messages
		fps = self.video.get(cv2.CAP_PROP_FPS)
		if fps == 0 or fps is None:
			fps = 30  # Default fallback

		frame = None

		cv2.namedWindow('Video', flags=cv2.WINDOW_GUI_NORMAL | cv2.WINDOW_AUTOSIZE)
		total_frames = int(self.video.get(cv2.CAP_PROP_FRAME_COUNT))
		cv2.createTrackbar('Progress', 'Video', 0, total_frames, lambda x: None)

		while self.video.isOpened():
			if not paused:
				success, frame = self.video.read()
				if not success:
					break

			# Make a copy for overlay (don't modify original)
			display_frame = frame.copy() if frame is not None else frame

			if display_frame is not None:
				# Always show status
				frame_num = int(self.video.get(cv2.CAP_PROP_POS_FRAMES))
				# Check if user moved trackbar before updating it
				new_pos = cv2.getTrackbarPos('Progress', 'Video')
				if abs(new_pos - frame_num) > 1:  # User moved it
					self.video.set(cv2.CAP_PROP_POS_FRAMES, new_pos)
					success, frame = self.video.read()
					if success:
						display_frame = frame.copy()
					frame_num = new_pos
				else:
					# Update trackbar to current position
					cv2.setTrackbarPos('Progress', 'Video', frame_num)

				status = "PAUSED" if paused else "PLAYING"
				cv2.putText(display_frame, f"{status} | Frame: {frame_num}",
				            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

				# Show temporary messages
				if status_timer > 0:
					cv2.putText(display_frame, status_message,
					            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
					if not paused:
						status_timer -= 1

				cv2.checkHardwareSupport(cv2.CPAUD)
				cv2.imshow('Video', display_frame)

			key = cv2.waitKeyEx(25 if not paused else 30)

			if key == -1:
				continue

			key_char = key & 0xFF

			if key_char == ord('q'):
				break
			elif key_char == ord('s'):
				frame_num = int(self.video.get(cv2.CAP_PROP_POS_FRAMES))
				self.extract_frame(frame_num)
				status_message = f"Frame {frame_num} saved!"
				status_timer = int(fps)
			elif key_char == ord('t'):
				self.generate_thumbnail(self.video_path, "thumbnail.jpg")
				status_message = "Thumbnail saved!"
				status_timer = int(fps)
			elif key_char == ord(' '):
				paused = not paused
				status_message = "PAUSED" if paused else "RESUMED"
				status_timer = int(fps)

			elif paused:
				if key in [2555904, ord('d'), ord('D')]:
					success, frame = self.video.read()
					if not success:
						current_frame = self.video.get(cv2.CAP_PROP_POS_FRAMES)
						self.video.set(cv2.CAP_PROP_POS_FRAMES, max(0, current_frame - 1))
					status_message = "Stepped forward"
					status_timer = int(fps)

				elif key in [2424832, ord('a'), ord('A')]:
					current_frame = self.video.get(cv2.CAP_PROP_POS_FRAMES)
					new_frame = max(0, current_frame - 2)
					self.video.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
					success, frame = self.video.read()
					if not success:
						logging.error("Could not read frame")
					status_message = "Stepped back"
					status_timer = int(fps)

				elif key in [ord('f'), ord('F')]:
					if frame is not None:
						denoised = cv2.fastNlMeansDenoisingColored(
								frame, None,
								h=10,
								hColor=10,
								templateWindowSize=7,
								searchWindowSize=21
						)
						cv2.imshow('Denoised', denoised)
						cv2.waitKey()
						try:
							cv2.destroyWindow('Denoised')
						except cv2.error as e:
							pass
						status_message = "Denoise applied"
						status_timer = int(fps)

				elif key in [ord('i'), ord('I')]:
					if frame is not None:
						viewer = ImageViewer(frame.copy())  # Pass frame directly
						viewer.show()
						status_message = "Image filters applied"
						status_timer = int(fps)

		self.video.release()
		cv2.destroyAllWindows()
	def extract_frame(self, frame_number):
		# Save current position
		current_pos = self.video.get(cv2.CAP_PROP_POS_FRAMES)

		# Get the requested frame
		self.video.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
		success, frame = self.video.read()

		if success:
			filename = f"frame_{int(frame_number):05d}.jpg"
			cv2.imwrite(filename, frame)
			print(f"Frame {int(frame_number)} saved as {filename}")
		else:
			print("Frame not found.")

		# Restore position
		self.video.set(cv2.CAP_PROP_POS_FRAMES, current_pos)

	@staticmethod
	def generate_thumbnail(video_path, output_path):
		thumbnail = None
		cap = cv2.VideoCapture(video_path)
		ret, thumb_frame = cap.read()
		if ret:
			# Resize to thumbnail size
			thumbnail = cv2.resize(thumb_frame, (320, 240))
			cv2.imwrite(output_path, thumbnail)
			print(f"Thumbnail saved to {output_path}")
		cap.release()
		return thumbnail

	@staticmethod
	def apply_filter(filter_name):
		filter_path = os.path.join(os.path.dirname(__file__), "filters", f"{filter_name}.py")
		if os.path.exists(filter_path):
			with open(filter_path, "r") as f:
				code = f.read()
				exec(code)

	def sharpen_filter_3_x_3(self, image):
		"""
		Apply sharpening using kernel
		"""
		kernel3 = np.array([[0, -1, 0],
		                    [-1, 5, -1],
		                    [0, -1, 0]])
		sharp_img = cv2.filter2D(src=image, ddepth=-1, kernel=kernel3)

		cv2.imshow('Original', image)
		cv2.imshow('Sharpened', sharp_img)

		cv2.waitKey()
		cv2.imwrite('sharp_image.jpg', sharp_img)
		cv2.destroyAllWindows()

	def sharpen_filter_5_x_5(self, image):
		"""
		Apply sharpening using kernel
		"""
		kernel3 = np.array([[1, 4, 6, 4, 1],
		                    [4, 16, 24, 16, 4],
		                    [6, 24, 36, 24, 6],
		                    [4, 16, 24, 16, 4],
		                    [1, 4, 6, 4, 1]])
		sharp_img = cv2.filter2D(src=image, ddepth=-1, kernel=kernel3)

		cv2.imshow('Original', image)
		cv2.imshow('Sharpened', sharp_img)

		cv2.waitKey()
		cv2.imwrite('sharp_image.jpg', sharp_img)
		cv2.destroyAllWindows()

	def unsharpen_filter(self, image):
		"""
		Apply sharpening using kernel
		"""
		kernel3 = np.array([[1, 4, 6, 4, 1],
		                    [4, 16, 24, 16, 4],
		                    [6, 24, -476, 24, 6],
		                    [4, 16, 24, 16, 4],
		                    [1, 4, 6, 4, 1]])
		sharp_img = cv2.filter2D(src=image, ddepth=-1, kernel=kernel3)

		cv2.imshow('Original', image)
		cv2.imshow('Sharpened', sharp_img)

		cv2.waitKey()
		cv2.imwrite('sharp_image.jpg', sharp_img)
		cv2.destroyAllWindows()
