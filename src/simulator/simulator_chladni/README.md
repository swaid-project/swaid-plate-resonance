# Chladni Plate Simulator

A physics-based simulator of [Chladni figures](https://en.wikipedia.org/wiki/Chladni_figures) — the standing-wave patterns that form when a vibrating plate causes sand (or particles) to collect along nodal lines.

Built on Kirchhoff thin-plate theory with modal superposition, supporting arbitrary transducer configurations with individual phase control.

---

## Features

| Feature | Details |
|---|---|
| **Plate geometries** | Square, Rectangular, Circular |
| **Materials** | Aluminium, Steel, Brass, Glass, Copper, Titanium |
| **Driven response** | Forced harmonic response via modal superposition with viscous damping |
| **Individual mode viewer** | Visualise any single mode (n, m) with its exact natural frequency |
| **Multi-transducer** | Add, move (drag), and remove transducers directly on the plate |
| **Per-transducer phase** | Set each transducer's phase independently (0°–360° slider or text entry) |
| **Phase presets** | 1-centre, 4-corners, 4-edges, 8-ring configurations |
| **Sand/particle simulation** | Particles driven by −∇(|w|²), physically matching acoustic radiation pressure — settling at nodal lines |
| **Particles-only view** | Toggle the wave heatmap off to see only particle positions |
| **3-D deformation view** | Real-time surface plot of the plate deflection |
| **Resonance spectrum** | Auto-computed frequency response with peak markers |
| **Snap to resonance** | One-click jump to the nearest resonant frequency |
| **Frequency sweep** | Animated sweep over a user-defined frequency range with optional frame saving |

---

## Requirements

- Python ≥ 3.9
- `numpy`, `scipy`, `matplotlib` (see [requirements.txt](../../../requirements.txt))
- A display / Tk backend (standard on Windows and most Linux desktops)

---

## How to run

All commands are run from the **repository root** (`swaid-plate-resonance/`).

### 1 — Install dependencies

```bash
# Create and activate a virtual environment (recommended)
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2 — Launch the simulator

```bash
# From the repository root
cd src
python -m simulator.simulator_chladni
```

---

## Quick-start guide

1. **Pick a material and geometry** in the left panel.
2. Set plate dimensions and thickness with the sliders.
3. Choose **"Resposta forçada"** (driven) or **"Modo individual"** view.
4. Drag the frequency slider or click **"Próxima ▶"** to jump to a resonance.
5. Click on the plate to add transducers; drag them to reposition.
6. Select a transducer in the list and use the **phase slider** (0°–360°) to set its individual phase.
7. Enable **"Mostrar partículas"** to watch sand settle onto nodal lines.
8. Enable **"Só partículas (sem onda)"** for a clean particle-only view.
9. Use **"▶ Iniciar Varrimento"** to run a frequency sweep animation.
