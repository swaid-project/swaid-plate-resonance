"""Chladni Figure Simulator (v3 - modular).

This file remains as a backward-compatible entry point.
The codebase was refactored into the simulator package:
  - constants.py  - materials, colormaps, theme colors
  - physics.py    - physics engine (square, rectangular, circular)
  - gui.py        - graphical user interface
  - sweep.py      - frequency sweep window
  - __main__.py   - entry point (python -m simulator)
"""

import tkinter as tk
from simulator.gui import ChladniApp


if __name__ == "__main__":
    root = tk.Tk()
    ChladniApp(root)
    root.mainloop()
