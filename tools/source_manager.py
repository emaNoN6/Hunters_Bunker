#  ==========================================================
#   Hunter's Command Console
#
#   File: source_manager.py
#   Last modified: 2026-01-10 19:50:20
#
#   Copyright (c) 2026 emaNoN & Codex
#
#  ==========================================================
# tools/source_manager.py
import customtkinter as ctk
from tkinter import ttk, messagebox
import sys
import os

# Add parent to path so we can import from hunter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hunter import db_manager

ctk.set_appearance_mode("dark")


class SourceManager(ctk.CTk):
	def __init__(self):
		super().__init__()
		self.title("Source Manager")
		self.geometry("900x600")

		self.db_conn = db_manager.get_db_connection()

		self._build_ui()
		self._load_domains()

	def _build_ui(self):
		# Left side - Domains
		left_frame = ctk.CTkFrame(self)
		left_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

		ctk.CTkLabel(left_frame, text="Source Domains", font=("", 16, "bold")).pack(pady=5)

		self.domain_tree = ttk.Treeview(left_frame, columns=("name", "agent", "max_req"), show="headings", height=10)
		self.domain_tree.heading("name", text="Domain")
		self.domain_tree.heading("agent", text="Agent Type")
		self.domain_tree.heading("max_req", text="Max Requests")
		self.domain_tree.column("name", width=120)
		self.domain_tree.column("agent", width=100)
		self.domain_tree.column("max_req", width=80)
		self.domain_tree.pack(fill="both", expand=True, padx=5, pady=5)
		self.domain_tree.bind("<<TreeviewSelect>>", self._on_domain_select)

		domain_btn_frame = ctk.CTkFrame(left_frame)
		domain_btn_frame.pack(fill="x", padx=5, pady=5)
		ctk.CTkButton(domain_btn_frame, text="Add", width=60, command=self._add_domain).pack(side="left", padx=2)
		ctk.CTkButton(domain_btn_frame, text="Edit", width=60, command=self._edit_domain).pack(side="left", padx=2)
		ctk.CTkButton(domain_btn_frame, text="Delete", width=60, command=self._delete_domain).pack(side="left", padx=2)

		# Right side - Sources
		right_frame = ctk.CTkFrame(self)
		right_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

		ctk.CTkLabel(right_frame, text="Sources", font=("", 16, "bold")).pack(pady=5)

		self.source_tree = ttk.Treeview(right_frame, columns=("name", "target", "active"), show="headings", height=10)
		self.source_tree.heading("name", text="Source Name")
		self.source_tree.heading("target", text="Target")
		self.source_tree.heading("active", text="Active")
		self.source_tree.column("name", width=150)
		self.source_tree.column("target", width=120)
		self.source_tree.column("active", width=60)
		self.source_tree.pack(fill="both", expand=True, padx=5, pady=5)

		source_btn_frame = ctk.CTkFrame(right_frame)
		source_btn_frame.pack(fill="x", padx=5, pady=5)
		ctk.CTkButton(source_btn_frame, text="Add", width=60, command=self._add_source).pack(side="left", padx=2)
		ctk.CTkButton(source_btn_frame, text="Edit", width=60, command=self._edit_source).pack(side="left", padx=2)
		ctk.CTkButton(source_btn_frame, text="Delete", width=60, command=self._delete_source).pack(side="left", padx=2)
		ctk.CTkButton(source_btn_frame, text="Toggle", width=60, command=self._toggle_source).pack(side="left", padx=2)

	def _load_domains(self):
		for item in self.domain_tree.get_children():
			self.domain_tree.delete(item)

		sql = "SELECT id, domain_name, agent_type, max_concurrent_requests FROM almanac.source_domains ORDER BY domain_name"
		with self.db_conn.cursor() as cur:
			cur.execute(sql)
			for row in cur.fetchall():
				self.domain_tree.insert("", "end", iid=row[0], values=(row[1], row[2], row[3]))

	def _load_sources(self, domain_id):
		for item in self.source_tree.get_children():
			self.source_tree.delete(item)

		sql = """SELECT id, source_name, target, is_active 
                 FROM almanac.sources WHERE domain_id = %s ORDER BY source_name"""
		with self.db_conn.cursor() as cur:
			cur.execute(sql, (domain_id,))
			for row in cur.fetchall():
				active = "✓" if row[3] else "✗"
				self.source_tree.insert("", "end", iid=row[0], values=(row[1], row[2], active))

	def _on_domain_select(self, event):
		selected = self.domain_tree.selection()
		if selected:
			self._load_sources(selected[0])

	def _get_selected_domain_id(self):
		selected = self.domain_tree.selection()
		return selected[0] if selected else None

	def _get_selected_source_id(self):
		selected = self.source_tree.selection()
		return selected[0] if selected else None

	# === Domain CRUD ===
	def _add_domain(self):
		DomainDialog(self, "Add Domain", self._save_new_domain)

	def _edit_domain(self):
		domain_id = self._get_selected_domain_id()
		if not domain_id:
			return

		sql = "SELECT domain_name, agent_type, max_concurrent_requests, notes FROM almanac.source_domains WHERE id = %s"
		with self.db_conn.cursor() as cur:
			cur.execute(sql, (domain_id,))
			row = cur.fetchone()

		DomainDialog(self, "Edit Domain", lambda data: self._save_edit_domain(domain_id, data),
		             initial={"name": row[0], "agent": row[1], "max_req": row[2], "notes": row[3] or ""})

	def _save_new_domain(self, data):
		sql = """INSERT INTO almanac.source_domains (domain_name, agent_type, max_concurrent_requests, notes)
                 VALUES (%s, %s, %s, %s)"""
		with self.db_conn.cursor() as cur:
			cur.execute(sql, (data["name"], data["agent"], data["max_req"], data["notes"]))
		self.db_conn.commit()
		self._load_domains()

	def _save_edit_domain(self, domain_id, data):
		sql = """UPDATE almanac.source_domains 
                 SET domain_name=%s, agent_type=%s, max_concurrent_requests=%s, notes=%s 
                 WHERE id=%s"""
		with self.db_conn.cursor() as cur:
			cur.execute(sql, (data["name"], data["agent"], data["max_req"], data["notes"], domain_id))
		self.db_conn.commit()
		self._load_domains()

	def _delete_domain(self):
		domain_id = self._get_selected_domain_id()
		if not domain_id:
			return
		if not messagebox.askyesno("Confirm", "Delete this domain and all its sources?"):
			return

		with self.db_conn.cursor() as cur:
			cur.execute("DELETE FROM almanac.sources WHERE domain_id = %s", (domain_id,))
			cur.execute("DELETE FROM almanac.source_domains WHERE id = %s", (domain_id,))
		self.db_conn.commit()
		self._load_domains()
		for item in self.source_tree.get_children():
			self.source_tree.delete(item)

	# === Source CRUD ===
	def _add_source(self):
		domain_id = self._get_selected_domain_id()
		if not domain_id:
			messagebox.showwarning("Select Domain", "Select a domain first")
			return
		SourceDialog(self, "Add Source", lambda data: self._save_new_source(domain_id, data))

	def _edit_source(self):
		source_id = self._get_selected_source_id()
		domain_id = self._get_selected_domain_id()
		if not source_id:
			return

		sql = "SELECT source_name, target, keywords, strategy FROM almanac.sources WHERE id = %s"
		with self.db_conn.cursor() as cur:
			cur.execute(sql, (source_id,))
			row = cur.fetchone()

		SourceDialog(self, "Edit Source", lambda data: self._save_edit_source(source_id, domain_id, data),
		             initial={"name": row[0], "target": row[1], "keywords": row[2] or "", "strategy": row[3] or ""})

	def _save_new_source(self, domain_id, data):
		sql = """INSERT INTO almanac.sources (source_name, domain_id, target, keywords, strategy)
                 VALUES (%s, %s, %s, %s, %s)"""
		with self.db_conn.cursor() as cur:
			cur.execute(sql, (data["name"], domain_id, data["target"], data["keywords"], data["strategy"]))
		self.db_conn.commit()
		self._load_sources(domain_id)

	def _save_edit_source(self, source_id, domain_id, data):
		sql = """UPDATE almanac.sources 
                 SET source_name=%s, target=%s, keywords=%s, strategy=%s 
                 WHERE id=%s"""
		with self.db_conn.cursor() as cur:
			cur.execute(sql, (data["name"], data["target"], data["keywords"], data["strategy"], source_id))
		self.db_conn.commit()
		self._load_sources(domain_id)

	def _delete_source(self):
		source_id = self._get_selected_source_id()
		domain_id = self._get_selected_domain_id()
		if not source_id:
			return
		if not messagebox.askyesno("Confirm", "Delete this source?"):
			return

		with self.db_conn.cursor() as cur:
			cur.execute("DELETE FROM almanac.sources WHERE id = %s", (source_id,))
		self.db_conn.commit()
		self._load_sources(domain_id)

	def _toggle_source(self):
		source_id = self._get_selected_source_id()
		domain_id = self._get_selected_domain_id()
		if not source_id:
			return

		sql = "UPDATE almanac.sources SET is_active = NOT is_active WHERE id = %s"
		with self.db_conn.cursor() as cur:
			cur.execute(sql, (source_id,))
		self.db_conn.commit()
		self._load_sources(domain_id)


