# This file will hold our custom-forged tools. We're keeping our
# workshop clean and organized.

import customtkinter as ctk
from CTkToolTip import CTkToolTip as _BaseToolTip


class OffsetToolTip:
    """
    A completely custom tooltip implementation that gives us full control
    over positioning and behavior, solving all previous bugs.
    """

    def __init__(
        self,
        widget,
        message: str = "",
        delay: float = 0.5,
        x_offset: int = 20,
        y_offset: int = 10,
        **kwargs,
    ):

        self.widget = widget
        self.message = message
        self.delay = delay
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.kwargs = kwargs

        self.tooltip_window = None
        self._display_after_id = None

        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        """Schedules the tooltip to be displayed."""
        self._cancel_scheduled_display()
        self._display_after_id = self.widget.after(
            int(self.delay * 1000), self._display_tooltip
        )

    def _on_leave(self, event=None):
        """Hides the tooltip window correctly."""
        self._cancel_scheduled_display()
        if self.tooltip_window is not None:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def _cancel_scheduled_display(self):
        """Helper to cancel a pending tooltip display."""
        if self._display_after_id is not None:
            self.widget.after_cancel(self._display_after_id)
            self._display_after_id = None

    def _display_tooltip(self):
        """Creates and displays the tooltip window at the correct position."""
        if self.tooltip_window is not None:
            return

        x = self.widget.winfo_rootx() + self.x_offset
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + self.y_offset

        self.tooltip_window = tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{int(x)}+{int(y)}")

        # --- THE FIX IS HERE ---
        # We create the label and simply unpack our kwargs.
        # The wraplength is already inside self.kwargs if it was passed.
        label = ctk.CTkLabel(
            master=tw, text=self.message, justify="left", **self.kwargs
        )  # Unpack the stored kwargs here
        label.pack(padx=(10, 10), pady=(4, 4))
