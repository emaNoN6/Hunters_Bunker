import threading
import time

import cv2
import numpy as np
import logging
from ffpyplayer.player import MediaPlayer

logger = logging.getLogger('Video Player')


class VideoPlayer:
	def __init__(self, video_path):
		self.video_path = video_path

		self.player = None

	def play(self):
		# Show loading window
		self._show_loading()

		# Initialize player
		headers = (
			"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\r\n"
		)
		self.player = MediaPlayer(self.video_path, ff_opts={'sync': 'audio', 'framedrop': True},
		                          lib_opts={'headers': headers, 'protocol_whitelist': 'file,http,https,tcp,tls,udp'})

		# Wait for stream to be ready (up to 10 sec)
		ready = False
		for i in range(100):
			meta = self.player.get_metadata()
			if meta.get('duration') is not None:
				logger.debug(f"Stream ready after {i * 0.1:.1f}s")
				ready = True
				break
			cv2.waitKey(100)

		if not ready:
			logger.warning("Stream timed out - playing anyway")

		no_frame_count = 0
		last_pts = -1
		stuck_count = 0

		# Main playback loop
		while True:
			frame, val = self.player.get_frame()

			if val == 'eof':
				break

			# val is sleep time in seconds (or 'eof'/'paused')
			if isinstance(val, (int, float)) and val > 0:
				time.sleep(val)

			if frame is not None:
				img, pts = frame

				# Check if we're stuck at the same timestamp
				if pts == last_pts:
					stuck_count += 1
					if stuck_count > 5:
						logger.debug(f"Stream stuck at pts={pts}, ending")
						break
				else:
					stuck_count = 0
					last_pts = pts

				arr = np.frombuffer(img.to_bytearray()[0], dtype=np.uint8)
				arr = arr.reshape((img.get_size()[1], img.get_size()[0], 3))
				arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
				cv2.imshow('Video', arr)

			key = cv2.waitKey(1) & 0xFF
			if key == ord('q'):
				break
			elif key == ord(' '):
				self.player.toggle_pause()

		self._cleanup()

	def _show_loading(self):
		loading_frame = np.zeros((200, 400, 3), dtype=np.uint8)
		cv2.putText(loading_frame, "Loading video...", (100, 100),
		            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
		cv2.imshow('Video', loading_frame)
		cv2.waitKey(1)

	def _cleanup(self):
		if self.player:
			threading.Thread(target=self.player.close_player, daemon=True).start()
			self.player = None
		cv2.destroyAllWindows()