class DomainDialog(ctk.CTkToplevel):
	def __init__(self, parent, title, on_save, initial=None):
		super().__init__(parent)
		self.title(title)
		self.geometry("300x250")
		self.on_save = on_save

		ctk.CTkLabel(self, text="Domain Name:").pack(pady=(10, 0))
		self.name_entry = ctk.CTkEntry(self, width=250)
		self.name_entry.pack(pady=5)

		ctk.CTkLabel(self, text="Agent Type:").pack(pady=(10, 0))
		self.agent_entry = ctk.CTkEntry(self, width=250)
		self.agent_entry.pack(pady=5)

		ctk.CTkLabel(self, text="Max Concurrent Requests:").pack(pady=(10, 0))
		self.max_req_entry = ctk.CTkEntry(self, width=250)
		self.max_req_entry.pack(pady=5)

		ctk.CTkLabel(self, text="Notes:").pack(pady=(10, 0))
		self.notes_entry = ctk.CTkEntry(self, width=250)
		self.notes_entry.pack(pady=5)

		ctk.CTkButton(self, text="Save", command=self._save).pack(pady=15)

		if initial:
			self.name_entry.insert(0, initial["name"])
			self.agent_entry.insert(0, initial["agent"])
			self.max_req_entry.insert(0, str(initial["max_req"]))
			self.notes_entry.insert(0, initial["notes"])
		else:
			self.max_req_entry.insert(0, "1")

	def _save(self):
		self.on_save({
			"name":    self.name_entry.get(),
			"agent":   self.agent_entry.get(),
			"max_req": int(self.max_req_entry.get() or 1),
			"notes":   self.notes_entry.get()
		})
		self.destroy()


