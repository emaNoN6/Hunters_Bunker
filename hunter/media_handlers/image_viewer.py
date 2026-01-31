#  ==========================================================
#   Hunter's Command Console
#
#   File: image_viewer.py
#   Purpose: Handles loading and viewing a single image
#  ==========================================================
import datetime
import logging
import os
import sys
import uuid

import cv2
import numpy as np
import requests
from io import BytesIO
from PIL import Image
from screeninfo import get_monitors
from hunter.models import Asset, ImageMetadata

from .. import db_manager

# Setup logger for this module
logger = logging.getLogger("ImageViewer")

# Import all filters (for the apply_filter sandbox)
from .filters import CLAHE, edges, false_color, high_pass, bilateral, median, detail_enhance

if sys.platform == "win32":
    import magic

    magic.Magic()

class ImageViewer:
    def __init__(self, image_path_or_frame, source_uuid: uuid.UUID):
        self.image = None
        self.metadata = None
        self.original_bytes = None
        self.display_image = None
        self.source_uuid = source_uuid

        # Case 1: Already a NumPy frame (video)
        if isinstance(image_path_or_frame, np.ndarray):
            self.image_path = "Video Frame"
            self.image = image_path_or_frame
            return

        # Case 2: File path or URL
        logger.debug(f"loading image from {image_path_or_frame}")
        self.image_path = image_path_or_frame

        # Load raw bytes FIRST
        self.original_bytes = self._load_raw_bytes()

        # Extract metadata BEFORE OpenCV touches the image
        self.metadata = self.extract_metadata(self.original_bytes)

        # Decode into cv2 image
        self.image = self._decode_cv2(self.original_bytes)

    def _load_raw_bytes(self):
        """Load raw bytes from URL or local file."""
        try:
            if self.image_path.startswith("http"):
                response = requests.get(self.image_path)
                response.raise_for_status()
                return response.content
            else:
                with open(self.image_path, "rb") as f:
                    return f.read()
        except Exception as e:
            logger.error(f"Failed to load raw bytes: {e}")
            raise

    def _decode_cv2(self, raw_bytes):
        """Decode raw bytes into an OpenCV image."""
        try:
            arr = np.frombuffer(raw_bytes, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("cv2.imdecode returned None")
            return img
        except Exception as e:
            logger.error(f"Failed to decode image: {e}")
            raise

    @staticmethod
    def extract_metadata(raw_bytes: bytes) -> ImageMetadata:
        """Extract metadata from raw image bytes using Pillow + python-magic."""
        mime = magic.from_buffer(raw_bytes, mime=True)
        img = Image.open(BytesIO(raw_bytes))

        return ImageMetadata(
                mime=mime,
                format=img.format,
                width=img.width,
                height=img.height,
                mode=img.mode,
                dpi=img.info.get("dpi"),
                exif=dict(img.getexif()) if hasattr(img, "getexif") else None,
                icc_profile=img.info.get("icc_profile")
        )

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

        while True:
            # Resize logic
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
                self.display_image = self.image

            cv2.imshow(window_name, self.display_image)

            key = cv2.waitKey(1) & 0xFF

            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                logger.debug("Window 'X' button clicked.")
                break

            if key == 255:
                continue

            key_char = chr(key)

            match key_char:
                case 'q':
                    logger.debug("'q' key pressed. Quitting.")
                    break

                case 's':
                    save_dir = "assets"
                    image_name = f"{save_dir}/saved_image_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    self.save(image_name)
                    logger.info(f"Image saved to {image_name}")

                case 'e':
                    self.apply_filter("edges")
                case 'c':
                    self.apply_filter("clahe")
                case 'f':
                    self.apply_filter("false_color")
                case 'h':
                    self.apply_filter("high_pass")
                case 'b':
                    self.apply_filter("bilateral")
                case 'm':
                    self.apply_filter("median")
                case 'd':
                    self.apply_filter("detail_enhance")

                case _:
                    pass

        logger.debug(f"[{self.image_path}] Window loop broken. Cleaning up.")
        try:
            cv2.destroyWindow(window_name)
        except Exception as e:
            pass
        cv2.waitKey(1)

    def save(self, output_path):
        """Saves the image to a file."""
        if self.image is not None:
            cv2.imwrite(output_path, self.image)
            file_size = os.path.getsize(output_path)
            asset = Asset(
                    source_uuid=self.source_uuid if self.source_uuid else None,
                    file_path=output_path,
                    file_type="image",
                    mime_type="image/png",
                    file_size=file_size,
                    related_cases=[self.source_uuid] if self.source_uuid else [],
                    metadata={
                        "image_metadata": self.metadata.to_dict() if self.metadata else None
                    }
            )
            logger.debug(f"Image saved to {output_path}")
            db_manager.save_asset(asset)

    def apply_filter(self, filter_name):
        """Applies a filter by dynamically running its 'apply' function."""
        filter_map = {
            "edges":          edges,
            "clahe":          CLAHE,
            "false_color":    false_color,
            "high_pass":      high_pass,
            "bilateral":      bilateral,
            "median":         median,
            "detail_enhance": detail_enhance
        }

        module = filter_map.get(filter_name)

        if module and hasattr(module, 'apply'):
            try:
                original_image = self.display_image.copy()
                processed_image = module.apply(original_image)
                self.image = processed_image
                logger.debug(f"Successfully applied filter: {filter_name}")
            except Exception as e:
                logger.error(f"Failed to apply filter '{filter_name}': {e}")
        else:
            logger.error(f"Filter '{filter_name}' not found or has no 'apply' function.")
