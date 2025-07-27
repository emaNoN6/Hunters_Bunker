#  ==========================================================
#  Hunter's Command Console
#  #
#  File: html_sanitizer.py
#  Last Modified: 7/27/25, 2:57 PM
#  Copyright (c) 2025, M. Stilson & Codex
#  #
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the MIT License.
#  #
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  LICENSE file for more details.
#  ==========================================================

# hunter/html_parsers/html_sanitizer.py

from bs4 import BeautifulSoup
from hunter import config_manager  # Use relative import to get the config

# --- GUI Configuration ---
GUI_CONFIG = config_manager.get_gui_config()
FONT_FAMILY = GUI_CONFIG.get("font_family", "Courier New")
HTML_FONT_SIZE = int(GUI_CONFIG.get("html_font_size_pt", 24))
DARK_GRAY = GUI_CONFIG.get("dark_gray", "#2b2b2b")
TEXT_COLOR = GUI_CONFIG.get("text_color", "#E0E0E0")
ACCENT_COLOR = GUI_CONFIG.get("accent_color", "#A9D1F5")
LINK_VISITED_COLOR = GUI_CONFIG.get("link_visited_color", "#B2A2D4")

# This is our "Bunker Standard" stylesheet.
BUNKER_STYLESHEET = f"""
<style>
    body {{
        background-color: {DARK_GRAY};
        color: {TEXT_COLOR};
        font-family: "{FONT_FAMILY}", monospace;
        font-size: {HTML_FONT_SIZE}pt;
        line-height: 1.6;
        margin: 15px;
    }}
    h1, h2, h3, h4, h5, h6 {{
        color: {ACCENT_COLOR};
        border-bottom: 1px solid #444;
        padding-bottom: 5px;
        margin-top: 20px;
    }}
    a, a:link {{ color: {ACCENT_COLOR}; text-decoration: none; }}
    a:visited {{ color: {LINK_VISITED_COLOR}; }}
    a:hover {{ text-decoration: underline; }}
    p {{ margin-bottom: 1em; }}
    blockquote {{
        border-left: 3px solid #666;
        padding-left: 15px;
        margin-left: 5px;
        color: #ccc;
        font-style: italic;
    }}
    pre, code {{
        background-color: #202020;
        padding: 10px;
        border-radius: 5px;
        white-space: pre-wrap;
    }}
</style>
"""


def sanitize_and_style(html_content, lead_title=""):
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    for tag in soup.find_all(True):
        if tag.has_attr("style"):
            del tag["style"]
    if lead_title:
        for h_tag in soup.find_all(["h1", "h2"]):
            if h_tag.get_text(strip=True).lower() == lead_title.lower():
                h_tag.decompose()
                break
    body_content = soup.find("body")
    body_inner_html = (
        body_content.decode_contents() if body_content else soup.decode_contents()
    )
    return (
        f"<html><head>{BUNKER_STYLESHEET}</head><body>{body_inner_html}</body></html>"
    )
