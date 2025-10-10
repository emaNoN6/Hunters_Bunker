# ==========================================================
# Hunter's Command Console - Satellite Control Panel
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import customtkinter as ctk
from tkinter import Canvas


class SatelliteControlApp(ctk.CTk):
	def __init__(self):
		super().__init__()

		self.title("Hunter's Bunker - Geospatial Command")
		self.geometry("1200x800")
		ctk.set_appearance_mode("dark")

		# --- Configure Grid Layout ---
		self.grid_columnconfigure(0, weight=3)  # Map panel
		self.grid_columnconfigure(1, weight=1)  # Control panel
		self.grid_rowconfigure(0, weight=1)

		# --- Map Panel (Left) ---
		self.map_frame = ctk.CTkFrame(self, fg_color="#1D1D1D")
		self.map_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
		self.map_frame.grid_rowconfigure(0, weight=1)
		self.map_frame.grid_columnconfigure(0, weight=1)

		self.map_canvas = Canvas(self.map_frame, bg="#2D2D2D", highlightthickness=0)
		self.map_canvas.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
		self.draw_placeholder_map()

		# --- Control Panel (Right) ---
		self.control_frame = ctk.CTkFrame(self)
		self.control_frame.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")
		self.control_frame.grid_columnconfigure(0, weight=1)

		# Title
		control_title = ctk.CTkLabel(self.control_frame, text="SATELLITE CONTROL",
		                             font=ctk.CTkFont(size=20, weight="bold"))
		control_title.grid(row=0, column=0, padx=20, pady=20, sticky="ew")

		# Satellite Selection
		satellite_label = ctk.CTkLabel(self.control_frame, text="Active Asset:")
		satellite_label.grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
		self.satellite_selector = ctk.CTkOptionMenu(self.control_frame,
		                                            values=["GEO-SCAN-01", "EMF-ORBITER-03", "SPECTRAL-EYE-02"])
		self.satellite_selector.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

		# Coordinate Input
		lat_label = ctk.CTkLabel(self.control_frame, text="Target Latitude:")
		lat_label.grid(row=3, column=0, padx=20, pady=(20, 0), sticky="w")
		self.lat_entry = ctk.CTkEntry(self.control_frame, placeholder_text="e.g., 40.2655")
		self.lat_entry.grid(row=4, column=0, padx=20, pady=5, sticky="ew")
		self.lat_entry.insert(0, "40.2655")  # Monongahela, PA

		lon_label = ctk.CTkLabel(self.control_frame, text="Target Longitude:")
		lon_label.grid(row=5, column=0, padx=20, pady=(10, 0), sticky="w")
		self.lon_entry = ctk.CTkEntry(self.control_frame, placeholder_text="e.g., -79.9295")
		self.lon_entry.grid(row=6, column=0, padx=20, pady=5, sticky="ew")
		self.lon_entry.insert(0, "-79.9295")  # Monongahela, PA

		# Tasking Button
		self.task_button = ctk.CTkButton(self.control_frame, text="Task Satellite", command=self.task_satellite)
		self.task_button.grid(row=7, column=0, padx=20, pady=20, sticky="ew")

		# Log/Info Panel
		info_label = ctk.CTkLabel(self.control_frame, text="Asset Status:")
		info_label.grid(row=8, column=0, padx=20, pady=(10, 0), sticky="w")
		self.info_textbox = ctk.CTkTextbox(self.control_frame)
		self.info_textbox.grid(row=9, column=0, padx=20, pady=5, sticky="nsew")
		self.control_frame.grid_rowconfigure(9, weight=1)
		self.log_to_panel("System ready. Awaiting tasking.")

	def draw_placeholder_map(self):
		# This is just a visual placeholder for a real map widget
		self.map_canvas.create_line(100, 400, 700, 100, fill="#4A4A4A", width=2)
		self.map_canvas.create_oval(300, 200, 310, 210, fill="red", outline="white")
		self.map_canvas.create_text(320, 205, text="Anomaly Detected", anchor="w", fill="white")

		self.map_canvas.create_oval(500, 350, 510, 360, fill="cyan", outline="white")
		self.map_canvas.create_text(520, 355, text="Case #341", anchor="w", fill="white")

	def task_satellite(self):
		lat = self.lat_entry.get()
		lon = self.lon_entry.get()
		asset = self.satellite_selector.get()

		if lat and lon:
			self.log_to_panel(f"Tasking {asset}...")
			self.log_to_panel(f"Targeting coordinates: ({lat}, {lon})")
			# In a real app, this would trigger the backend geocoding/analysis
			self.log_to_panel("Tasking command sent successfully.")
		else:
			self.log_to_panel("Error: Invalid coordinates.")

	def log_to_panel(self, message):
		self.info_textbox.configure(state="normal")
		self.info_textbox.insert("end", f"> {message}\n")
		self.info_textbox.configure(state="disabled")
		self.info_textbox.see("end")


if __name__ == "__main__":
	app = SatelliteControlApp()
	app.mainloop()
