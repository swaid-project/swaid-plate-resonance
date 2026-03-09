"""
Constantes, materiais e colormaps para o simulador Chladni.
"""

import numpy as np
from matplotlib.colors import LinearSegmentedColormap

# ── Materiais ─────────────────────────────────────────────────────────────
MATERIALS = {
    "Alumínio": {"E": 69e9,  "rho": 2700, "nu": 0.33},
    "Aço":      {"E": 200e9, "rho": 7800, "nu": 0.30},
    "Latão":    {"E": 100e9, "rho": 8500, "nu": 0.34},
    "Vidro":    {"E": 70e9,  "rho": 2500, "nu": 0.24},
    "Cobre":    {"E": 117e9, "rho": 8960, "nu": 0.34},
    "Titânio":  {"E": 116e9, "rho": 4507, "nu": 0.32},
}

# ── Geometrias suportadas ─────────────────────────────────────────────────
GEOMETRIES = ["Quadrada", "Rectangular", "Circular"]

# ── Colormap areia ────────────────────────────────────────────────────────
SAND_CMAP = LinearSegmentedColormap.from_list("sand", [
    "#080808", "#12100a", "#2a2010", "#503c1a",
    "#806830", "#b09050", "#d4b870", "#e8d8a8",
    "#f5ecd0", "#fffbf0",
], N=256)

# ── Cores do tema ─────────────────────────────────────────────────────────
class Theme:
    BG     = "#1e1e2e"
    BG2    = "#282840"
    BG3    = "#353560"
    FG     = "#cdd6f4"
    FG_DIM = "#9399b2"
    ACCENT = "#89b4fa"
    RED    = "#f38ba8"
    GREEN  = "#a6e3a1"
    YELLOW = "#f9e2af"
    PL_BG  = "#111118"

# ── Zeros de J_n(x) para placa circular (Bessel) ─────────────────────────
# Pre-computed zeros of derivative of Bessel functions J'_n(x) = 0
# for free-edge circular plate: λ_nm values
# For clamped circular plate we use zeros of J_n(x)
BESSEL_ZEROS = {
    (0, 1): 2.4048, (0, 2): 5.5201, (0, 3): 8.6537,
    (1, 1): 3.8317, (1, 2): 7.0156, (1, 3): 10.1735,
    (2, 1): 5.1356, (2, 2): 8.4172, (2, 3): 11.6198,
    (3, 1): 6.3802, (3, 2): 9.7610, (3, 3): 13.0152,
    (4, 1): 7.5883, (4, 2): 11.0647, (4, 3): 14.3725,
    (5, 1): 8.7715, (5, 2): 12.3386, (5, 3): 15.7002,
}
