# ==========================================================
# Hunter's Command Console - Main Application
# v6.0 - Definitive version with all features, correct imports,
#        and the final, precise scroll fix.
# ==========================================================

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
from functools import partial
from hunter import dispatcher

# --- Our Custom Tools ---
from hunter import config_manager
from hunter import db_manager
from hunter.custom_widgets.tooltip import CTkToolTip
from hunter.html_parsers import html_sanitizer, link_extractor
from hunter.utils import logger_setup
# --- SURGICAL CHANGE: Import new Dispatcher class and data contracts ---
from hunter.dispatcher import Dispatcher
from hunter.models import LeadData

log_queue = logger_setup.setup_logging()

import logging

logger = logging.getLogger("HunterApp")
LOG_PATTERN = re.compile(r"^(\[.*?])\s+(\[.*?])\s+(.*)")
LEVEL_TAGS = {
	"ERROR":    "ERROR",
	"CRITICAL": "ERROR",
	"WARNING":  "WARNING",
	"SUCCESS":  "SUCCESS",
}


# Store the original method
original_check_if_master_is_canvas = ctk.CTkScrollableFrame.check_if_master_is_canvas

def patched_check_if_master_is_canvas(self, widget):
	# If widget is a string, return False to avoid the error
	if isinstance(widget, str):
		return False
	return original_check_if_master_is_canvas(self, widget)

# Apply the patch
ctk.CTkScrollableFrame.check_if_master_is_canvas = patched_check_if_master_is_canvas


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


def _is_scrolled_to_bottom(textbox):
	return float(textbox.yview()[0]) >= 0.999


