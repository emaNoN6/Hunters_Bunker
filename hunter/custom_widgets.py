# hunter/custom_widgets.py

# ==========================================================
# Hunter's Command Console - Custom Widgets v2.0
# This version includes a more robust tooltip implementation
# that uses a placed frame instead of a Toplevel window to
# avoid event-loop conflicts.
# ==========================================================

import customtkinter as ctk

class OffsetToolTip:
    """
    A robust, custom tooltip that uses a placed frame to avoid the
    event-loop bugs associated with creating/destroying Toplevel windows.
    """

    def __init__(
        self,
        widget,
        text,
        delay: float = 0.5,
        x_offset: int = 20,
        y_offset: int = 10,
        **kwargs,
    ):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.kwargs = kwargs

        self._tooltip_frame = None
        self._display_after_id = None

        self.widget.bind("<Enter>", self._schedule_display)
        self.widget.bind("<Leave>", self._hide_tooltip)
        self.widget.bind("<Button-1>", self._hide_tooltip) # Hide on click

    def _schedule_display(self, event=None):
        """Schedules the tooltip to be displayed after a delay."""
        self._cancel_scheduled_display() # Cancel any pending tooltips
        self._display_after_id = self.widget.after(
            int(self.delay * 1000), self._display_tooltip
        )

    def _hide_tooltip(self, event=None):
        """Hides the tooltip frame."""
        self._cancel_scheduled_display()
        if self._tooltip_frame:
            self._tooltip_frame.place_forget() # Hide the frame
            self._tooltip_frame.destroy()      # Clean up the widgets
            self._tooltip_frame = None

    def _cancel_scheduled_display(self):
        """Helper to cancel a pending tooltip display."""
        if self._display_after_id:
            self.widget.after_cancel(self._display_after_id)
            self._display_after_id = None

    def _display_tooltip(self):
        """Creates and displays the tooltip frame at the correct position."""
        if self._tooltip_frame:
            return

        # --- THE NEW LOGIC ---
        # We create a CTkFrame on the top-level window, which is safer.
        toplevel_window = self.widget.winfo_toplevel()
        self._tooltip_frame = ctk.CTkFrame(toplevel_window, border_width=1, border_color="gray50")

        # Calculate position relative to the root window
        x = self.widget.winfo_rootx() + self.x_offset
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + self.y_offset

        label = ctk.CTkLabel(
            self._tooltip_frame,
            text=self.text,
            justify="left",
            **self.kwargs
        )
        label.pack(padx=8, pady=4)

        # Use .place() to position the frame on top of everything else
        self._tooltip_frame.place(x=x, y=y)
