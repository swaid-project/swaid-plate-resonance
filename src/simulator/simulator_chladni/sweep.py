"""Frequency sweep simulation window.

Generates one Chladni pattern image per frequency in a chosen range.
"""

import os
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .constants import SAND_CMAP, Theme


class SweepWindow:
    """Toplevel window that runs a frequency sweep, displaying and
    optionally saving the Chladni pattern at each step."""

    # Uniqueness filter settings for automatic sweeps.
    NODAL_THRESHOLD = 0.80
    IOU_DUPLICATE = 0.90
    HASH_SIZE = 24

    @staticmethod
    def _with_phase(transducer, phase_deg):
        """Return transducer tuple with updated phase, preserving extras."""
        t = list(transducer)
        if len(t) < 4:
            raise ValueError("Transducer must have at least 4 fields.")
        t[3] = phase_deg
        return tuple(t)

    def __init__(self, parent, physics, params):
        """
        params dict keys:
            Lx, Ly, D, rho, h, transducers, n_modes, damping, sign,
            geometry, freq_start, freq_end, freq_step, material_name,
            sweep_mode, sweep_phase
        """
        self.physics = physics
        self.params = params
        self._running = False
        self._current_idx = 0

        self.frames = []
        mode = params.get("sweep_mode", "Clássico (Passo)")
        phase_opt = params.get("sweep_phase", "Fase Atual")
        
        if mode == "Clássico (Passo)":
            freqs = np.arange(params["freq_start"],
                              params["freq_end"] + params["freq_step"] / 2,
                              params["freq_step"])
            for f in freqs:
                self.frames.append((f, params["transducers"], ""))
        else:
            # Resonances (Automático)
            freq_start = params["freq_start"]
            freq_end = params["freq_end"]
            geom = params["geometry"]
            Lx, Ly = params["Lx"], params["Ly"]
            D, rho, h = params["D"], params["rho"], params["h"]
            nm, sign = params["n_modes"], params["sign"]

            # Compute theoretical resonances
            if geom == "Circular":
                R = Lx / 2.0
                self.physics._build_cache_circ(R, nm, D, rho, h)
            else:
                self.physics._build_cache_rect(Lx, Ly, sign, nm, D, rho, h)
            
            res_set = set()
            for fnm in self.physics._f_nm:
                if freq_start <= fnm <= freq_end:
                    res_set.add(round(float(fnm), 1))
            ordered_freqs = sorted(res_set)
            
            base_trans = params["transducers"]
            n_t = len(base_trans)
            
            combinations = []
            if phase_opt == "Fase Atual":
                combinations.append(("Atual", base_trans))
            elif phase_opt == "Uniforme (0°)":
                combinations.append((
                    "Uniforme",
                    [self._with_phase(t, 0.0) for t in base_trans],
                ))
            else:
                # "Múltiplas Fases (Auto)"
                combinations.append((
                    "Unif",
                    [self._with_phase(t, 0.0) for t in base_trans],
                ))
                if n_t >= 4:
                    # Distintos: 0, 90, 180, 270
                    phases = [0.0, 90.0, 180.0, 270.0]
                    c_dist = [
                        self._with_phase(base_trans[i], phases[i % 4])
                        for i in range(n_t)
                    ]
                    combinations.append(("Distintos", c_dist))
                    
                    # Pares Adjacentes: 0, 0, 180, 180
                    phases_adj = [0.0, 0.0, 180.0, 180.0]
                    c_adj = [
                        self._with_phase(base_trans[i], phases_adj[i % 4])
                        for i in range(n_t)
                    ]
                    combinations.append(("Pares_Adj", c_adj))
                    
                    # Pares Diagonais: 0, 180, 180, 0
                    phases_diag = [0.0, 180.0, 180.0, 0.0]
                    c_diag = [
                        self._with_phase(base_trans[i], phases_diag[i % 4])
                        for i in range(n_t)
                    ]
                    combinations.append(("Pares_Diag", c_diag))
            
            raw_frames = []
            for f in ordered_freqs:
                for name, t_conf in combinations:
                    raw_frames.append((f, t_conf, name))

            # Keep only the best representative for each unique nodal symbol.
            self.frames = self._filter_unique_symbols(raw_frames)
                    
        self.n_total = len(self.frames)

        self.win = tk.Toplevel(parent)
        self.win.title("Varrimento de Frequência")
        self.win.geometry("800x700")
        self.win.configure(bg=Theme.BG)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

    @staticmethod
    def _nodal_mask_from_sand(sand, threshold):
        """Extract nodal lines as a binary mask from normalized sand map."""
        return sand >= float(threshold)

    @staticmethod
    def _dilate_mask_8(mask):
        """One-pixel 8-neighborhood dilation for small spatial tolerance."""
        p = np.pad(mask, ((1, 1), (1, 1)), mode="constant")
        return (
            p[1:-1, 1:-1]
            | p[:-2, :-2] | p[:-2, 1:-1] | p[:-2, 2:]
            | p[1:-1, :-2] | p[1:-1, 2:]
            | p[2:, :-2] | p[2:, 1:-1] | p[2:, 2:]
        )

    @staticmethod
    def _resize_bool_nearest(mask, out_h, out_w):
        """Nearest-neighbor resize for boolean masks without extra deps."""
        h, w = mask.shape
        yi = np.clip(np.round(np.linspace(0, h - 1, out_h)).astype(int),
                     0, h - 1)
        xi = np.clip(np.round(np.linspace(0, w - 1, out_w)).astype(int),
                     0, w - 1)
        return mask[np.ix_(yi, xi)]

    @staticmethod
    def _mask_hash(mask, hash_size):
        """Compact hash key from a downsampled binary nodal mask."""
        small = SweepWindow._resize_bool_nearest(mask, hash_size, hash_size)
        packed = np.packbits(small.astype(np.uint8), axis=None)
        return packed.tobytes()

    @staticmethod
    def _mask_iou(mask_a, mask_b):
        """Intersection over Union of two binary masks."""
        inter = np.count_nonzero(mask_a & mask_b)
        union = np.count_nonzero(mask_a | mask_b)
        if union == 0:
            return 1.0
        return inter / union

    @staticmethod
    def _symbol_quality(sand):
        """Higher means clearer symbol (stronger contrast and line salience)."""
        p95 = float(np.percentile(sand, 95.0))
        p05 = float(np.percentile(sand, 5.0))
        return p95 - p05

    def _filter_unique_symbols(self, frames):
        """Deduplicate automatic sweep frames using nodal-mask IoU."""
        if not frames:
            return []

        p = self.params
        entries = []
        buckets = {}

        for freq, trans, phase_label in frames:
            sand, _ = self.physics.sand_and_3d(
                freq, p["Lx"], p["Ly"], p["D"], p["rho"], p["h"],
                trans, n_modes=p["n_modes"], damping=p["damping"],
                sign=p["sign"], geometry=p["geometry"])

            mask = self._nodal_mask_from_sand(sand, self.NODAL_THRESHOLD)
            mask_tol = self._dilate_mask_8(mask)
            quality = self._symbol_quality(sand)
            key = self._mask_hash(mask_tol, self.HASH_SIZE)

            dup_idx = None
            for idx in buckets.get(key, []):
                iou = self._mask_iou(mask_tol, entries[idx]["mask"])
                if iou >= self.IOU_DUPLICATE:
                    dup_idx = idx
                    break

            if dup_idx is None:
                idx_new = len(entries)
                entries.append({
                    "frame": (freq, trans, phase_label),
                    "mask": mask_tol,
                    "quality": quality,
                })
                buckets.setdefault(key, []).append(idx_new)
            elif quality > entries[dup_idx]["quality"]:
                entries[dup_idx]["frame"] = (freq, trans, phase_label)
                entries[dup_idx]["mask"] = mask_tol
                entries[dup_idx]["quality"] = quality

        return [e["frame"] for e in entries]

    def _build_ui(self):
        top = ttk.Frame(self.win)
        top.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(top, text="Varrimento de Frequência",
                  font=("Segoe UI", 14, "bold"),
                  foreground=Theme.ACCENT, background=Theme.BG
                  ).pack(side=tk.LEFT)

        p = self.params
        info = (f"{p['material_name']} | "
                f"{p['geometry']} | "
                f"{p['freq_start']:.0f}–{p['freq_end']:.0f} Hz "
                f"(Δ={p['freq_step']:.0f} Hz) | "
                f"{self.n_total} imagens")
        ttk.Label(top, text=info, style="Small.TLabel").pack(
            side=tk.LEFT, padx=15)

        # Controls
        ctrl = ttk.Frame(self.win)
        ctrl.pack(fill=tk.X, padx=10, pady=5)

        self.btn_start = ttk.Button(ctrl, text="▶ Iniciar",
                                    command=self._start)
        self.btn_start.pack(side=tk.LEFT, padx=3)

        self.btn_pause = ttk.Button(ctrl, text="⏸ Pausar",
                                    command=self._pause, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=3)

        self.btn_stop = ttk.Button(ctrl, text="⏹ Parar",
                                   command=self._stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=3)

        ttk.Separator(ctrl, orient="vertical").pack(
            side=tk.LEFT, fill=tk.Y, padx=8)

        self.save_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(ctrl, text="Guardar imagens",
                        variable=self.save_var).pack(side=tk.LEFT, padx=3)

        self.btn_dir = ttk.Button(ctrl, text="📁 Pasta...",
                                  command=self._choose_dir)
        self.btn_dir.pack(side=tk.LEFT, padx=3)

        self.dir_var = tk.StringVar(value="")
        ttk.Label(ctrl, textvariable=self.dir_var,
                  style="Small.TLabel").pack(side=tk.LEFT, padx=5)

        # Speed control
        ttk.Label(ctrl, text="Vel.:").pack(side=tk.LEFT, padx=(10, 2))
        self.speed_var = tk.IntVar(value=200)
        tk.Scale(ctrl, from_=50, to=2000, resolution=50,
                 orient=tk.HORIZONTAL, variable=self.speed_var,
                 bg=Theme.BG, fg=Theme.FG, troughcolor=Theme.BG2,
                 highlightthickness=0, length=120,
                 sliderrelief="flat").pack(side=tk.LEFT)
        ttk.Label(ctrl, text="ms/frame", style="Small.TLabel").pack(
            side=tk.LEFT)

        # Progress
        prog_frame = ttk.Frame(self.win)
        prog_frame.pack(fill=tk.X, padx=10, pady=3)

        self.progress = ttk.Progressbar(prog_frame, maximum=self.n_total,
                                        mode="determinate")
        self.progress.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 5))

        self.freq_label = ttk.Label(prog_frame, text="—",
                                    style="Freq.TLabel")
        self.freq_label.pack(side=tk.RIGHT)

        self.status_label = ttk.Label(prog_frame,
                                      text=f"0 / {self.n_total}",
                                      style="Val.TLabel")
        self.status_label.pack(side=tk.RIGHT, padx=10)

        # Plot
        self.fig = Figure(figsize=(7, 5.5), facecolor=Theme.PL_BG, dpi=100)
        self.ax_pat = self.fig.add_axes([0.05, 0.05, 0.55, 0.90])
        self.ax_3d = self.fig.add_axes([0.62, 0.05, 0.36, 0.90],
                                       projection="3d")

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.win)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5,
                                         pady=5)

    def _choose_dir(self):
        d = filedialog.askdirectory(parent=self.win,
                                    title="Pasta para guardar imagens")
        if d:
            self.dir_var.set(d)

    def _start(self):
        if self._running:
            return
        if self.save_var.get() and not self.dir_var.get():
            messagebox.showwarning("Aviso",
                                   "Seleciona uma pasta primeiro.",
                                   parent=self.win)
            return
        self._running = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_pause.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.NORMAL)
        self._step()

    def _pause(self):
        self._running = False
        self.btn_start.config(state=tk.NORMAL)
        self.btn_pause.config(state=tk.DISABLED)

    def _stop(self):
        self._running = False
        self._current_idx = 0
        self.progress["value"] = 0
        self.status_label.config(text=f"0 / {self.n_total}")
        self.freq_label.config(text="—")
        self.btn_start.config(state=tk.NORMAL)
        self.btn_pause.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.DISABLED)

    def _step(self):
        if not self._running or self._current_idx >= self.n_total:
            self._running = False
            self.btn_start.config(state=tk.NORMAL)
            self.btn_pause.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.DISABLED)
            if self._current_idx >= self.n_total:
                messagebox.showinfo("Concluído",
                                    "Varrimento completo!",
                                    parent=self.win)
            return

        freq, current_trans, phase_label = self.frames[self._current_idx]
        p = self.params

        sand, Z_3d = self.physics.sand_and_3d(
            freq, p["Lx"], p["Ly"], p["D"], p["rho"], p["h"],
            current_trans, n_modes=p["n_modes"],
            damping=p["damping"], sign=p["sign"],
            geometry=p["geometry"])

        Lx, Ly = p["Lx"], p["Ly"]
        geom = p["geometry"]

        # 2D pattern
        ax = self.ax_pat
        ax.clear()

        if geom == "Circular":
            R = Lx / 2.0
            X, Y = self.physics.X_circ * 2.0 * R, self.physics.Y_circ * 2.0 * R
            ax.pcolormesh(X, Y, sand, cmap=SAND_CMAP, vmin=0, vmax=1,
                          shading="gouraud")
            theta_bnd = np.linspace(0, 2 * np.pi, 100)
            ax.plot(R * np.cos(theta_bnd), R * np.sin(theta_bnd),
                    color="#555", lw=1.5)
            ax.set_xlim(-R * 1.05, R * 1.05)
            ax.set_ylim(-R * 1.05, R * 1.05)
        else:
            ext = [-Lx / 2, Lx / 2, -Ly / 2, Ly / 2]
            ax.imshow(sand, cmap=SAND_CMAP, origin="lower", extent=ext,
                      interpolation="bilinear", vmin=0, vmax=1,
                      aspect="equal")
            ax.plot([-Lx/2, Lx/2, Lx/2, -Lx/2, -Lx/2],
                    [-Ly/2, -Ly/2, Ly/2, Ly/2, -Ly/2],
                    color="#555", lw=1.5)

        title_text = f"{freq:.0f} Hz"
        if phase_label:
            title_text += f" ({phase_label})"

        ax.set_title(title_text, color=Theme.FG, fontsize=14,
                     fontweight="bold")
        ax.set_facecolor(Theme.PL_BG)
        ax.tick_params(colors=Theme.FG_DIM, labelsize=7)
        for sp in ax.spines.values():
            sp.set_color(Theme.BG3)

        # 3D
        ax3 = self.ax_3d
        ax3.clear()
        step = max(1, self.physics.res // 50)

        if geom == "Circular":
            Xs = (self.physics.X_circ * Lx)[::step, ::step]
            Ys = (self.physics.Y_circ * Lx)[::step, ::step]
        else:
            Xs = (self.physics.X_norm * Lx)[::step, ::step]
            Ys = (self.physics.Y_norm * Ly)[::step, ::step]
        Zs = Z_3d[::step, ::step]

        ax3.plot_surface(Xs, Ys, Zs, cmap="coolwarm", alpha=0.88,
                         edgecolor="none", antialiased=True)
        ax3.set_title(f"Deformação", color=Theme.FG, fontsize=10, pad=0)
        ax3.set_facecolor(Theme.PL_BG)
        ax3.tick_params(colors=Theme.FG_DIM, labelsize=5)
        try:
            for a in (ax3.xaxis, ax3.yaxis, ax3.zaxis):
                a.pane.fill = False
                a.pane.set_edgecolor(Theme.BG3)
        except Exception:
            pass

        self.canvas.draw_idle()

        # Save if requested
        if self.save_var.get() and self.dir_var.get():
            save_dir = self.dir_var.get()
            suffix = f"_{phase_label}" if phase_label else ""
            fname = os.path.join(save_dir,
                                 f"chladni_{freq:07.1f}Hz{suffix}.png")
            self.fig.savefig(fname, dpi=150, facecolor=Theme.PL_BG)

        # Update progress
        self._current_idx += 1
        self.progress["value"] = self._current_idx
        self.status_label.config(
            text=f"{self._current_idx} / {self.n_total}")
        self.freq_label.config(text=title_text)

        # Schedule next step
        self.win.after(self.speed_var.get(), self._step)

    def _on_close(self):
        self._running = False
        self.win.destroy()
