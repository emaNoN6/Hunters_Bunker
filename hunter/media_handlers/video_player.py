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

loggings = logging.getLogger("Video Player")


class VideoPlayer:
	def __init__(self, video_path):
		self.video_path = video_path
		self.video = cv2.VideoCapture(video_path)

	def play(self):
		global frame
		paused = False

		while self.video.isOpened():
			if not paused:
				success, frame = self.video.read()
				if not success:
					break

			cv2.namedWindow('Video', flags=cv2.WINDOW_GUI_NORMAL | cv2.WINDOW_AUTOSIZE)
			cv2.imshow('Video', frame)

			key = cv2.waitKeyEx(25 if not paused else 30)

			# Skip if no key was pressed (255 = timeout)
			if key == -1:
				continue

			# Debug: print the key code for any actual key press
			#			if key != 255:
			#				print(f"Key pressed: {key}")

			# For regular ASCII keys, mask to get the character code
			key_char = key & 0xFF

			if key_char == ord('q'):
				break
			elif key_char == ord('f'):
				self.extract_frame(int(self.video.get(cv2.CAP_PROP_POS_FRAMES)))
			elif key_char == ord('t'):
				self.generate_thumbnail(self.video_path, "thumbnail.jpg")
			elif key_char == ord(' '):
				# Toggle pause
				paused = not paused
				if paused:
					print("PAUSED - Use arrow keys (or 'a'/'d') to step frame-by-frame")
				else:
					print("RESUMED")

			# Frame stepping (only works when paused)
			# Arrow keys on Windows have these extended codes:
			# Left: 2424832, Right: 2555904, Up: 2490368, Down: 2621440
			elif paused:
				if key in [2555904, ord('d'), ord('D')]:  # Right arrow or 'd'
					# Step forward one frame
					success, frame = self.video.read()
					if not success:
						# Go back one frame so we don't break
						current_frame = self.video.get(cv2.CAP_PROP_POS_FRAMES)
						self.video.set(cv2.CAP_PROP_POS_FRAMES, max(0, current_frame - 1))

				elif key in [2424832, ord('a'), ord('A')]:  # Left arrow or 'a'
					# Step backward one frame
					current_frame = self.video.get(cv2.CAP_PROP_POS_FRAMES)
					# Go back 2 frames (current position is already 1 ahead)
					new_frame = max(0, current_frame - 2)
					self.video.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
					success, frame = self.video.read()
					if not success:
						logging.error("Could not read frame")

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
