# FILE: hunter_app.py (UPDATED with GUI Fixes)
# ===============================================

import customtkinter as ctk
import threading
import queue
import config_manager
import actions_news_search

# --- NEW: GUI Configuration (The Right Way) ---
# This happens ONCE, at the start of the program, before any windows are made.
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")  # Let's make it look like a classic terminal


class HunterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- NEW: Font Definitions ---
        # We define our font styles here, like C typedefs.
        self.log_font = ctk.CTkFont(family="Courier New", size=14)
        self.button_font = ctk.CTkFont(family="System", size=13, weight="bold")
        # You no longer need to add the color setting here.

        self.title("Hunter's Command Console")
        self.geometry("1100x700")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.is_searching = False
        self.log_queue = queue.Queue()
        self.results_queue = queue.Queue()

        # --- Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=180, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, text="H.C.C.", font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Apply the new font to our button
        self.search_button = ctk.CTkButton(
            self,
            text="Search for Cases",
            command=self.search_cases_action,
            font=self.button_font,
        )
        self.search_button.grid(
            in_=self.sidebar_frame, row=1, column=0, padx=20, pady=10
        )

        # --- Main Content ---
        # Apply the new, bigger font to our log textbox
        self.log_textbox = ctk.CTkTextbox(self, font=self.log_font)
        self.log_textbox.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.log_textbox.insert(
            "0.0", "Hunter's Command Console Initialized.\n" + "=" * 50 + "\n"
        )

        self.process_log_queue()
        self.process_results_queue()

    def add_log(self, message):
        self.log_textbox.insert("end", f"{message}\n")
        self.log_textbox.see("end")

    # ... (the rest of the search functions remain exactly the same) ...

    def process_log_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.add_log(message)
        except queue.Empty:
            pass
        self.after(100, self.process_log_queue)

    def process_results_queue(self):
        try:
            while True:
                result = self.results_queue.get_nowait()
                if result == "SEARCH_COMPLETE":
                    self.on_search_complete()
                else:
                    self.add_log(f"[LEAD]: {result.get('title', 'Untitled Lead')}")
        except queue.Empty:
            pass
        self.after(100, self.process_results_queue)

    def search_cases_action(self):
        if self.is_searching:
            self.log_queue.put("[WARNING]: Search already in progress.")
            return

        self.add_log("\n[ACTION]: Dispatching all agents...")
        self.is_searching = True
        self.search_button.configure(state="disabled")

        search_thread = threading.Thread(
            target=actions_news_search.run_all_searches,
            args=(self.log_queue, self.results_queue),
            daemon=True,
        )
        search_thread.start()

    def on_search_complete(self):
        self.is_searching = False
        self.search_button.configure(state="normal")


if __name__ == "__main__":
    # Ensure a default config exists before starting the app
    if "config_manager" in locals() or "config_manager" in globals():
        config_manager.create_default_config()
    app = HunterApp()
    app.mainloop()
