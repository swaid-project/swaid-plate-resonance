"""
Janela de varrimento de frequência (Frequency Sweep Simulation).
Gera imagens do padrão de Chladni para cada frequência num intervalo definido.
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

    def __init__(self, parent, physics, params):
        """
        params dict keys:
            Lx, Ly, D, rho, h, transducers, n_modes, damping, sign,
            geometry, freq_start, freq_end, freq_step, material_name
        """
        self.physics = physics
        self.params = params
        self._running = False
        self._current_idx = 0

        freqs = np.arange(params["freq_start"],
                          params["freq_end"] + params["freq_step"] / 2,
                          params["freq_step"])
        self.freqs = freqs
        self.n_total = len(freqs)

        self.win = tk.Toplevel(parent)
        self.win.title("Varrimento de Frequência")
        self.win.geometry("800x700")
        self.win.configure(bg=Theme.BG)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

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

        freq = self.freqs[self._current_idx]
        p = self.params

        sand, Z_3d = self.physics.sand_and_3d(
            freq, p["Lx"], p["Ly"], p["D"], p["rho"], p["h"],
            p["transducers"], n_modes=p["n_modes"],
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

        ax.set_title(f"{freq:.0f} Hz", color=Theme.FG, fontsize=14,
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
            fname = os.path.join(save_dir,
                                 f"chladni_{freq:07.1f}Hz.png")
            self.fig.savefig(fname, dpi=150, facecolor=Theme.PL_BG)

        # Update progress
        self._current_idx += 1
        self.progress["value"] = self._current_idx
        self.status_label.config(
            text=f"{self._current_idx} / {self.n_total}")
        self.freq_label.config(text=f"{freq:.0f} Hz")

        # Schedule next step
        self.win.after(self.speed_var.get(), self._step)

    def _on_close(self):
        self._running = False
        self.win.destroy()
