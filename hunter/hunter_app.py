#  ==========================================================
#  Hunter's Command Console
#  #
#  File: hunter_app.py
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

import customtkinter as ctk
import threading
import queue
import webbrowser
import os
import re
import time
import textwrap
from datetime import datetime
from PIL import Image
import tkinterweb

# --- Our Custom Tools ---
# These imports are now correct for our package structure.
from . import config_manager
from . import actions_news_search
from . import db_manager
from .custom_widgets.tooltip import CTkToolTip
from html_parsers import html_sanitizer, link_extractor

# --- GUI Configuration ---
# All theme settings are now loaded from the config file.
GUI_CONFIG = config_manager.get_gui_config()
FONT_FAMILY = GUI_CONFIG.get("font_family", "Courier New")
FONT_SIZE = int(GUI_CONFIG.get("font_size", 14))
DARK_BG = GUI_CONFIG.get("dark_bg", "#242424")
DARK_GRAY = GUI_CONFIG.get("dark_gray", "#2b2b2b")
ACCENT_COLOR = GUI_CONFIG.get("accent_color", "#A9D1F5")
TEXT_COLOR = GUI_CONFIG.get("text_color", "#E0E0E0")
ERROR_COLOR = GUI_CONFIG.get("error_color", "#FF6B6B")
SUCCESS_COLOR = GUI_CONFIG.get("success_color", "#6BFFB8")
WARNING_COLOR = GUI_CONFIG.get("warning_color", "#FFD700")
TIMESTAMP_COLOR = GUI_CONFIG.get("timestamp_color", "gray70")
LINK_VISITED_COLOR = GUI_CONFIG.get("link_visited_color", "#B2A2D4")


class HunterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Window Setup ---
        self.title("Hunter's Command Console")
        self.geometry("800x600")
        self.configure(fg_color=DARK_BG)

        # --- Font Definitions ---
        self.main_font = ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE)
        self.bold_font = ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE, weight="bold")
        self.button_font = ctk.CTkFont(
            family=FONT_FAMILY, size=FONT_SIZE + 2, weight="bold"
        )

        # --- Database Connection Check ---
        if not db_manager.check_database_connection():
            error_label = ctk.CTkLabel(
                self,
                text="FATAL ERROR: Could not connect to PostgreSQL database.",
                font=self.bold_font,
                text_color="red",
            )
            error_label.pack(expand=True)
            return

        # --- Main Layout ---
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=5)
        self.grid_rowconfigure(0, weight=1)

        self.left_frame = ctk.CTkFrame(self, fg_color=DARK_GRAY)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        self.left_frame.grid_rowconfigure(1, weight=1)

        self.right_frame = ctk.CTkFrame(self, fg_color=DARK_GRAY)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.right_frame.grid_rowconfigure(0, weight=1)

        self.build_triage_desk()
        self.build_dossier_viewer()

        self.triage_items = []
        self.log_queue = queue.Queue()
        self.after(100, self.process_log_queue)
        self.after(200, self._run_startup_checks)

    def build_triage_desk(self):
        title_label = ctk.CTkLabel(
            self.left_frame,
            text="Triage Desk",
            font=self.bold_font,
            text_color=TEXT_COLOR,
        )
        title_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.scrollable_frame = ctk.CTkScrollableFrame(
            self.left_frame, fg_color=DARK_GRAY
        )
        self.scrollable_frame.grid(
            row=1, column=0, sticky="nsew", padx=10, pady=(0, 10)
        )
        self.bottom_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.bottom_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        self.bottom_frame.grid_columnconfigure(0, weight=1)
        self.bottom_frame.grid_columnconfigure(1, weight=1)
        self.search_button = ctk.CTkButton(
            self.bottom_frame,
            text="Search for New Cases",
            command=self.start_search_thread,
            font=self.button_font,
        )
        self.search_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.confirm_button = ctk.CTkButton(
            self.bottom_frame,
            text="Confirm & File Selected",
            command=self.confirm_triage_action,
            font=self.button_font,
        )
        self.confirm_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def build_dossier_viewer(self):
        self.tab_view = ctk.CTkTabview(self.right_frame, fg_color=DARK_BG)
        self.tab_view.pack(expand=True, fill="both", padx=10, pady=10)
        self.tab_view.add("Dossier")
        self.tab_view.add("Operations Log")
        self.detail_frame = self.tab_view.tab("Dossier")
        self.log_frame = self.tab_view.tab("Operations Log")
        self.log_textbox = ctk.CTkTextbox(
            self.log_frame,
            font=self.main_font,
            wrap="word",
            fg_color=DARK_BG,
            text_color=TEXT_COLOR,
        )
        self.log_textbox.pack(expand=True, fill="both")
        self.log_textbox.tag_config("INFO", foreground=ACCENT_COLOR)
        self.log_textbox.tag_config("SUCCESS", foreground=SUCCESS_COLOR)
        self.log_textbox.tag_config("ERROR", foreground=ERROR_COLOR)
        self.log_textbox.tag_config("WARNING", foreground=WARNING_COLOR)
        self.log_textbox.tag_config("TIMESTAMP", foreground=TIMESTAMP_COLOR)
        self.log_textbox.configure(state="disabled")

    def start_search_thread(self):
        self.log_message("[APP]: Hunter dispatch requested...")
        self.search_button.configure(state="disabled")
        threading.Thread(target=self.run_search, daemon=True).start()

    def run_search(self):
        if config_manager.is_debug_mode():
            self.log_message(
                "[APP DEBUG]: Running in debug mode. Fetching test cases from archive..."
            )
            results = db_manager.get_random_cases_for_testing(20)
        else:
            self.log_message("[APP]: Hunter dispatched. Searching for new cases...")
            results = actions_news_search.search_all_sources(self.log_queue)
        self.after(0, self.populate_triage_list, results)
        self.after(0, lambda: self.search_button.configure(state="normal"))
        if not config_manager.is_debug_mode():
            self.log_message("[APP]: All agents have returned.")

    def populate_triage_list(self, results):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.triage_items.clear()
        grouped_results = {}
        for lead in results:
            source = lead.get("source", "Unknown Source")
            if source not in grouped_results:
                grouped_results[source] = []
            grouped_results[source].append(lead)
        for source, leads in grouped_results.items():
            header = ctk.CTkFrame(
                self.scrollable_frame, fg_color=DARK_GRAY, cursor="hand2"
            )
            header.pack(fill="x", pady=(5, 1), padx=2)
            lead_count = len(leads)
            plural_s = "s" if lead_count != 1 else ""
            label_text = f"▶ {source} ({lead_count} new lead{plural_s})"
            header_label = ctk.CTkLabel(
                header,
                text=label_text,
                font=self.bold_font,
                anchor="w",
                text_color=TEXT_COLOR,
            )
            header_label.pack(side="left", padx=10, pady=5)
            content_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
            header._is_expanded = False
            header.bind(
                "<Button-1>",
                lambda e, h=header, c=content_frame, l=leads: self._toggle_source_group(
                    h, c, l
                ),
            )
            header_label.bind(
                "<Button-1>",
                lambda e, h=header, c=content_frame, l=leads: self._toggle_source_group(
                    h, c, l
                ),
            )

    def _toggle_source_group(self, header, content_frame, leads):
        header_label = header.winfo_children()[0]
        if header._is_expanded:
            content_frame.pack_forget()
            header_label.configure(text=header_label.cget("text").replace("▼", "▶"))
            header._is_expanded = False
        else:
            header_label.configure(text=header_label.cget("text").replace("▶", "▼"))
            content_frame.pack(fill="x", padx=2, after=header)
            header._is_expanded = True
            if not content_frame.winfo_children():
                self._create_lead_widgets(content_frame, leads)

    def _create_lead_widgets(self, parent_frame, leads):
        tooltip_x = int(GUI_CONFIG.get("tooltip_x_offset", 20))
        tooltip_y = int(GUI_CONFIG.get("tooltip_y_offset", 10))
        case_border = GUI_CONFIG.get("case_border_color", "#006600")
        case_fg = GUI_CONFIG.get("case_fg_color", "#008800")
        case_hover = GUI_CONFIG.get("case_hover_color", "#00AA00")
        not_case_border = GUI_CONFIG.get("not_case_border_color", "#660000")
        not_case_fg = GUI_CONFIG.get("not_case_fg_color", "#880000")
        not_case_hover = GUI_CONFIG.get("not_case_hover_color", "#AA0000")
        corner_radius = int(GUI_CONFIG.get("corner_radius", 4))

        for lead_data in leads:
            item_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
            item_frame.pack(fill="x", pady=2, padx=10)
            decision_var = ctk.StringVar(value="none")
            ctk.CTkRadioButton(
                item_frame,
                text="",
                variable=decision_var,
                corner_radius=corner_radius,
                width=16,
                height=16,
                border_color=case_border,
                fg_color=case_fg,
                hover_color=case_hover,
                value="case",
            ).pack(side="left", padx=1)
            ctk.CTkRadioButton(
                item_frame,
                text="",
                variable=decision_var,
                corner_radius=corner_radius,
                width=16,
                height=16,
                border_color=not_case_border,
                hover_color=not_case_hover,
                fg_color=not_case_fg,
                value="not_a_case",
            ).pack(side="left", padx=1)
            subject_label = ctk.CTkLabel(
                item_frame,
                text=textwrap.shorten(lead_data["title"], width=50, placeholder="..."),
                anchor="w",
                cursor="hand2",
                font=self.main_font,
                text_color=TEXT_COLOR,
            )
            subject_label.pack(side="left", padx=10, expand=True, fill="x")
            subject_label.bind(
                "<Button-1>", lambda e, data=lead_data: self.display_lead_detail(data)
            )
            CTkToolTip(
                subject_label,
                message=lead_data["title"],
                delay=0.25,
                follow=True,
                x_offset=tooltip_x,
                y_offset=tooltip_y,
            )
            self.triage_items.append(
                {"frame": item_frame, "data": lead_data, "decision_var": decision_var}
            )

    def confirm_triage_action(self):
        items_to_process = self.triage_items[:]
        for item in items_to_process:
            decision = item["decision_var"].get()
            if decision == "case":
                self.log_message(
                    f"[TRIAGE SUCCESS]: Filing 'Case': {item['data']['title']}"
                )
                db_manager.add_case(item["data"])
            elif decision == "not_a_case":
                self.log_message(f"[TRIAGE]: Filing 'Not a Case' for retraining.")
                self.file_for_retraining(item["data"])
        self.log_message("[APP]: Triage complete. Refreshing search...")
        self.start_search_thread()

    def file_for_retraining(self, lead_data):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        not_case_dir = os.path.join(project_root, "data", "training_data", "not_a_case")
        os.makedirs(not_case_dir, exist_ok=True)
        safe_title = re.sub(r"[^\w\s-]", "", lead_data["title"]).replace(" ", "_")[:100]
        filepath = os.path.join(not_case_dir, f"{safe_title}.txt")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(lead_data.get("full_text", ""))
            self.log_message(
                f"[SAVE SUCCESS]: Saved retraining file: {os.path.basename(filepath)}"
            )
        except Exception as e:
            self.log_message(f"[SAVE ERROR]: Could not save retraining file: {e}")

    def display_lead_detail(self, lead_data):
        for widget in self.detail_frame.winfo_children():
            widget.destroy()
        self.detail_frame.grid_rowconfigure(0, weight=3)
        self.detail_frame.grid_rowconfigure(1, weight=1)
        self.detail_frame.grid_columnconfigure(0, weight=1)
        top_pane = ctk.CTkFrame(self.detail_frame, fg_color=DARK_GRAY)
        top_pane.grid(row=0, column=0, sticky="nsew")
        raw_html = lead_data.get("full_html", "")
        styled_html = html_sanitizer.sanitize_and_style(
            raw_html, lead_data.get("title")
        )
        if styled_html:
            html_viewer = tkinterweb.HtmlFrame(
                top_pane,
                messages_enabled=False,
                on_link_click=self.open_link_in_browser,
            )
            html_viewer.load_html(styled_html)
            html_viewer.pack(fill="both", expand=True)
            html_viewer.html.bind_all("<MouseWheel>", self._consume_scroll_event)
            html_viewer.html.bind_all("<Button-4>", self._consume_scroll_event)
            html_viewer.html.bind_all("<Button-5>", self._consume_scroll_event)
        else:
            text_box = ctk.CTkTextbox(
                top_pane,
                font=self.main_font,
                wrap="word",
                text_color=TEXT_COLOR,
                fg_color=DARK_GRAY,
            )
            text_box.pack(expand=True, fill="both")
            text_box.insert("0.0", lead_data.get("full_text", "No content available."))
            text_box.configure(state="disabled")
        bottom_pane = ctk.CTkFrame(self.detail_frame, fg_color=DARK_GRAY)
        bottom_pane.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        bottom_pane.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            bottom_pane,
            text="Extracted Links",
            font=self.bold_font,
            text_color=TEXT_COLOR,
        ).pack(anchor="w", padx=10, pady=5)
        links_frame = ctk.CTkScrollableFrame(bottom_pane, fg_color="transparent")
        links_frame.pack(fill="both", expand=True, padx=5, pady=5)
        extracted_links = link_extractor.find_links(raw_html)
        if not extracted_links:
            ctk.CTkLabel(
                links_frame,
                text="No links found.",
                font=self.main_font,
                text_color="gray",
            ).pack()
        else:
            for link in extracted_links:
                link_text = f"🔗 {link['text']}"
                link_label = ctk.CTkLabel(
                    links_frame,
                    text=link_text,
                    anchor="w",
                    cursor="hand2",
                    font=self.main_font,
                    text_color=ACCENT_COLOR,
                )
                link_label.pack(fill="x", padx=5, pady=2)
                link_label.bind(
                    "<Button-1>",
                    lambda e, url=link["url"]: self.open_link_in_browser(url),
                )
                CTkToolTip(links_frame, message=link["url"])

    def _consume_scroll_event(self, event):
        return "break"

    def open_link_in_browser(self, url):
        self.log_message(f"[APP]: Opening external link: {url}")
        try:
            webbrowser.open_new_tab(url)
        except Exception as e:
            self.log_message(f"[APP ERROR]: Could not open link: {e}")

    def log_message(self, msg):
        self.log_queue.put(msg)

    def process_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_textbox.configure(state="normal")
                timestamp = f"{datetime.now().strftime('%H:%M:%S')} - "
                self.log_textbox.insert("end", timestamp, "TIMESTAMP")
                tag_match = re.search(r"^(\[.*?\])", msg)
                if tag_match:
                    tag = tag_match.group(1)
                    if "ERROR" in tag or "FATAL" in tag:
                        tag_name = "ERROR"
                    elif "WARNING" in tag:
                        tag_name = "WARNING"
                    elif "SUCCESS" in tag:
                        tag_name = "SUCCESS"
                    else:
                        tag_name = "INFO"
                    self.log_textbox.insert("end", tag, tag_name)
                    self.log_textbox.insert("end", msg[len(tag) :] + "\n")
                else:
                    self.log_textbox.insert("end", msg + "\n")
                self.log_textbox.configure(state="disabled")
                self.log_textbox.see("end")
        except queue.Empty:
            pass
        self.after(100, self.process_log_queue)

    def _run_startup_checks(self):
        self.log_message("[APP]: Running startup system checks...")
        tasks = db_manager.get_all_tasks()
        if not tasks:
            self.log_message(
                "[APP WARNING]: No system tasks found in database. Run seeder?"
            )
            return
        pending_tasks = [
            task["task_name"] for task in tasks if task["status"] == "PENDING"
        ]
        if pending_tasks:
            self.log_message(
                f"[APP INFO]: {len(pending_tasks)} system task(s) are pending."
            )
            for task_name in pending_tasks:
                self.log_message(f"  -> PENDING: {task_name}")
        else:
            self.log_message("[APP SUCCESS]: All system tasks are complete.")


# The main execution block should be in hunter/__main__.py
