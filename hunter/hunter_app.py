# ==========================================================
# Hunter's Command Console - Main Application
# v6.0 - Definitive version with all features, correct imports,
#        and the final, precise scroll fix.
# ==========================================================
import base64
import io
import uuid

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
from tkinter import ttk, messagebox, Menu

# --- Our Custom Tools ---
from hunter import config_manager
from hunter import db_manager
from hunter.custom_widgets.tooltip import TkToolTip
from hunter.html_parsers import html_sanitizer, link_extractor
from hunter.utils import logger_setup
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


def file_for_retraining(lead_data):
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


class HunterApp(ctk.CTk):
	def __init__(self):
		super().__init__()

		# --- Window Setup ---
		self.hunt_event = None
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

		self.dispatcher = None
		self.config = config_manager  # Assuming module-level access

		self.tree_tooltip = None

		if not self._init_db_and_components():
			self.after(100, self.destroy)
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
		self.log_queue = logger_setup.setup_logging()

		self.after(100, self.process_gui_log_queue)
		self.after(200, self._run_startup_checks)

		self.after(200, self.refresh_triage_list)

	def _init_db_and_components(self):
		# 1. Perform health check (this also warms up the lazy connection)
		if not db_manager.check_database_connection():
			logger.critical("FATAL: Database unreachable.")
			return False

		# 2. Initialize Dispatcher (No connection passed!)
		try:
			self.dispatcher = Dispatcher(self.config)
		except Exception as e:
			logger.critical(f"FATAL: Components failed: {e}")
			return False
		return True

	def build_triage_desk(self):
		"""Build the triage desk with ttk.Treeview for performance"""

		style = ttk.Style()
		style.theme_use('default')
		tree_font = (FONT_FAMILY, FONT_SIZE)
		heading_font = (FONT_FAMILY, FONT_SIZE, "bold")

		# Title
		title_label = ctk.CTkLabel(self.left_frame, text="Triage Desk",
		                           font=self.bold_font, text_color=TEXT_COLOR)
		title_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

		# Style the Treeview to match dark theme
		style = ttk.Style()
		style.theme_use('default')
		style.configure("Treeview",
		                background=DARK_GRAY,
		                foreground=TEXT_COLOR,
		                fieldbackground=DARK_GRAY,
		                font=tree_font,
		                rowheight=int(FONT_SIZE * 2),
		                borderwidth=0)
		style.configure("Treeview.Heading",
		                background=DARK_BG,
		                foreground=TEXT_COLOR,
		                font=heading_font,
		                relief="flat")
		style.map('Treeview', background=[('selected', ACCENT_COLOR)])

		# Create Treeview with columns
		self.triage_tree = ttk.Treeview(
				self.left_frame,
				columns=('source', 'date', 'decision'),
				show='tree headings',
				selectmode='extended',
				height=25
		)

		# Configure columns
		self.triage_tree.heading('#0', text='Title')
		self.triage_tree.heading('source', text='Source')
		self.triage_tree.heading('date', text='Date')
		self.triage_tree.heading('decision', text='Decision')

		self.triage_tree.column('#0', width=400, anchor='w')
		self.triage_tree.column('source', width=150, anchor='w')
		self.triage_tree.column('date', width=100, anchor='w')
		self.triage_tree.column('decision', width=100, anchor='center')

		# Add scrollbar
		scrollbar = ttk.Scrollbar(self.left_frame, orient="vertical",
		                          command=self.triage_tree.yview)
		self.triage_tree.configure(yscrollcommand=scrollbar.set)

		# Grid layout
		self.triage_tree.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(0, 10))
		scrollbar.grid(row=1, column=1, sticky="ns", pady=(0, 10))

		# Buttons at bottom
		self.bottom_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
		self.bottom_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
		self.bottom_frame.grid_columnconfigure(0, weight=1)
		self.bottom_frame.grid_columnconfigure(1, weight=1)

		self.search_button = ctk.CTkButton(self.bottom_frame, text="Search for New Cases",
		                                   command=self.start_hunt, font=self.button_font)
		self.search_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))

		self.confirm_button = ctk.CTkButton(self.bottom_frame, text="Confirm & File Selected",
		                                    command=self.confirm_triage_action, font=self.button_font)
		self.confirm_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

		# Bind events for tooltips and clicks
		self.triage_tree.bind('<Motion>', self.show_tree_tooltip)
		self.triage_tree.bind('<Leave>', self.hide_tree_tooltip)
		self.triage_tree.bind('<Double-1>', self.on_tree_double_click)

		# Store lead data by tree item id
		self.tree_lead_data = {}

		# bind keys for classification
		self.triage_tree.bind('<c>', self.mark_selected_as_case)
		self.triage_tree.bind('<C>', self.mark_selected_as_case)
		self.triage_tree.bind('<n>', self.mark_selected_as_not_case)
		self.triage_tree.bind('<N>', self.mark_selected_as_not_case)
		self.triage_tree.bind('<s>', self.mark_selected_as_skip)
		self.triage_tree.bind('<S>', self.mark_selected_as_skip)
		self.triage_tree.bind('<space>', self.clear_selected_decision)
		self.triage_tree.bind('<BackSpace>', self.clear_selected_decision)

	def mark_selected_as_case(self, event=None):
		"""Mark selected leads as CASE"""
		selected = self.triage_tree.selection()
		for item_id in selected:
			if item_id in self.tree_lead_data:
				self.triage_tree.set(item_id, 'decision', 'CASE')
		logger.info(f"[APP]: Marked {len(selected)} item(s) as CASE")

	def mark_selected_as_not_case(self, event=None):
		"""Mark selected leads as NOT_CASE"""
		selected = self.triage_tree.selection()
		for item_id in selected:
			if item_id in self.tree_lead_data:
				self.triage_tree.set(item_id, 'decision', 'NOT_CASE')
		logger.info(f"[APP]: Marked {len(selected)} item(s) as NOT_CASE")

	def mark_selected_as_skip(self, event=None):
		"""Mark selected leads as SKIP (junk)"""
		selected = self.triage_tree.selection()
		for item_id in selected:
			if item_id in self.tree_lead_data:
				self.triage_tree.set(item_id, 'decision', 'SKIP')
		logger.info(f"[APP]: Marked {len(selected)} item(s) as SKIP")

	def clear_selected_decision(self, event=None):
		"""Clear decision (back to untouched)"""
		selected = self.triage_tree.selection()
		for item_id in selected:
			if item_id in self.tree_lead_data:
				self.triage_tree.set(item_id, 'decision', '')
		logger.info(f"[APP]: Cleared decision for {len(selected)} item(s)")

	def show_tree_tooltip(self, event):
		"""Show tooltip with full title on hover"""
		item_id = self.triage_tree.identify_row(event.y)

		if item_id and item_id in self.tree_lead_data:
			lead = self.tree_lead_data[item_id]

			# Wrap text to approx 60 chars to prevent extremely wide tooltips
			display_text = textwrap.fill(lead.title, width=60)

			# Create tooltip once if it doesn't exist
			if not self.tree_tooltip:
				self.tree_tooltip = TkToolTip(
						self.triage_tree,
						message=display_text,
						delay=0.25,
						x_offset=20,
						y_offset=10,
						bg_color=DARK_GRAY,
						fg_color=TEXT_COLOR,
						font=(FONT_FAMILY, FONT_SIZE),
						padding=8  # Adjust as needed
				)
				# Ensure multi-line text is left-aligned for better readability
				self.tree_tooltip.label.configure(justify="left")
			else:
				# Update existing tooltip's message
				self.tree_tooltip.label.configure(text=display_text)
				self.tree_tooltip.on_enter(event)
		else:
			if self.tree_tooltip:
				self.tree_tooltip.hide()

	def hide_tree_tooltip(self, event):
		"""Hide tooltip when mouse leaves"""
		if self.tree_tooltip:
			self.tree_tooltip.on_leave()

	def on_tree_double_click(self, event):
		"""Display lead details when double-clicked"""
		item_id = self.triage_tree.identify_row(event.y)
		if item_id and item_id in self.tree_lead_data:
			lead = self.tree_lead_data[item_id]
			self.display_lead_detail(lead)

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
		self.log_textbox.tag_config("DEBUG", foreground="#AA0033")
		self.log_textbox.tag_config("SUCCESS", foreground=SUCCESS_COLOR)
		self.log_textbox.tag_config("ERROR", foreground=ERROR_COLOR)
		self.log_textbox.tag_config("WARNING", foreground=WARNING_COLOR)
		self.log_textbox.tag_config("TIMESTAMP", foreground=TIMESTAMP_COLOR)
		self.log_textbox.tag_config("CALLER", foreground="#80A0C0")  # A nice blue for the module name

		self.log_textbox.configure(state="disabled")

	def start_hunt(self):
		"""Initiates a hunt in a background thread."""
		logger.info("[APP]: Hunter dispatch requested...")
		self.search_button.configure(state="disabled", text="Hunting...")

		# Get the list of sources for the dispatcher from the db_manager
		sources_to_hunt = db_manager.get_active_sources_by_purpose()
		if not sources_to_hunt:
			logger.warning("No active sources found to hunt.")
			self.search_button.configure(state="normal", text="Search for New Cases")
			return

		# Run the dispatcher's 'dispatch' method in a separate thread
		self.hunt_event = self.dispatcher.dispatch(sources_to_hunt)  # Store the event
		self.after(1000, self._check_hunt_status)  # Start polling

	def _check_hunt_status(self):
		if not self.hunt_event.is_set():
			self.after(1000, self._check_hunt_status)
		else:
			logger.info("[APP]: All hunt threads completed.")
			self.search_button.configure(state="normal", text="Search for New Cases")
			self.refresh_triage_list()

	def refresh_triage_list(self):
		"""
		Fetches the latest untriaged leads from the database and populates the Treeview.
		"""
		import time
		from collections import defaultdict

		logger.info("[APP]: Refreshing Triage list from database...")
		start_time = time.perf_counter()

		# Clear existing tree items
		for item in self.triage_tree.get_children():
			self.triage_tree.delete(item)
		self.tree_lead_data = {}
		clear_time = time.perf_counter()

		# Fetch leads from database (returns list[LeadData])
		leads = db_manager.get_unprocessed_leads()
		fetch_time = time.perf_counter()

		if not leads:
			logger.info("[APP]: No leads found for triage.")
			return

		# Group leads by source_name
		grouped_leads = defaultdict(list)
		for lead in leads:
			grouped_leads[lead.source_name].append(lead)

		# Populate tree with grouped leads
		for source_name, source_leads in grouped_leads.items():
			# Insert parent (source group)
			parent_id = self.triage_tree.insert(
					'', 'end',
					text=f"{source_name} ({len(source_leads)} new leads)",
					values=('', '', ''),
					tags=('source_group',)
			)

			# Insert children (individual leads)
			for lead in source_leads:
				# Format publication date
				pub_date = lead.publication_date.strftime('%Y-%m-%d') if lead.publication_date else 'Unknown'

				# Truncate long titles
				title = lead.title
				display_title = title[:80] + '...' if len(title) > 80 else title

				lead_id = self.triage_tree.insert(
						parent_id, 'end',
						text=display_title,
						values=(source_name, pub_date, ''),
						tags=('lead_item',)
				)

				# Store full lead data object
				self.tree_lead_data[lead_id] = lead

		logger.info(f"[APP]: Triage list updated with {len(leads)} leads.")

	def _toggle_source_group(self, header, content_frame, leads):
		start_time = time.perf_counter()
		header_label = header.winfo_children()[0]
		if header._is_expanded:
			content_frame.pack_forget()
			header_label.configure(text=header_label.cget("text").replace("▼", "▶"))
			header._is_expanded = False
		else:
			header_label.configure(text=header_label.cget("text").replace("▶", "▼"))
			content_frame.pack(fill="x", padx=2, after=header)
			header._is_expanded = True
			start_time = time.perf_counter()
			if not content_frame.winfo_children():
				self._create_lead_widgets(content_frame, leads)
		end_time = time.perf_counter()
		logger.debug(f"[APP]: Expanding source group took {end_time - start_time:.2f} seconds.")

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
			TkToolTip(subject_label, message=lead_data.title, delay=0.25, follow=True, x_offset=tooltip_x,
					   y_offset=tooltip_y)
			self.triage_items.append({"frame": item_frame, "data": lead_data, "decision_var": decision_var})

	def confirm_triage_action(self):
		"""Process all leads with decisions (CASE, NOT_CASE, or SKIP)"""
		processed_count = 0

		# Iterate through all tree items
		results = {
			'CASE':     [],
			'NOT_CASE': [],
			'SKIP':     []
		}

		for item_id, lead in self.tree_lead_data.items():
			decision = self.triage_tree.set(item_id, 'decision')
			if decision in results:
				results[decision].append(lead.lead_uuid)
				processed_count += 1

		# One call, db_manager handles routing
		db_manager.process_triage(results)


		logger.info(f"[APP]: Processed {processed_count} leads. Refreshing list...")
		self.refresh_triage_list()

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
		images = []

		if lead_data.url is not None:
			extracted_links.append({'text':      '🔗 Lead URL',
			                        'url':       lead_data.url,
			                        'type':      'url',
			                        'lead_uuid': lead_data.lead_uuid})
		if lead_data.metadata is not None:
			metadata = lead_data.metadata
			if metadata.__contains__('article_url'):
				metadata_link = metadata.get('article_url')
				extracted_links.append({'text':      '🔗 Article URL',
				                        'url':       metadata_link,
				                        'lead_uuid': lead_data.lead_uuid})

			if metadata.__contains__('article_image'):
				extracted_links.append(
						{'text':      '🖼️ Article Image',
						 'url':       metadata.get('article_image'),
						 'type':      'image',
						 'lead_uuid': lead_data.lead_uuid})

			if metadata.__contains__('media'):
				media = metadata.get('media')
				media_url = media.get('url')
				media_fallback_url = media.get('fallback_url')
				media_type = media.get('type')
				duration = media.get('duration', 0)

				match media_type:
					case 'video':
						# Add to links with duration if available
						label = f"🎞️ {media_type.title()} ({duration}s)" if duration else media_type.title()
						extracted_links.append({'text':         label,
						                        'url':          media_url if media_url else media_fallback_url,
						                        'fallback_url': media_fallback_url,
						                        'type':         'video',
						                        'lead_uuid':    lead_data.lead_uuid})
					case 'image':
						label = f"🖼️ {media_type.title()}"
						extracted_links.append({'text':      label,
						                        'url':       media_url,
						                        'type':      'image',
						                        'lead_uuid': lead_data.lead_uuid})
					case 'gallery':
						gallery_items = media.get('url', [])
						i = 0
						for item in gallery_items:
							i = i + 1
							extracted_links.append({'text':      f"🖼️ Gallery Image {i}:",
							                        'url':       item,
							                        'type':      'image',
							                        'lead_uuid': lead_data.lead_uuid})

					case _:
						logger.warning(f"Unhandled media type: {media_type}")
						pass

		if not extracted_links:
			ctk.CTkLabel(links_frame, text="No links found.", font=self.main_font, text_color="gray").pack()
		else:
			counter = 1
			for link in extracted_links:
				link_text = f"{counter:>2d}: {link['text']}"
				link_label = ctk.CTkLabel(links_frame, text=link_text, anchor="w", cursor="hand2", font=self.main_font,
										  text_color=ACCENT_COLOR)
				link_label.pack(fill="x", padx=5, pady=2)
				if link.get('type') == 'video':
					click_handler = partial(self._show_video_menu,
					                        link['url'],  # hls for viewing
					                        link['fallback_url'],  # mp4 for analysis
					                        link['lead_uuid'])
					link_label.bind("<Button-1>", click_handler)
				elif link.get('type') == 'image':
					click_handler = partial(self.show_image, link['url'], lead_uuid)
				else:
					click_handler = partial(self.open_link_in_browser, link['url'])
				link_label.bind("<Button-1>", click_handler)
				TkToolTip(links_frame, message=link["url"])
				counter += 1

	def _show_video_menu(self, hls_url, fallback_url, lead_uuid, event):
		"""
		Show video menu
		"""

		def open_in_browser(url: str):
			import webbrowser
			threading.Thread(
					target=lambda: webbrowser.open_new_tab(url),
					daemon=True
			).start()

		menu = Menu(self, tearoff=0)
		menu.add_command(label="▶ Open in browser", command=lambda: [menu.destroy(), open_in_browser(hls_url)])
		menu.add_separator()
		if fallback_url:
			menu.add_command(label="🔍 Analyze",
			                 command=lambda: [menu.destroy(), self.analyze_video(fallback_url, lead_uuid=lead_uuid)])
		menu.post(event.x_root, event.y_root)

	@staticmethod
	def _is_link_alive(link):
		import requests
		response = 0
		try:
			response = requests.head(link, timeout=5, allow_redirects=True)
			logger.info(f"[APP]: Link status: {response.status_code}")
			return response.status_code == 200
		except:
			logger.info(f"[APP]: Link status: {response.status_code}")
			return False

	def analyze_video(self, video_url: str, lead_uuid):
		"""
		Open video in cv2 player for analysis
		"""
		if not self._is_link_alive(video_url):
			logger.info(f"Video link not found: {video_url}")
			return False

		def run():
			from hunter.media_handlers.video_analysis import VideoAnalysis
			analyzer = VideoAnalysis(video_url, lead_uuid)
			analyzer.play()

		threading.Thread(target=run, daemon=True).start()
		logger.info(f"[APP]: Analyzing video: {video_url}")

	def show_image(self, image_url: str, case_uuid: uuid.UUID, event=None):
		"""Show image in a background thread to avoid blocking the GUI"""

		def show_in_thread():
			try:
				# Import your ImageViewer class directly
				# (adjust path if needed)
				from hunter.media_handlers.image_viewer import ImageViewer

				# Create the instance
				viewer = ImageViewer(image_url, case_uuid)

				# Run the blocking 'show' method
				# This call has cv2.waitKey(0) and will pause
				# *this thread* until the user closes the image.
				viewer.show()

			except Exception as e:
				logger.error(f"[IMAGE ERROR]: Failed to show image: {e}")

		# Start the thread, just like you do for the video
		thread = threading.Thread(target=show_in_thread, daemon=True)
		thread.start()
		logger.info(f"[APP]: Showing image: {image_url}")

	def play_video(self, video_url: str, event=None):
		"""Play video in a background thread to avoid blocking the GUI"""

		if not self._is_link_alive(video_url):
			logger.info(f"Video link not found: {video_url}")
			return False
		def play_in_thread():
			try:
				from hunter.media_handlers.video_player import VideoPlayer
				player = VideoPlayer(video_url)
				player.play()
			except Exception as e:
				logger.error(f"[VIDEO ERROR]: Failed to play video: {e}")

		thread = threading.Thread(target=play_in_thread, daemon=True)
		thread.start()
		logger.info(f"[APP]: Playing video: {video_url}")

	@staticmethod
	def get_article_image(self, url: str):
		"""Get the article image from the article URL"""
		import requests
		try:
			def download_and_process_image():
				import requests
				try:
					response = requests.get(url)
					response.raise_for_status()

					image_data = io.BytesIO(response.content)
					image = Image.open(image_data)
					image.thumbnail((200, 200))
					image_bytes = io.BytesIO()
					image.save(image_bytes, format='PNG')
					image.show()

					# Use after() to safely update GUI from background thread
					encoded = base64.b64encode(image_bytes.getvalue()).decode("utf-8")
					return "data:image/png;base64," + encoded

				except requests.exceptions.RequestException as e:
					logger.error(f"Error downloading image: {e}")
					return None
				except Image.UnidentifiedImageError:
					logger.error("Error: The data at the URL is not a valid image.")
					return None

			# Create and start background thread
			thread = threading.Thread(target=download_and_process_image)
			thread.daemon = True
			thread.start()

			# Return immediately while thread runs
			return None

		except Image.UnidentifiedImageError:
			print("Error: The data at the URL is not a valid image.")


	@staticmethod
	def _consume_scroll_event(event):
		"""A firewall to stop scroll events from propagating and causing errors."""
		return "break"

	@staticmethod
	def open_link_in_browser(url, event=None):
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
		logger.info("Closing database connection and shutting down.")
		# TODO: add db_manager close connection.
		#		if self.db_conn:
		#			self.db_conn.close()
		self.destroy()
