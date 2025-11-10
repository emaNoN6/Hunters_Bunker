#  ==========================================================
#   Hunter's Command Console
#
#   File: image_viewer.py
#   Last modified: 2025-11-08 15:07:24
#
#   Copyright (c) 2025-2025 emaNoN & Codex
#
#  ==========================================================
import os

from PIL import Image


class ImageViewer:
	def __init__(self, image_path):
		self.image_path = image_path

	def show(self):
		image = Image.open(self.image_path)
		image.show()

	def save(self, output_path):
		image = Image.open(self.image_path)
		image.save(output_path)

	def thumbnail(self, output_path):
		image = Image.open(self.image_path)
		image.thumbnail((320, 240))

	def apply_filter(self, filter_name):
		filter_path = os.path.join(os.path.dirname(__file__), "filters", f"{filter_name}.py")
		with open(filter_path, "r") as f:
			code = f.read()
			exec(code)

	def apply_filters(self, filter_names):
		for filter_name in filter_names:
			self.apply_filter(filter_name)
