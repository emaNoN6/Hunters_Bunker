# ==========================================================
# Hunter's Command Console - Main Application
# v2.1 - Fixes missing datetime import.
# ==========================================================

import customtkinter as ctk
import threading
import queue
import webbrowser
import os
import re
import time
import textwrap
from tkhtmlview import HTMLLabel
from datetime import datetime  # <-- THE FIX IS HERE

# --- Our Custom Tools ---
# These imports are now relative to the 'hunter' package.
from . import config_manager
from . import actions_news_search
from . import db_manager
from .custom_widgets import OffsetToolTip

# We also need to specify the html_parsers package now
# from html_parsers import html_sanitizer, link_extractor

# --- GUI Configuration ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")
dark_bg = "#242424"
dark_gray = "#2b2b2b"


class HunterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Window Setup ---
        self.title("Hunter's Command Console")
        self.geometry("1200x800")

        # --- Font Definitions ---
        self.main_font = ctk.CTkFont(family="Courier New", size=14)
        self.bold_font = ctk.CTkFont(family="Courier New", size=14, weight="bold")

        # --- Database Connection Check on Startup ---
        print("[APP]: Checking PostgreSQL database connection...")
        if not db_manager.check_database_connection():
            error_label = ctk.CTkLabel(
                self,
                text="FATAL ERROR: Could not connect to PostgreSQL database.\nCheck console for details.",
                font=self.bold_font,
                text_color="red",
            )
            error_label.pack(expand=True, padx=20, pady=20)
            return
        print("[APP]: Database connection successful.")

        # --- Main Layout ---
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=5)
        self.grid_rowconfigure(0, weight=1)

        self.left_frame = ctk.CTkFrame(self, fg_color=dark_bg)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        self.left_frame.grid_rowconfigure(1, weight=1)

        self.right_frame = ctk.CTkFrame(self, fg_color=dark_bg)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.right_frame.grid_rowconfigure(0, weight=1)

        # --- Left Pane: Triage Desk ---
        self.build_triage_desk()

        # --- Right Pane: Dossier Viewer & Log ---
        self.build_dossier_viewer()

        # --- Data & Threading Setup ---
        self.triage_items = []
        self.log_queue = queue.Queue()
        self.after(100, self.process_log_queue)

    def build_triage_desk(self):
        title_label = ctk.CTkLabel(
            self.left_frame, text="Triage Desk", font=self.bold_font
        )
        title_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.scrollable_frame = ctk.CTkScrollableFrame(
            self.left_frame, fg_color=dark_bg
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
            font=self.main_font,
        )
        self.search_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.confirm_button = ctk.CTkButton(
            self.bottom_frame,
            text="Confirm & File Selected",
            command=self.confirm_triage_action,
            font=self.main_font,
        )
        self.confirm_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def build_dossier_viewer(self):
        self.tab_view = ctk.CTkTabview(self.right_frame, fg_color=dark_gray)
        self.tab_view.pack(expand=True, fill="both", padx=10, pady=10)
        self.tab_view.add("Dossier")
        self.tab_view.add("Operations Log")

        self.detail_frame = self.tab_view.tab("Dossier")
        self.log_frame = self.tab_view.tab("Operations Log")

        self.log_textbox = ctk.CTkTextbox(
            self.log_frame, font=self.main_font, wrap="word", fg_color=dark_bg
        )
        self.log_textbox.pack(expand=True, fill="both")
        self.log_textbox.configure(state="disabled")

    def start_search_thread(self):
        self.log_message("[APP]: Hunter dispatched. Searching for new cases...")
        self.search_button.configure(state="disabled")
        search_thread = threading.Thread(target=self.run_search, daemon=True)
        search_thread.start()

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
        self.log_message("[APP]: All agents have returned.")

    def populate_triage_list(self, results):
        for item in self.triage_items:
            item["frame"].destroy()
        self.triage_items.clear()

        header_frame = ctk.CTkFrame(self.scrollable_frame, fg_color=dark_gray)
        header_frame.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(header_frame, text="Case", font=self.bold_font, width=60).pack(
            side="left", padx=5
        )
        ctk.CTkLabel(
            header_frame, text="Not a Case", font=self.bold_font, width=90
        ).pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Subject", font=self.bold_font).pack(
            side="left", padx=10, expand=True, anchor="w"
        )
        ctk.CTkLabel(header_frame, text="Source", font=self.bold_font, width=100).pack(
            side="right", padx=10
        )

        for lead_data in results:
            item_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
            item_frame.pack(fill="x", pady=2)

            decision_var = ctk.StringVar(value="none")

            case_radio = ctk.CTkRadioButton(
                item_frame, text="", variable=decision_var, value="case", width=60
            )
            case_radio.pack(side="left", padx=5)

            not_case_radio = ctk.CTkRadioButton(
                item_frame, text="", variable=decision_var, value="not_a_case", width=90
            )
            not_case_radio.pack(side="left", padx=5)

            subject_label = ctk.CTkLabel(
                item_frame,
                text=textwrap.shorten(lead_data["title"], width=50, placeholder="..."),
                anchor="w",
                cursor="hand2",
                font=self.main_font,
            )
            subject_label.pack(side="left", padx=10, expand=True, fill="x")
            subject_label.bind(
                "<Button-1>", lambda e, data=lead_data: self.display_lead_detail(data)
            )
            OffsetToolTip(subject_label, text=lead_data["title"])

            source_label = ctk.CTkLabel(
                item_frame, text=lead_data["source"], width=100, font=self.main_font
            )
            source_label.pack(side="right", padx=10)

            self.triage_items.append(
                {"frame": item_frame, "data": lead_data, "decision_var": decision_var}
            )

    def confirm_triage_action(self):
        items_to_remove = []
        for item in self.triage_items:
            decision = item["decision_var"].get()
            if decision == "case":
                self.log_message(f"[TRIAGE]: Filing 'Case': {item['data']['title']}")
                db_manager.add_case(item["data"])
                items_to_remove.append(item)
            elif decision == "not_a_case":
                self.log_message(
                    f"[TRIAGE]: Filing 'Not a Case' for retraining: {item['data']['title']}"
                )
                self.file_for_retraining(item["data"])
                items_to_remove.append(item)

        for item in items_to_remove:
            item["frame"].destroy()
            self.triage_items.remove(item)

    def file_for_retraining(self, lead_data):
        not_case_dir = os.path.join(
            os.path.dirname(__file__), "training_data", "not_a_case"
        )
        os.makedirs(not_case_dir, exist_ok=True)
        safe_title = re.sub(r"[^\w\s-]", "", lead_data["title"]).replace(" ", "_")[:100]
        filepath = os.path.join(not_case_dir, f"{safe_title}.txt")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(lead_data.get("text", ""))
            self.log_message(
                f"[SAVE]: Saved retraining file: {os.path.basename(filepath)}"
            )
        except Exception as e:
            self.log_message(f"[ERROR]: Could not save retraining file: {e}")

    def display_lead_detail(self, lead_data):
        for widget in self.detail_frame.winfo_children():
            widget.destroy()

        if lead_data.get("html"):
            styled_html = f"<body style='background-color:{dark_gray}; color:white; font-family: Courier New; font-size: 14px;'>{lead_data['html']}</body>"
            html_frame = ctk.CTkFrame(self.detail_frame, fg_color=dark_gray)
            html_frame.pack(fill="both", expand=True)
            HTMLLabel(html_frame, html=styled_html, background=dark_gray).pack(
                fill="both", expand=True, padx=10, pady=10
            )
        else:
            text_box = ctk.CTkTextbox(
                self.detail_frame, font=self.main_font, wrap="word"
            )
            text_box.pack(expand=True, fill="both", padx=10, pady=10)
            text_box.insert("0.0", lead_data.get("text", "No text available."))
            text_box.configure(state="disabled")

    def log_message(self, msg):
        self.log_queue.put(msg)

    def process_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_textbox.configure(state="normal")
                self.log_textbox.insert(
                    "end", f"{datetime.now().strftime('%H:%M:%S')} - {msg}\n"
                )
                self.log_textbox.configure(state="disabled")
                self.log_textbox.see("end")
        except queue.Empty:
            pass
        self.after(100, self.process_log_queue)


if __name__ == "__main__":
    app = HunterApp()
    app.mainloop()
