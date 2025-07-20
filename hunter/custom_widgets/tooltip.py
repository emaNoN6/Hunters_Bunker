"""
CTkToolTip Widget
version: 0.8 (modified)
 - reduced default y_offset
 - cancels pending after calls to prevent residual tooltips
"""

import time
import sys
import customtkinter
from tkinter import Toplevel, Frame


class CTkToolTip(Toplevel):
    def __init__(
        self,
        widget: any,
        message: str = None,
        delay: float = 0.2,
        follow: bool = True,
        x_offset: int = 0,
        y_offset: int = 4,  # ← reduced from 10
        container: any = None,
        bg_color: str = None,
        corner_radius: int = 10,
        border_width: int = 0,
        border_color: str = None,
        alpha: float = 0.95,
        padding: tuple = (10, 2),
        **message_kwargs,
    ):
        super().__init__()
        self.widget = widget
        self.container = container or widget.master

        # state and scheduling
        self.delay = delay
        self.follow = follow
        self.x_offset = x_offset
        self.y_offset = y_offset
        self._after_id = None  # ← will hold the scheduled callback
        self.disable = False
        self.status = "outside"
        self.last_moved = 0

        # standard Toplevel setup
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-alpha", alpha)
        self._setup_transparency(bg_color, corner_radius)

        # build UI
        self._build_widgets(
            message,
            padding,
            corner_radius,
            border_width,
            border_color,
            **message_kwargs,
        )

        # bind events on widget + tooltip to avoid flicker
        self._bind_events()

    def _setup_transparency(self, bg_color, corner_radius):
        # platform‐specific transparency logic
        if sys.platform.startswith("win"):
            tc = self.widget._apply_appearance_mode(
                customtkinter.ThemeManager.theme["CTkToplevel"]["fg_color"]
            )
            self.transparent_color = tc
            self.attributes("-transparentcolor", tc)
            self.transient()
        elif sys.platform.startswith("darwin"):
            self.transparent_color = "systemTransparent"
            self.attributes("-transparent", True)
            self.transient(self.master)
        else:
            self.transparent_color = "#000001"
            corner_radius = 0
            self.transient()

        self.resizable(width=True, height=True)
        self.config(background=self.transparent_color)

    def _build_widgets(
        self,
        message,
        padding,
        corner_radius,
        border_width,
        border_color,
        **message_kwargs,
    ):
        self.messageVar = customtkinter.StringVar(value=message)

        # outer transparent frame
        tf = Frame(self, bg=self.transparent_color)
        tf.pack(fill="both", expand=True)

        # actual CTkFrame
        fg = (
            customtkinter.ThemeManager.theme["CTkFrame"]["fg_color"]
            if border_color is None
            else border_color
        )
        self.frame = customtkinter.CTkFrame(
            tf,
            bg_color=self.transparent_color,
            corner_radius=corner_radius,
            border_width=border_width,
            fg_color=fg,
        )
        self.frame.pack(fill="both", expand=True)

        # label
        self.message_label = customtkinter.CTkLabel(
            self.frame, textvariable=self.messageVar, **message_kwargs
        )
        self.message_label.pack(
            fill="both",
            padx=padding[0] + border_width,
            pady=padding[1] + border_width,
            expand=True,
        )

    def _bind_events(self):
        w = self.widget
        w.bind("<Enter>", self.on_enter, add="+")
        w.bind("<Motion>", self.on_enter, add="+")
        w.bind("<Leave>", self.on_leave, add="+")
        w.bind("<Destroy>", lambda _: self.hide(), add="+")

        # keep pointer-over-tooltip from hiding it
        self.bind("<Enter>", self._on_tooltip_enter)
        self.bind("<Leave>", self._on_tooltip_leave)
        self._pointer_over_tooltip = False

    def on_enter(self, event):
        if self.disable:
            return

        self.last_moved = time.time()
        if self.status == "outside":
            self.status = "inside"

        if not self.follow:
            self.withdraw()

        # cancel any pending show
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

        # measure container for clamping
        c = self.container
        c.update_idletasks()
        left = c.winfo_rootx() + 4
        right = c.winfo_rootx() + c.winfo_width() - 4

        # measure tooltip size
        self.message_label.update_idletasks()
        tip_w = self.message_label.winfo_reqwidth()
        tip_h = self.winfo_reqheight()

        # compute centered X + clamp
        px = event.x_root + self.x_offset
        desired_x = px - (tip_w // 2)
        if desired_x < left:
            x = left
        elif desired_x + tip_w > right:
            x = right - tip_w
        else:
            x = desired_x

        # compute Y
        py = event.y_root + self.y_offset
        # if the tooltip would overlap pointer, flip above
        if py <= event.y_root + tip_h:
            y = event.y_root - tip_h - abs(self.y_offset)
        else:
            y = py

        # move & schedule show
        self.geometry(f"+{x}+{y}")
        self._after_id = self.after(int(self.delay * 1000), self._show)

    def _on_tooltip_enter(self, _e):
        self._pointer_over_tooltip = True

    def _on_tooltip_leave(self, _e):
        self._pointer_over_tooltip = False
        # if pointer is also outside widget, hide
        self.on_leave()

    def on_leave(self, event=None):
        # don't hide if pointer just moved over tooltip
        if self._pointer_over_tooltip:
            return

        # cancel pending show
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

        self.status = "outside"
        self.withdraw()

    def _show(self):
        self._after_id = None
        if not self.widget.winfo_exists():
            self.destroy()
            return

        # only show if still inside after the delay
        if self.status == "inside" and (time.time() - self.last_moved) >= self.delay:
            self.status = "visible"
            self.deiconify()

    def hide(self):
        # cancel any leftover callback
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

        self.disable = True
        self.withdraw()

    def is_disabled(self):
        return self.disable

    def get(self):
        return self.messageVar.get()

    def configure(self, message=None, delay=None, bg_color=None, **kwargs):
        if delay is not None:
            self.delay = delay
        if bg_color is not None:
            self.frame.configure(fg_color=bg_color)
        if message is not None:
            self.messageVar.set(message)
        if kwargs:
            self.message_label.configure(**kwargs)
