# hunter/html_parsers/html_sanitizer.py

from bs4 import BeautifulSoup
from hunter import config_manager  # Use relative import

# --- GUI Configuration ---
GUI_CONFIG = config_manager.get_gui_config()
FONT_FAMILY = GUI_CONFIG.get("font_family", "Courier New")
FONT_SIZE = int(GUI_CONFIG.get("font_size", 14))
DARK_GRAY = GUI_CONFIG.get("dark_gray", "#2b2b2b")
TEXT_COLOR = GUI_CONFIG.get("text_color", "#E0E0E0")
ACCENT_COLOR = GUI_CONFIG.get("accent_color", "#A9D1F5")
LINK_VISITED_COLOR = GUI_CONFIG.get("link_visited_color", "#B2A2D4")

# This is our "Bunker Standard" stylesheet. It's now more powerful
# because tkinterweb can understand it correctly.
BUNKER_STYLESHEET = f"""
<style>
    body {{
        background-color: {DARK_GRAY};
        color: {TEXT_COLOR};
        font-family: "{FONT_FAMILY}", monospace;
        font-size: 40pt;
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
    """
    Takes raw HTML, strips it of all conflicting styles and scripts,
    and injects our standard stylesheet into the <head>.
    """
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, "html.parser")

    # Exorcism Ritual
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
    if body_content:
        body_inner_html = body_content.decode_contents()
    else:
        body_inner_html = soup.decode_contents()

    # Re-forge the document with a proper head and our stylesheet
    styled_html = f"""
    <html><head>{BUNKER_STYLESHEET}</head><body>{body_inner_html}</body></html>
    """

    return styled_html
