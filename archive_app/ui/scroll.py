import sys
import tkinter as tk
from tkinter import ttk

class AutoScrollbar(ttk.Scrollbar):
    def set(self, low: str, high: str) -> None:
        if float(low) <= 0.0 and float(high) >= 1.0:
            self.grid_remove()
        else:
            try:
                self.grid()
            except tk.TclError:
                pass
        super().set(low, high)

def _on_shift_scroll_global(event: tk.Event) -> None:
    widget = event.widget
    while widget:
        if isinstance(widget, (tk.Canvas, ttk.Treeview, tk.Text)):
            if getattr(event, "num", 0) == 4:
                widget.xview_scroll(-1, "units")
            elif getattr(event, "num", 0) == 5:
                widget.xview_scroll(1, "units")
            elif getattr(event, "delta", 0) != 0:
                if sys.platform == "darwin":
                    widget.xview_scroll(-event.delta, "units")
                else:
                    widget.xview_scroll(int(-event.delta / 120), "units")
            return
        widget = getattr(widget, "master", None)
