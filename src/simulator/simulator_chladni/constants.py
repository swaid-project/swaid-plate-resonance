"""Constants, materials, and colormaps for the Chladni simulator."""

from dataclasses import dataclass
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

@dataclass(frozen=True)
class MaterialSpec:
    """Material preset for real metal sheets available on market."""
    name: str
    E: float
    rho: float
    nu: float
    sizes_mm: tuple
    thicknesses_mm: tuple


@dataclass(frozen=True)
class VibrationSpeaker:
    """Physical constraints for a real vibration speaker transducer."""
    f_min: float = 20.0
    f_max: float = 20000.0
    nominal_power_w: float = 25.0
    diameter_m: float = 0.05
    mass_kg: float = 0.268


# ── Real materials ────────────────────────────────────────────────────────
MATERIAL_CATALOG = {
    "Aço Inoxidável 304 (Mirror 8K)": MaterialSpec(
        name="Aço Inoxidável 304 (Mirror 8K)",
        E=193e9,
        rho=8000.0,
        nu=0.29,
        sizes_mm=((100, 100), (100, 200), (200, 200),
                  (200, 300), (300, 300), (300, 400)),
        thicknesses_mm=(0.5, 0.8, 1.0, 1.5, 2.0),
    ),
    "Alumínio (High Reflective Mirror)": MaterialSpec(
        name="Alumínio (High Reflective Mirror)",
        E=69e9,
        rho=2700.0,
        nu=0.33,
        sizes_mm=((200, 200), (300, 300)),
        thicknesses_mm=(0.3, 0.4, 0.5, 0.8, 1.0),
    ),
}

# Legacy-friendly mapping consumed by GUI code (E/rho/nu fields).
MATERIALS = {
    name: {"E": spec.E, "rho": spec.rho, "nu": spec.nu,
           "sizes_mm": spec.sizes_mm,
           "thicknesses_mm": spec.thicknesses_mm}
    for name, spec in MATERIAL_CATALOG.items()
}

DEFAULT_MATERIAL = "Alumínio (High Reflective Mirror)"
DEFAULT_VIBRATION_SPEAKER = VibrationSpeaker()

# ── Supported geometries ──────────────────────────────────────────────────
GEOMETRIES = ["Quadrada", "Rectangular", "Circular"]

# ── Sand colormap ─────────────────────────────────────────────────────────
SAND_CMAP = LinearSegmentedColormap.from_list("sand", [
    "#080808", "#12100a", "#2a2010", "#503c1a",
    "#806830", "#b09050", "#d4b870", "#e8d8a8",
    "#f5ecd0", "#fffbf0",
], N=256)

# ── Theme colors ──────────────────────────────────────────────────────────
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

# ── J_n(x) zeros for circular plate (Bessel) ─────────────────────────────
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