class SourceDialog(ctk.CTkToplevel):
	def __init__(self, parent, title, on_save, initial=None):
		super().__init__(parent)
		self.title(title)
		self.geometry("300x280")
		self.on_save = on_save

		ctk.CTkLabel(self, text="Source Name:").pack(pady=(10, 0))
		self.name_entry = ctk.CTkEntry(self, width=250)
		self.name_entry.pack(pady=5)

		ctk.CTkLabel(self, text="Target (subreddit, topic, etc):").pack(pady=(10, 0))
		self.target_entry = ctk.CTkEntry(self, width=250)
		self.target_entry.pack(pady=5)

		ctk.CTkLabel(self, text="Keywords (comma separated):").pack(pady=(10, 0))
		self.keywords_entry = ctk.CTkEntry(self, width=250)
		self.keywords_entry.pack(pady=5)

		ctk.CTkLabel(self, text="Strategy:").pack(pady=(10, 0))
		self.strategy_entry = ctk.CTkEntry(self, width=250)
		self.strategy_entry.pack(pady=5)

		ctk.CTkButton(self, text="Save", command=self._save).pack(pady=15)

		if initial:
			self.name_entry.insert(0, initial["name"])
			self.target_entry.insert(0, initial["target"])
			self.keywords_entry.insert(0, initial["keywords"])
			self.strategy_entry.insert(0, initial["strategy"])

	def _save(self):
		self.on_save({
			"name":     self.name_entry.get(),
			"target":   self.target_entry.get(),
			"keywords": self.keywords_entry.get(),
			"strategy": self.strategy_entry.get()
		})
		self.destroy()


if __name__ == "__main__":
	app = SourceManager()
	app.mainloop()
