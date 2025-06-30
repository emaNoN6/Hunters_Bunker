import customtkinter as ctk
import threading
import queue
import webbrowser
import os
import re
import time
import textwrap

# You will need to install tkhtmlview: pip install tkhtmlview
from tkhtmlview import HTMLLabel

# You will need to install this: pip install customtkinter-tooltip
from custom_widgets import OffsetToolTip

# Our own custom tools
import config_manager
import actions_news_search

# --- GUI Configuration ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


class HunterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Font Definitions ---
        self.main_font = ctk.CTkFont(family="Courier New", size=14)
        self.button_font = ctk.CTkFont(family="Courier New", size=13, weight="bold")
        self.title_font = ctk.CTkFont(family="Courier New", size=16, weight="bold")
        self.header_font = ctk.CTkFont(
            family="Courier New", size=14, weight="bold", underline=True
        )

        # --- Window Setup ---
        self.title("Hunter's Command Console - Investigation Desk")
        self.geometry("1400x800")

        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        # --- State & Communication ---
        self.is_searching = False
        self.results_queue = queue.Queue()
        self.triage_items = []

        # --- Left Pane: The Triage Desk ---
        self.triage_frame = ctk.CTkFrame(self)
        self.triage_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.triage_frame.grid_columnconfigure(0, weight=1)
        self.triage_frame.grid_rowconfigure(
            3, weight=1
        )  # The list inside should expand

        triage_label = ctk.CTkLabel(
            self.triage_frame, text="New Leads for Triage", font=self.title_font
        )
        triage_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.search_button = ctk.CTkButton(
            self.triage_frame,
            text="Search for New Cases",
            command=self.search_cases_action,
            font=self.button_font,
        )
        self.search_button.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        # --- NEW: The Header Row ---
        header_frame = ctk.CTkFrame(self.triage_frame, fg_color="transparent")
        header_frame.grid(row=2, column=0, sticky="ew", padx=5)
        header_frame.grid_columnconfigure(2, weight=1)  # Subject column expands

        ctk.CTkLabel(header_frame, text="Case", font=self.header_font).grid(
            row=0, column=0, padx=5
        )
        ctk.CTkLabel(header_frame, text="Not Case", font=self.header_font).grid(
            row=0, column=1, padx=5
        )
        ctk.CTkLabel(
            header_frame, text="Subject", font=self.header_font, anchor="w"
        ).grid(row=0, column=2, padx=10, sticky="w")
        ctk.CTkLabel(
            header_frame, text="Source", font=self.header_font, anchor="e"
        ).grid(row=0, column=3, padx=10, sticky="e")

        # --- The Scrollable List ---
        self.triage_scroll_frame = ctk.CTkScrollableFrame(
            self.triage_frame, label_text=""
        )
        self.triage_scroll_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)
        self.triage_scroll_frame.grid_columnconfigure(0, weight=1)

        self.confirm_button = ctk.CTkButton(
            self.triage_frame,
            text="Confirm & File Selected",
            command=self.confirm_triage_action,
            font=self.button_font,
        )
        self.confirm_button.grid(row=4, column=0, sticky="ew", padx=10, pady=10)

        # --- Right Pane: The Dossier Viewer ---
        self.detail_frame = ctk.CTkFrame(self)
        self.detail_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        self.detail_frame.grid_columnconfigure(0, weight=1)
        self.detail_frame.grid_rowconfigure(0, weight=1)
        self.detail_frame.grid_propagate(False)

        self.detail_placeholder = ctk.CTkLabel(
            self.detail_frame,
            text="Select a lead to view its contents.",
            font=self.title_font,
        )
        self.detail_placeholder.pack(expand=True)

        self.process_queues()

    def process_queues(self):
        try:
            while True:
                result = self.results_queue.get_nowait()
                if isinstance(result, dict):
                    self.add_triage_item(result)
                elif result == "SEARCH_COMPLETE":
                    self.on_search_complete()
        except queue.Empty:
            pass
        self.after(100, self.process_queues)

    def add_triage_item(self, lead_data):
        """Creates a row that uses our new, definitive tooltip."""
        item_frame = ctk.CTkFrame(self.triage_scroll_frame, fg_color="transparent")
        item_frame.grid(sticky="ew", padx=5, pady=2)
        item_frame.grid_columnconfigure(2, weight=1)

        triage_var = ctk.StringVar(value="none")
        rb_case = ctk.CTkRadioButton(
            item_frame, text="", variable=triage_var, value="case", width=20
        )
        rb_not_case = ctk.CTkRadioButton(
            item_frame, text="", variable=triage_var, value="not_a_case", width=20
        )

        full_title = lead_data.get("title", "No Title")

        subject_label = ctk.CTkLabel(
            item_frame, text=full_title, anchor="w", cursor="hand2", font=self.main_font
        )
        subject_label.bind(
            "<Button-1>", lambda e, data=lead_data: self.display_lead_details(data)
        )

        # Prepare the wrapped text for the tooltip
        wrapped_text = "\n".join(textwrap.wrap(full_title, width=80))

        # Call our new, stable tooltip class
        OffsetToolTip(
            subject_label,
            message=wrapped_text,
            delay=0.5,
            font=self.main_font,
            wraplength=600,  # pass wraplength as a kwarg
            x_offset=20,
            y_offset=10,
        )

        source_label = ctk.CTkLabel(
            item_frame,
            text=f"({lead_data.get('source', 'Unknown')})",
            text_color="gray",
            font=self.main_font,
        )

        rb_case.grid(row=0, column=0, padx=20, pady=5)
        rb_not_case.grid(row=0, column=1, padx=20, pady=5)
        subject_label.grid(row=0, column=2, padx=10, pady=5, sticky="w")
        source_label.grid(row=0, column=3, padx=10, pady=5, sticky="e")

        self.triage_items.append(
            {"frame": item_frame, "decision_var": triage_var, "data": lead_data}
        )

    def clear_detail_pane(self):
        for widget in self.detail_frame.winfo_children():
            widget.destroy()

    def display_lead_details(self, lead_data):
        self.clear_detail_pane()
        if "html" in lead_data and lead_data["html"]:
            original_html = lead_data["html"]

            # Define our dark theme colors
            dark_bg = "#2B2B2B"
            dark_fg = "#DCE4EE"

            # --- The Injection Spell ---
            # We wrap the original HTML in a div with our own styling.
            # This sets a base font size and a more readable text color.
            styled_html = f"""
            <html>
              <body>
                <div
                  style="
                    font-size: 32px;
                    color: {dark_fg};
                    background-color: {dark_bg};
                    padding: 10px;">
                  {original_html}
                </div>
              </body>
            </html>
            """

            print(
                f"[DETAILS]: Displaying HTML content for {lead_data.get('title', 'Unknown')}\n   [HTML]: {styled_html}"
            )
            html_frame = ctk.CTkScrollableFrame(self.detail_frame)
            html_frame.pack(expand=True, fill="both")
            HTMLLabel(html_frame, html=styled_html).pack(
                fill="both", padx=10, pady=10
            )
        else:
            text_box = ctk.CTkTextbox(
                self.detail_frame, font=self.main_font, wrap="word"
            )
            text_box.pack(expand=True, fill="both", padx=10, pady=10)
            text_box.insert("0.0", lead_data.get("text", "No text available."))
            text_box.configure(state="disabled")

    def clear_triage_desk(self):
        for item in self.triage_items:
            item["frame"].destroy()
        self.triage_items.clear()
        self.clear_detail_pane()
        self.detail_placeholder = ctk.CTkLabel(
            self.detail_frame,
            text="Select a lead from the list to view its contents.",
            font=self.title_font,
        ).pack(expand=True)

    def search_cases_action(self):
        if self.is_searching:
            return
        print("\n[ACTION]: Dispatching agents...")
        self.clear_triage_desk()
        self.is_searching = True
        self.search_button.configure(state="disabled")
        search_thread = threading.Thread(
            target=actions_news_search.run_all_searches,
            args=(self.results_queue, self.results_queue),
            daemon=True,
        )
        search_thread.start()

    def on_search_complete(self):
        self.is_searching = False
        self.search_button.configure(state="normal")
        print("Search complete. Triage desk populated with new leads.")

    def confirm_triage_action(self):
        items_to_remove = []
        for item in self.triage_items:
            decision = item["decision_var"].get()
            if decision == "case":
                print(f"[TRIAGE]: SAVING TO DB (future): {item['data']['title']}")
                items_to_remove.append(item)
            elif decision == "not_a_case":
                print(
                    f"[TRIAGE]: DISCARDING & FILING FOR RETRAINING: {item['data']['title']}"
                )
                self.file_for_retraining(item["data"])
                items_to_remove.append(item)

        for item in items_to_remove:
            item["frame"].destroy()
            self.triage_items.remove(item)

    def file_for_retraining(self, lead_data):
        try:
            output_dir = "training_data/not_a_case"
            os.makedirs(output_dir, exist_ok=True)
            safe_title = (
                re.sub(r"[^\w\s-]", "", lead_data.get("title", "untitled"))
                .replace(" ", "_")
                .lower()[:100]
            )
            timestamp = int(time.time())
            filepath = os.path.join(
                output_dir, f"discarded_{safe_title}_{timestamp}.txt"
            )
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(lead_data.get("text", ""))
            print(f"  -> Filed '{safe_title}' for future training.")
        except Exception as e:
            print(f"  -> ERROR filing for retraining: {e}")


if __name__ == "__main__":
    try:
        import tkhtmlview
        from CTkToolTip import CTkToolTip
    except ImportError:
        print("ERROR: Missing required libraries.")
        print("Please run: pip install tkhtmlview customtkinter-tooltip")
        exit()

    config_manager.create_default_config()
    app = HunterApp()
    app.mainloop()
