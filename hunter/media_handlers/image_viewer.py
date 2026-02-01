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


def _build_help_image():
    help_lines = [
        "Keyboard Shortcuts:",
        "  E  - Edges",
        "  C  - Clahe",
        "  F  - False Color",
        "  H  - High Pass",
        "  B  - Bilateral",
        "  M  - Median",
        "  D  - Detail Enhance",
        "  S  - Save",
        "  Q  - Quit"
    ]

    img = np.zeros((300, 400, 3), dtype=np.uint8)
    y = 20
    for line in help_lines:
        cv2.putText(img, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 0), 1, cv2.LINE_AA)
        y += 25

    return img


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


def _decode_cv2(raw_bytes):
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


class ImageViewer:
    def __init__(self, image_path_or_frame, source_uuid: uuid.UUID):
        self.image = None
        self.metadata = None
        self.original_bytes = None
        self.display_image = None
        self.source_uuid = source_uuid
        self.dragging = False
        self.ix = self.iy = 0
        self.fx = self.fy = 0
        self.zoom_factor = 2.0
        self._help_image = _build_help_image()
        self.help_visible = False

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
        self.metadata = extract_metadata(self.original_bytes)

        # Decode into cv2 image
        decoded_np = _decode_cv2(self.original_bytes)
        self.image = cv2.UMat(decoded_np)

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

    def _update_display_image(self):
        """Helper to resize self.image to fit screen dimensions."""
        try:
            # FIX: UMat doesn't have .shape.
            # We use .get() to fetch the CPU header to read dimensions.
            # (This is fast enough since we only do it once per filter change)
            (img_h, img_w) = self.image.get().shape[:2]

            monitor = get_monitors()[0]
            max_h = int(monitor.height * 0.90)
            max_w = int(monitor.width * 0.90)

            if img_h > max_h or img_w > max_w:
                ratio = min(max_w / float(img_w), max_h / float(img_h))
                new_dims = (int(img_w * ratio), int(img_h * ratio))

                # cv2.resize handles UMat automatically and returns a UMat
                self.display_image = cv2.resize(self.image, new_dims, interpolation=cv2.INTER_AREA)
            else:
                self.display_image = self.image
        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            self.display_image = self.image

    def show(self):
        """
        Shows the image in a self-contained OpenCV window.
        """
        if self.image is None:
            logger.error("No image to show.")
            return

        window_name = self.image_path  # Use path as window title

        # 1. SETUP ONCE: Initialize window and callback outside the loop
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, self._mouse_handler)

        # 2. RESIZE ONCE: Prepare the initial display image
        self._update_display_image()

        while True:
            # 3. DISPLAY LOOP
            # Copy the display image so we can draw the rectangle without permanent alteration
            img_to_show = cv2.copyTo(self.display_image, None)

            # If dragging, draw the green rectangle on this frame
            if self.dragging:
                cv2.rectangle(img_to_show, (self.ix, self.iy), (self.fx, self.fy), (0, 255, 0), 1)

            # Check if window was closed via X button
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                break

            cv2.imshow(window_name, img_to_show)

            key = cv2.waitKey(1) & 0xFF

            # Handle Help Window cleanup
            if self.help_visible and key != 255:
                cv2.destroyWindow("Help")
                self.help_visible = False

            if key == 255:
                continue

            key_char = chr(key)
            filter_applied = False

            match key_char:
                case 'q':
                    break

                case 's':
                    save_dir = "assets"
                    # Ensure directory exists
                    os.makedirs(save_dir, exist_ok=True)
                    image_name = f"{save_dir}/saved_image_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    self.save(image_name)
                    logger.info(f"Image saved to {image_name}")

                case 'e':
                    self.apply_filter("edges")
                    filter_applied = True
                case 'c':
                    self.apply_filter("clahe")
                    filter_applied = True
                case 'f':
                    self.apply_filter("false_color")
                    filter_applied = True
                case 'h':
                    self.apply_filter("high_pass")
                    filter_applied = True
                case 'b':
                    self.apply_filter("bilateral")
                    filter_applied = True
                case 'm':
                    self.apply_filter("median")
                    filter_applied = True
                case 'd':
                    self.apply_filter("detail_enhance")
                    filter_applied = True
                case _:
                    pass

            # 4. RE-CALCULATE ONLY IF NEEDED
            if filter_applied:
                self._update_display_image()

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
            logger.info(f"Image saved to {output_path}")
            db_manager.save_asset(asset)

    def _mouse_handler(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.dragging = True
            self.ix, self.iy = x, y
            self.fx, self.fy = x, y

        elif event == cv2.EVENT_MOUSEMOVE and self.dragging:
            # Only update coordinates.
            # The drawing happens in the main show() loop.
            self.fx, self.fy = x, y

        elif event == cv2.EVENT_LBUTTONUP:
            self.dragging = False
            self.fx, self.fy = x, y

            # Normalize coordinates
            x1, x2 = sorted([self.ix, self.fx])
            y1, y2 = sorted([self.iy, self.fy])

            # Map display coords → original image coords
            disp_h, disp_w = self.display_image.get().shape[:2]
            img_h, img_w = self.image.get().shape[:2]

            scale_x = img_w / disp_w
            scale_y = img_h / disp_h

            ox1 = int(x1 * scale_x)
            ox2 = int(x2 * scale_x)
            oy1 = int(y1 * scale_y)
            oy2 = int(y2 * scale_y)

            # UMat slicing requires strict Ranges: [start, end]
            # Note: Ranges must be integers
            roi = cv2.UMat(self.image, [oy1, oy2], [ox1, ox2])

            # UMat doesn't have .size property like numpy, check dimensions instead
            if roi.get().size == 0:  # or check roi.rows == 0 or roi.cols == 0
                return

            zoomed = cv2.resize(
                    roi,
                    None,
                    fx=self.zoom_factor,
                    fy=self.zoom_factor,
                    interpolation=cv2.INTER_LINEAR
            )
            cv2.imshow("Zoomed", zoomed)

        elif event == cv2.EVENT_RBUTTONDOWN:
            cv2.imshow("Help", self._help_image)
            self.help_visible = True

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
                original_image = self.display_image
                processed_image = module.apply(original_image)
                self.image = processed_image
                logger.debug(f"Successfully applied filter: {filter_name}")
            except Exception as e:
                logger.error(f"Failed to apply filter '{filter_name}': {e}")
        else:
            logger.error(f"Filter '{filter_name}' not found or has no 'apply' function.")