class HunterApp(ctk.CTk):
	def __init__(self):
		super().__init__()

		# --- Window Setup ---
		self.title("Hunter's Command Console")
		self.geometry("800x600+100+100")
		self.configure(fg_color=DARK_BG)

		# --- Font Definitions ---
		self.main_font = ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE)
		self.bold_font = ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE, weight="bold")
		self.button_font = ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE + 2, weight="bold")

		# --- Database Connection Check ---
		if not db_manager.check_database_connection():
			error_label = ctk.CTkLabel(self, text="FATAL ERROR: Could not connect to PostgreSQL database.",
									   font=self.bold_font, text_color="red")
			error_label.pack(expand=True)
			return

		# --- SURGICAL CHANGE: Centralized DB Connection and Component Init ---
		self.db_conn = None
		self.dispatcher = None
		self.config = config_manager  # Assuming module-level access

		if not self._init_db_and_components():
			self.after(100, self.destroy)
			return
		# --- END CHANGE ---

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
		self.log_queue = logger_setup.setup_logging()

		self.after(100, self.process_gui_log_queue)
		self.after(200, self._run_startup_checks)

		self.after(200, self.refresh_triage_list)

	# --- SURGICAL CHANGE: New centralized init function ---
	def _init_db_and_components(self):
		"""Initializes DB connection and all dependent components."""
		self.db_conn = db_manager.get_db_connection()
		if not self.db_conn:
			logger.critical("FATAL: Could not connect to PostgreSQL database.")
			# TODO write messagebox for this error
			#			messagebox.showerror("Database Error", "Could not connect to PostgreSQL. Application will close.")
			return False

		try:
			self.dispatcher = Dispatcher(self.db_conn, self.config)
		except Exception as e:
			logger.critical(f"FATAL: Failed to initialize Dispatcher: {e}", exc_info=True)
			# TODO write messagebox for this error
			#			messagebox.showerror("Initialization Error", f"Failed to initialize dispatcher. Check logs.\n\n{e}")
			return False

		logger.info("Database connected and dispatcher initialized successfully.")
		return True

	def build_triage_desk(self):
		title_label = ctk.CTkLabel(self.left_frame, text="Triage Desk", font=self.bold_font, text_color=TEXT_COLOR)
		title_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
		self.scrollable_frame = ctk.CTkScrollableFrame(self.left_frame, fg_color=DARK_GRAY)
		self.scrollable_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
		self.bottom_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
		self.bottom_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
		self.bottom_frame.grid_columnconfigure(0, weight=1)
		self.bottom_frame.grid_columnconfigure(1, weight=1)
		self.search_button = ctk.CTkButton(self.bottom_frame, text="Search for New Cases",
		                                   command=self.start_hunt, font=self.button_font)  # <-- RE-WIRED
		self.search_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
		self.confirm_button = ctk.CTkButton(self.bottom_frame, text="Confirm & File Selected",
											command=self.confirm_triage_action, font=self.button_font)
		self.confirm_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

	def build_dossier_viewer(self):
		self.tab_view = ctk.CTkTabview(self.right_frame, fg_color=DARK_BG)
		self.tab_view.pack(expand=True, fill="both", padx=10, pady=10)
		self.tab_view.add("Dossier")
		self.tab_view.add("Operations Log")
		self.detail_frame = self.tab_view.tab("Dossier")
		self.log_frame = self.tab_view.tab("Operations Log")
		self.log_textbox = ctk.CTkTextbox(self.log_frame, font=self.main_font, wrap="word", fg_color=DARK_BG,
										  text_color=TEXT_COLOR)
		self.log_textbox.pack(expand=True, fill="both")
		self.log_textbox.tag_config("INFO", foreground=ACCENT_COLOR)
		self.log_textbox.tag_config("SUCCESS", foreground=SUCCESS_COLOR)
		self.log_textbox.tag_config("ERROR", foreground=ERROR_COLOR)
		self.log_textbox.tag_config("WARNING", foreground=WARNING_COLOR)
		self.log_textbox.tag_config("TIMESTAMP", foreground=TIMESTAMP_COLOR)
		self.log_textbox.tag_config("CALLER", foreground="#80A0C0")  # A nice blue for the module name

		self.log_textbox.configure(state="disabled")

	def start_search_thread(self):
		logger.info("[APP]: Hunter dispatch requested...")
		self.search_button.configure(state="disabled")
		threading.Thread(target=self.dispatch_hunt(), daemon=True).start()

	# --- SURGICAL CHANGE: Re-wired hunt process to use the new Dispatcher ---
	def start_hunt(self):
		"""Initiates a hunt in a background thread."""
		logger.info("[APP]: Hunter dispatch requested...")
		self.search_button.configure(state="disabled", text="Hunting...")

		# Get the list of sources for the dispatcher from the db_manager
		sources_to_hunt = db_manager.get_active_sources_by_purpose(self.db_conn)
		if not sources_to_hunt:
			logger.warning("No active sources found to hunt.")
			self.search_button.configure(state="normal", text="Search for New Cases")
			return

		# Run the dispatcher's 'dispatch' method in a separate thread
		hunt_thread = threading.Thread(
				target=self.dispatcher.dispatch,
				args=(sources_to_hunt,)
		)
		hunt_thread.daemon = True
		hunt_thread.start()

		self.after(100, self._check_hunt_status, hunt_thread)

	def _check_hunt_status(self, thread):
		"""Polls the hunt thread and refreshes the GUI when complete."""
		if thread.is_alive():
			self.after(1000, self._check_hunt_status, thread)
		else:
			logger.info("[APP]: Hunt thread has completed.")
			self.search_button.configure(state="normal", text="Search for New Cases")
			self.refresh_triage_list()

	def dispatch_hunt(self):
		"""
		Kicks off a new intel-gathering hunt in a background thread.
		This replaces the old 'run_search'.
		"""
		self.search_button.configure(state="disabled")
		logger.info("[APP]: Dispatcher activated. Hunting for new intel...")

		# Run the hunt in a separate thread to keep the GUI responsive
		hunt_thread = threading.Thread(target=self._hunt_thread_worker)
		hunt_thread.start()

	def _hunt_thread_worker(self):
		"""The actual work of the hunt, run in a background thread."""
		# Call our new, definitive dispatcher
		dispatcher.run_hunt()

		# When the hunt is done, safely tell the main GUI thread to refresh the list
		self.after(0, self.refresh_triage_list)
		self.after(0, lambda: self.search_button.configure(state="normal"))
		logger.info("[APP]: Dispatcher has completed all hunts.")

	def refresh_triage_list(self):
		"""Fetches unprocessed leads from the DB and updates the GUI."""
		logger.info("[APP]: Refreshing Triage list from database...")
		for widget in self.scrollable_frame.winfo_children():
			widget.destroy()
		self.triage_items.clear()

		unprocessed_leads = db_manager.get_unprocessed_leads(self.db_conn)

		grouped_results = {}
		for lead in unprocessed_leads:  # <-- Now iterating over LeadData objects
			grouped_results.setdefault(lead.source_name, []).append(lead)

		for source, leads in grouped_results.items():
			header = ctk.CTkFrame(self.scrollable_frame, fg_color=DARK_GRAY, cursor="hand2")
			header.pack(fill="x", pady=(5, 1), padx=2)
			lead_count = len(leads)
			plural_s = 's' if lead_count != 1 else ''
			label_text = f"▶ {source} ({lead_count} new lead{plural_s})"
			header_label = ctk.CTkLabel(header, text=label_text, font=self.bold_font, anchor="w", text_color=TEXT_COLOR)
			header_label.pack(side="left", padx=10, pady=5)
			content_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
			header._is_expanded = False
			header.bind("<Button-1>", lambda e, h=header, c=content_frame, l=leads: self._toggle_source_group(h, c, l))
			header_label.bind("<Button-1>",
							  lambda e, h=header, c=content_frame, l=leads: self._toggle_source_group(h, c, l))
		logger.info(f"[APP]: Triage list updated with {len(unprocessed_leads)} leads.")

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
		corner_radius = int(GUI_CONFIG.get("radio_corner_radius", 4))

		for lead_data in leads:
			item_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
			item_frame.pack(fill="x", pady=2, padx=10)
			decision_var = ctk.StringVar(value="none")
			ctk.CTkRadioButton(item_frame, text="", variable=decision_var, corner_radius=corner_radius, width=16,
							   height=16, border_color=case_border, fg_color=case_fg, hover_color=case_hover,
							   value="case").pack(side="left", padx=1)
			ctk.CTkRadioButton(item_frame, text="", variable=decision_var, corner_radius=corner_radius, width=16,
							   height=16, border_color=not_case_border, hover_color=not_case_hover,
							   fg_color=not_case_fg, value="not_a_case").pack(side="left", padx=1)
			subject_label = ctk.CTkLabel(item_frame,
			                             # Use attribute access: lead_data.title
			                             text=textwrap.shorten(lead_data.title, width=50, placeholder="..."),
			                             anchor="w", cursor="hand2", font=self.main_font, text_color="#E0E0E0")
			subject_label.pack(side="left", padx=10, expand=True, fill="x")
			subject_label.bind("<Button-1>", lambda e, data=lead_data: self.display_lead_detail(data))
			CTkToolTip(subject_label, message=lead_data.title, delay=0.25, follow=True, x_offset=tooltip_x,
					   y_offset=tooltip_y)
			self.triage_items.append({"frame": item_frame, "data": lead_data, "decision_var": decision_var})

	def confirm_triage_action(self):
		items_to_process = self.triage_items[:]
		for item in items_to_process:
			decision = item["decision_var"].get()
			lead_object = item["data"]  # This is a LeadData object
			if decision == "case":
				logger.info(f"[TRIAGE SUCCESS]: Filing 'Case': {lead_object.title}")
				# We now pass the clean LeadData object to add_case
				db_manager.add_case(self.db_conn, lead_object)
			elif decision == "not_a_case":
				logger.info(f"[TRIAGE]: Marking lead as 'ignored': {lead_object.title}")
				# Use the lead_uuid from our object to update the status in the router
				db_manager.update_lead_status(self.db_conn, lead_object.lead_uuid, 'IGNORED')

		logger.info("[APP]: Triage complete. Refreshing list...")
		self.refresh_triage_list()

	def file_for_retraining(self, lead_data):
		project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
		not_case_dir = os.path.join(project_root, "data", "training_data", "not_a_case")
		os.makedirs(not_case_dir, exist_ok=True)
		safe_title = re.sub(r"[^\w\s-]", "", lead_data["title"]).replace(" ", "_")[:100]
		filepath = os.path.join(not_case_dir, f"{safe_title}.txt")
		try:
			with open(filepath, "w", encoding="utf-8") as f:
				f.write(lead_data.get("full_text", ""))
			logger.info(f"[SAVE SUCCESS]: Saved retraining file: {os.path.basename(filepath)}")
		except Exception as e:
			logger.error(f"[SAVE ERROR]: Could not save retraining file: {e}")

	def display_lead_detail(self, lead_data: LeadData):
		for widget in self.detail_frame.winfo_children(): widget.destroy()
		self.detail_frame.grid_rowconfigure(0, weight=3)
		self.detail_frame.grid_rowconfigure(1, weight=1)
		self.detail_frame.grid_columnconfigure(0, weight=1)
		top_pane = ctk.CTkFrame(self.detail_frame, fg_color=DARK_GRAY)
		top_pane.grid(row=0, column=0, sticky="nsew")

		lead_uuid = lead_data.lead_uuid
		details_dict = db_manager.get_staged_lead_details(lead_uuid)

		if details_dict:
			# Prioritize HTML, but fall back to plain text if HTML is missing
			raw_html = details_dict.get("full_html")
			if not raw_html:
				# If no HTML, wrap the plain text in simple paragraph tags
				plain_text = details_dict.get("full_text", "No content available for this lead.")
				raw_html = f"<p>{plain_text}</p>"
		else:
			# If the database call fails, create a simple error message
			logger.error(f"[APP ERROR]: Could not find details for lead {lead_uuid}.")
			raw_html = "<html><body><h2>Error</h2><p>Could not retrieve lead details from the database.</p></body></html>"

		styled_html = html_sanitizer.sanitize_and_style(raw_html, lead_data.title)

		if styled_html:
			html_viewer = tkinterweb.HtmlFrame(top_pane, messages_enabled=False,
											   on_link_click=self.open_link_in_browser)
			html_viewer.load_html(styled_html)
			html_viewer.pack(fill="both", expand=True)

			# --- THE DEFINITIVE SCROLL FIX ---
			# We bind the scroll events directly to the widget's internal frame.
			# This is a more precise ward than bind_all and avoids side effects.
			html_viewer.html.bind("<MouseWheel>", self._consume_scroll_event)
			html_viewer.html.bind("<Button-4>", self._consume_scroll_event)  # For Linux
			html_viewer.html.bind("<Button-5>", self._consume_scroll_event)  # For Linux
		else:
			text_box = ctk.CTkTextbox(top_pane, font=self.main_font, wrap="word", text_color=TEXT_COLOR,
									  fg_color=DARK_GRAY)
			text_box.pack(expand=True, fill="both")
			text_box.insert("0.0", lead_data.text)
			text_box.configure(state="disabled")

		bottom_pane = ctk.CTkFrame(self.detail_frame, fg_color=DARK_GRAY)
		bottom_pane.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
		bottom_pane.grid_columnconfigure(0, weight=1)
		ctk.CTkLabel(bottom_pane, text="Extracted Links", font=self.bold_font, text_color=TEXT_COLOR).pack(anchor="w",
																										   padx=10,
																										   pady=5)
		links_frame = ctk.CTkScrollableFrame(bottom_pane, fg_color="transparent")
		links_frame.pack(fill="both", expand=True, padx=5, pady=5)
		extracted_links = link_extractor.find_links(raw_html)
		if not extracted_links:
			ctk.CTkLabel(links_frame, text="No links found.", font=self.main_font, text_color="gray").pack()
		else:
			for link in extracted_links:
				link_text = f"🔗 {link['text']}"
				link_label = ctk.CTkLabel(links_frame, text=link_text, anchor="w", cursor="hand2", font=self.main_font,
										  text_color=ACCENT_COLOR)
				link_label.pack(fill="x", padx=5, pady=2)
				# Instead of a lambda, we use functools.partial to create a clean,
				# stable callback function that correctly captures the URL.
				click_handler = partial(self.open_link_in_browser, link['url'])
				link_label.bind("<Button-1>", click_handler)
				CTkToolTip(links_frame, message=link["url"])

	@staticmethod
	def _consume_scroll_event(event):
		"""A firewall to stop scroll events from propagating and causing errors."""
		return "break"

	@staticmethod
	def open_link_in_browser(self, url):
		logger.info(f"[APP]: Opening external link: {url}")
		try:
			webbrowser.open_new_tab(url)
		except Exception as e:
			logger.error(f"[APP ERROR]: Could not open link: {e}")

	def process_gui_log_queue(self):
		processed_any = False
		try:
			# Check scroll state before inserting
			y0, y1 = self.log_textbox.yview()
			# If not scrollable yet (y1 == 1.0), or already at bottom, we should follow
			at_bottom = (y1 == 1.0) or (y1 >= 0.999)

			self.log_textbox.configure(state="normal")

			while True:
				msg = self.log_queue.get_nowait()
				processed_any = True

				timestamp = f"{datetime.now().strftime('%H:%M:%S')} - "
				self.log_textbox.insert("end", timestamp, "TIMESTAMP")

				match = LOG_PATTERN.match(msg)
				if match:
					level_tag, caller_tag, message_text = match.groups()
					level_color_tag = next(
							(LEVEL_TAGS[key] for key in LEVEL_TAGS if key in level_tag),
							"INFO"
					)
					self.log_textbox.insert("end", f"{level_tag} ", level_color_tag)
					self.log_textbox.insert("end", f"{caller_tag} ", "CALLER")
					self.log_textbox.insert("end", f"{message_text}\n", "INFO")
				else:
					self.log_textbox.insert("end", f"{msg}\n", "INFO")

		except queue.Empty:
			pass
		finally:
			self.log_textbox.configure(state="disabled")

			# Only scroll if we were at bottom OR not scrollable yet
			if at_bottom:
				self.log_textbox.see("end")

		if processed_any:
			self.after_idle(self.process_gui_log_queue)
		else:
			self.after(100, self.process_gui_log_queue)
	@staticmethod
	def _run_startup_checks():
		logger.info("[APP]: Running startup system checks...")
		tasks = db_manager.get_all_tasks()
		if not tasks:
			logger.warning("[APP WARNING]: No system tasks found in database. Run seeder?")
			return
		pending_tasks = [task['task_name'] for task in tasks if task['status'] == 'PENDING']
		if pending_tasks:
			logger.info(f"[APP INFO]: {len(pending_tasks)} system task(s) are pending.")
			for task_name in pending_tasks:
				logger.info(f"  -> PENDING: {task_name}")
		else:
			logger.info("[APP SUCCESS]: All system tasks are complete.")

	def on_closing(self):
		"""SURGICAL CHANGE: Ensure the central connection is closed."""
		logger.info("Closing database connection and shutting down.")
		if self.db_conn:
			self.db_conn.close()
		self.destroy()
