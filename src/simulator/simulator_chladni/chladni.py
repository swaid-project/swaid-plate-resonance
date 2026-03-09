"""
Simulador de Figuras de Chladni  (v3 — modular)
=================================================
Este ficheiro mantém-se como ponto de entrada retrocompatível.
O código foi refactored para o package simulator:
  - constants.py  — materiais, colormaps, cores
  - physics.py    — motor de física (quadrada, rectangular, circular)
  - gui.py        — interface gráfica
  - sweep.py      — varrimento de frequência
  - __main__.py   — entry point (python -m simulator)
"""

import tkinter as tk
from simulator.gui import ChladniApp


if __name__ == "__main__":
    root = tk.Tk()
    ChladniApp(root)
    root.mainloop()
