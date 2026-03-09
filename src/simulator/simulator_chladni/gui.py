"""
Interface gráfica (GUI) para o simulador de figuras de Chladni.
"""

import numpy as np
from scipy.signal import find_peaks
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import tkinter as tk
from tkinter import ttk

from .constants import MATERIALS, GEOMETRIES, SAND_CMAP, Theme
from .physics import ChladniPhysics
from .sweep import SweepWindow


class ChladniApp:
    """Main application window."""

    def __init__(self, root):
        self.root = root
        root.title("Simulador de Figuras de Chladni")
        root.geometry("1440x900")
        root.minsize(1100, 650)
        root.configure(bg=Theme.BG)

        self.physics = ChladniPhysics(resolution=200)
        # transducers: [(x, y, amplitude, phase_rad), ...]
        self.transducers = [(0.0, 0.0, 1.0, 0.0)]
        self._drag_idx = None
        self._update_id = None
        self._dragging = False
        self._particle_anim_id = None
        self._selected_trans_idx = 0

        self._configure_styles()
        self._build_ui()
        root.after(100, self.full_update)

    # ── Styles ────────────────────────────────────────────────────────
    def _configure_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        for name, kw in [
            (".",            {"background": Theme.BG,
                              "foreground": Theme.FG}),
            ("TFrame",       {"background": Theme.BG}),
            ("TLabel",       {"background": Theme.BG,
                              "foreground": Theme.FG,
                              "font": ("Segoe UI", 10)}),
            ("H.TLabel",     {"background": Theme.BG,
                              "foreground": Theme.ACCENT,
                              "font": ("Segoe UI", 11, "bold")}),
            ("Val.TLabel",   {"background": Theme.BG,
                              "foreground": Theme.YELLOW,
                              "font": ("Segoe UI", 10, "bold")}),
            ("Freq.TLabel",  {"background": Theme.BG,
                              "foreground": Theme.GREEN,
                              "font": ("Segoe UI", 16, "bold")}),
            ("Warn.TLabel",  {"background": Theme.BG,
                              "foreground": Theme.RED,
                              "font": ("Segoe UI", 9)}),
            ("Small.TLabel", {"background": Theme.BG,
                              "foreground": Theme.FG_DIM,
                              "font": ("Segoe UI", 8)}),
            ("TButton",      {"font": ("Segoe UI", 9)}),
            ("TRadiobutton", {"background": Theme.BG,
                              "foreground": Theme.FG,
                              "font": ("Segoe UI", 10)}),
            ("TCombobox",    {"font": ("Segoe UI", 10)}),
            ("TCheckbutton", {"background": Theme.BG,
                              "foreground": Theme.FG,
                              "font": ("Segoe UI", 10)}),
        ]:
            s.configure(name, **kw)
        s.map("TCombobox", fieldbackground=[("readonly", Theme.BG2)])

    # ── Layout ────────────────────────────────────────────────────────
    def _build_ui(self):
        outer = ttk.Frame(self.root)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(0, weight=1)

        left_box = ttk.Frame(outer, width=360)
        left_box.grid(row=0, column=0, sticky="ns", padx=(0, 6))
        left_box.grid_propagate(False)

        self._scv = tk.Canvas(left_box, bg=Theme.BG, highlightthickness=0,
                              width=340)
        sb = ttk.Scrollbar(left_box, orient="vertical",
                           command=self._scv.yview)
        self.ctrl = ttk.Frame(self._scv)
        self.ctrl.bind("<Configure>",
                       lambda e: self._scv.configure(
                           scrollregion=self._scv.bbox("all")))
        self._scv.create_window((0, 0), window=self.ctrl, anchor="nw")
        self._scv.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._scv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._scv.bind_all("<Button-4>",
                           lambda e: self._scv.yview_scroll(-2, "units"))
        self._scv.bind_all("<Button-5>",
                           lambda e: self._scv.yview_scroll(2, "units"))

        right = ttk.Frame(outer)
        right.grid(row=0, column=1, sticky="nsew")

        self._build_controls()
        self._build_plots(right)

    # ── Helpers ───────────────────────────────────────────────────────
    def _sep(self):
        ttk.Separator(self.ctrl, orient="horizontal").pack(
            fill=tk.X, padx=5, pady=(14, 4))

    def _header(self, txt):
        ttk.Label(self.ctrl, text=txt, style="H.TLabel").pack(
            anchor=tk.W, padx=10, pady=(2, 2))

    def _mk_scale(self, lo, hi, res, var, cmd):
        f = ttk.Frame(self.ctrl)
        f.pack(fill=tk.X, padx=10)
        sc = tk.Scale(f, from_=lo, to=hi, resolution=res,
                      orient=tk.HORIZONTAL, variable=var,
                      command=lambda _: cmd(),
                      bg=Theme.BG, fg=Theme.FG, troughcolor=Theme.BG2,
                      highlightthickness=0, length=260,
                      sliderrelief="flat", activebackground=Theme.ACCENT)
        sc.pack(fill=tk.X)
        return sc

    # ── Controls panel ────────────────────────────────────────────────
    def _build_controls(self):
        ttk.Label(self.ctrl, text="🔊  Simulador Chladni",
                  font=("Segoe UI", 16, "bold"),
                  foreground=Theme.ACCENT, background=Theme.BG
                  ).pack(anchor=tk.W, padx=10, pady=(10, 0))
        ttk.Label(self.ctrl,
                  text="Vibração de placas — padrões de areia",
                  style="Small.TLabel").pack(anchor=tk.W, padx=10)

        # ── Material ──
        self._sep()
        self._header("⚙  Material do Prato")
        self.material_var = tk.StringVar(value="Alumínio")
        cb = ttk.Combobox(self.ctrl, textvariable=self.material_var,
                          values=list(MATERIALS.keys()), state="readonly",
                          width=22)
        cb.pack(fill=tk.X, padx=10, pady=2)
        cb.bind("<<ComboboxSelected>>", lambda e: self.full_update())
        self.mat_info = ttk.Label(self.ctrl, style="Small.TLabel")
        self.mat_info.pack(anchor=tk.W, padx=10)

        # ── Geometry ──
        self._sep()
        self._header("📐  Geometria da Placa")
        self.geom_var = tk.StringVar(value="Quadrada")
        gf = ttk.Frame(self.ctrl)
        gf.pack(fill=tk.X, padx=10, pady=2)
        for g in GEOMETRIES:
            ttk.Radiobutton(gf, text=g, variable=self.geom_var,
                            value=g, command=self._on_geometry_change
                            ).pack(side=tk.LEFT, padx=4)

        self.Lx_var = tk.DoubleVar(value=0.30)
        ttk.Label(self.ctrl, text="Lado / Diâmetro Lx (m):"
                  ).pack(anchor=tk.W, padx=10, pady=(4, 0))
        self._mk_scale(0.05, 1.0, 0.01, self.Lx_var, self.full_update)
        self.Lx_lbl = ttk.Label(self.ctrl, style="Val.TLabel")
        self.Lx_lbl.pack(anchor=tk.W, padx=10)

        self.Ly_var = tk.DoubleVar(value=0.30)
        self.Ly_label_widget = ttk.Label(self.ctrl, text="Lado Ly (m):")
        self.Ly_label_widget.pack(anchor=tk.W, padx=10, pady=(4, 0))
        self.Ly_scale_frame = ttk.Frame(self.ctrl)
        self.Ly_scale_frame.pack(fill=tk.X, padx=10)
        self.Ly_scale = tk.Scale(
            self.Ly_scale_frame, from_=0.05, to=1.0, resolution=0.01,
            orient=tk.HORIZONTAL, variable=self.Ly_var,
            command=lambda _: self.full_update(),
            bg=Theme.BG, fg=Theme.FG, troughcolor=Theme.BG2,
            highlightthickness=0, length=260,
            sliderrelief="flat", activebackground=Theme.ACCENT)
        self.Ly_scale.pack(fill=tk.X)
        self.Ly_lbl = ttk.Label(self.ctrl, style="Val.TLabel")
        self.Ly_lbl.pack(anchor=tk.W, padx=10)

        self.h_var = tk.DoubleVar(value=0.002)
        ttk.Label(self.ctrl, text="Grossura h (m):"
                  ).pack(anchor=tk.W, padx=10, pady=(6, 0))
        self._mk_scale(0.0005, 0.02, 0.0005, self.h_var, self.full_update)
        self.h_lbl = ttk.Label(self.ctrl, style="Val.TLabel")
        self.h_lbl.pack(anchor=tk.W, padx=10)

        # Initial Ly visibility
        self._update_ly_visibility()

        # ── Visualization mode ──
        self._sep()
        self._header("🎵  Modo de Visualização")
        self.view_var = tk.StringVar(value="driven")
        vf = ttk.Frame(self.ctrl)
        vf.pack(fill=tk.X, padx=10)
        ttk.Radiobutton(vf, text="Resposta forçada (transdutores)",
                        variable=self.view_var, value="driven",
                        command=self.full_update).pack(anchor=tk.W)
        ttk.Radiobutton(vf, text="Modo individual (n, m)",
                        variable=self.view_var, value="mode",
                        command=self.full_update).pack(anchor=tk.W)

        nf = ttk.Frame(self.ctrl)
        nf.pack(fill=tk.X, padx=10, pady=3)
        self.n_var = tk.IntVar(value=3)
        self.m_var = tk.IntVar(value=2)
        ttk.Label(nf, text="n:").pack(side=tk.LEFT)
        tk.Spinbox(nf, from_=0, to=15, textvariable=self.n_var, width=4,
                   command=self.full_update, bg=Theme.BG2, fg=Theme.FG,
                   buttonbackground=Theme.BG3).pack(side=tk.LEFT,
                                                     padx=(2, 12))
        ttk.Label(nf, text="m:").pack(side=tk.LEFT)
        tk.Spinbox(nf, from_=1, to=15, textvariable=self.m_var, width=4,
                   command=self.full_update, bg=Theme.BG2, fg=Theme.FG,
                   buttonbackground=Theme.BG3).pack(side=tk.LEFT, padx=2)

        self.sign_var = tk.IntVar(value=1)
        sf = ttk.Frame(self.ctrl)
        sf.pack(fill=tk.X, padx=10)
        ttk.Label(sf, text="Simetria:").pack(side=tk.LEFT)
        ttk.Radiobutton(sf, text=" + ", variable=self.sign_var, value=1,
                        command=self.full_update).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(sf, text=" − ", variable=self.sign_var, value=-1,
                        command=self.full_update).pack(side=tk.LEFT, padx=4)

        # ── Transducers ──
        self._sep()
        self._header("📍  Transdutores")
        ttk.Label(self.ctrl,
                  text="Clica no prato → adicionar\n"
                       "Arrasta → mover · Duplo-clique → inverter fase\n"
                       "🔴 fase 0°  🔵 fase 180°  🟢 outra fase",
                  style="Small.TLabel").pack(anchor=tk.W, padx=10)
        self.trans_lb = tk.Listbox(
            self.ctrl, height=5, bg=Theme.BG2, fg=Theme.FG,
            selectbackground=Theme.ACCENT, font=("Consolas", 9),
            highlightthickness=0, borderwidth=1, relief="flat")
        self.trans_lb.pack(fill=tk.X, padx=10, pady=3)

        bf = ttk.Frame(self.ctrl)
        bf.pack(fill=tk.X, padx=10, pady=2)
        ttk.Button(bf, text="＋ Adicionar",
                   command=self._add_trans).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="✕ Remover",
                   command=self._rem_trans).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="↕ Inv. Fase",
                   command=self._flip_trans).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="⌖ Centro",
                   command=self._center_trans).pack(side=tk.LEFT, padx=2)
        self._refresh_trans()

        # Manual position + phase
        ttk.Label(self.ctrl, text="Definir posição / fase (selecionado):",
                  style="Small.TLabel").pack(anchor=tk.W, padx=10,
                                             pady=(6, 0))
        pf = ttk.Frame(self.ctrl)
        pf.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(pf, text="x:", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.tx_entry = tk.Entry(pf, width=7, bg=Theme.BG2, fg=Theme.FG,
                                 insertbackground=Theme.FG,
                                 font=("Consolas", 9))
        self.tx_entry.pack(side=tk.LEFT, padx=(2, 5))
        ttk.Label(pf, text="y:", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.ty_entry = tk.Entry(pf, width=7, bg=Theme.BG2, fg=Theme.FG,
                                 insertbackground=Theme.FG,
                                 font=("Consolas", 9))
        self.ty_entry.pack(side=tk.LEFT, padx=(2, 5))

        pf2 = ttk.Frame(self.ctrl)
        pf2.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(pf2, text="Amp:", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.tamp_entry = tk.Entry(pf2, width=5, bg=Theme.BG2, fg=Theme.FG,
                                   insertbackground=Theme.FG,
                                   font=("Consolas", 9))
        self.tamp_entry.pack(side=tk.LEFT, padx=(2, 5))
        self.tamp_entry.insert(0, "1.0")

        ttk.Label(pf2, text="Fase(°):", font=("Segoe UI", 9)).pack(
            side=tk.LEFT)
        self.tphase_entry = tk.Entry(pf2, width=5, bg=Theme.BG2,
                                     fg=Theme.FG,
                                     insertbackground=Theme.FG,
                                     font=("Consolas", 9))
        self.tphase_entry.pack(side=tk.LEFT, padx=(2, 5))
        self.tphase_entry.insert(0, "0")

        ttk.Button(pf2, text="✓", width=2,
                   command=self._apply_pos).pack(side=tk.LEFT, padx=4)
        self.trans_lb.bind("<<ListboxSelect>>", self._on_trans_select)

        # Per-transducer phase slider
        ttk.Label(self.ctrl, text="Fase do transdutor selecionado (°):",
                  style="Small.TLabel").pack(anchor=tk.W, padx=10,
                                             pady=(6, 0))
        self.phase_slider_var = tk.DoubleVar(value=0)
        phase_sf = ttk.Frame(self.ctrl)
        phase_sf.pack(fill=tk.X, padx=10)
        self.phase_slider = tk.Scale(
            phase_sf, from_=0, to=360, resolution=1,
            orient=tk.HORIZONTAL, variable=self.phase_slider_var,
            command=self._on_phase_slider,
            bg=Theme.BG, fg=Theme.FG, troughcolor=Theme.BG2,
            highlightthickness=0, length=260,
            sliderrelief="flat", activebackground=Theme.ACCENT)
        self.phase_slider.pack(fill=tk.X)

        # Transducer presets
        ttk.Label(self.ctrl, text="Presets de transdutores:",
                  style="Small.TLabel").pack(anchor=tk.W, padx=10,
                                             pady=(6, 0))
        preset_f = ttk.Frame(self.ctrl)
        preset_f.pack(fill=tk.X, padx=10, pady=2)
        for label, cmd in [
            ("1 Centro", self._preset_1_center),
            ("4 Cantos", self._preset_4_corners),
            ("4 Meios", self._preset_4_edges),
            ("8 Ring", self._preset_8_ring),
        ]:
            ttk.Button(preset_f, text=label,
                       command=cmd).pack(side=tk.LEFT, padx=2)

        # Grid toggle
        self.grid_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.ctrl, text="Mostrar grelha no prato",
                        variable=self.grid_var,
                        command=self.full_update).pack(
                            anchor=tk.W, padx=10, pady=(4, 0))

        # ── Particle visualization ──
        self._sep()
        self._header("🔵  Partículas")
        self.particle_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.ctrl, text="Mostrar partículas",
                        variable=self.particle_var,
                        command=self._toggle_particles).pack(
                            anchor=tk.W, padx=10, pady=(2, 0))

        self.particles_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.ctrl, text="Só partículas (sem onda)",
                        variable=self.particles_only_var,
                        command=self.full_update).pack(
                            anchor=tk.W, padx=10, pady=(2, 0))

        pnf = ttk.Frame(self.ctrl)
        pnf.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(pnf, text="Nº partículas:").pack(side=tk.LEFT)
        self.npart_var = tk.IntVar(value=2000)
        tk.Spinbox(pnf, from_=100, to=10000, increment=100,
                   textvariable=self.npart_var, width=6,
                   bg=Theme.BG2, fg=Theme.FG,
                   buttonbackground=Theme.BG3).pack(side=tk.LEFT, padx=4)
        ttk.Button(pnf, text="Reiniciar",
                   command=self._reset_particles).pack(side=tk.LEFT, padx=4)

        # ── Frequency ──
        self._sep()
        self._header("🔊  Frequência de Excitação")
        self.freq_var = tk.DoubleVar(value=500.0)
        self.freq_sc = self._mk_scale(20, 10000, 1, self.freq_var,
                                      self._debounced_pattern)
        self.freq_lbl = ttk.Label(self.ctrl, style="Freq.TLabel")
        self.freq_lbl.pack(anchor=tk.W, padx=10)

        rf = ttk.Frame(self.ctrl)
        rf.pack(fill=tk.X, padx=10, pady=2)
        ttk.Button(rf, text="◀ Ressonância",
                   command=lambda: self._snap(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(rf, text="Próxima ▶",
                   command=lambda: self._snap(1)).pack(side=tk.LEFT, padx=2)

        self.fmax_var = tk.DoubleVar(value=5000)
        ttk.Label(self.ctrl, text="Freq. máx. espectro (Hz):"
                  ).pack(anchor=tk.W, padx=10, pady=(6, 0))
        self._mk_scale(500, 20000, 100, self.fmax_var,
                       self._update_spectrum_only)

        # ── Sweep ──
        self._sep()
        self._header("📊  Varrimento de Frequência")
        sw_f = ttk.Frame(self.ctrl)
        sw_f.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(sw_f, text="De:", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.sweep_start_var = tk.DoubleVar(value=100)
        tk.Entry(sw_f, textvariable=self.sweep_start_var, width=6,
                 bg=Theme.BG2, fg=Theme.FG, insertbackground=Theme.FG,
                 font=("Consolas", 9)).pack(side=tk.LEFT, padx=2)
        ttk.Label(sw_f, text="Até:", font=("Segoe UI", 9)).pack(
            side=tk.LEFT)
        self.sweep_end_var = tk.DoubleVar(value=5000)
        tk.Entry(sw_f, textvariable=self.sweep_end_var, width=6,
                 bg=Theme.BG2, fg=Theme.FG, insertbackground=Theme.FG,
                 font=("Consolas", 9)).pack(side=tk.LEFT, padx=2)
        ttk.Label(sw_f, text="Passo:", font=("Segoe UI", 9)).pack(
            side=tk.LEFT)
        self.sweep_step_var = tk.DoubleVar(value=50)
        tk.Entry(sw_f, textvariable=self.sweep_step_var, width=5,
                 bg=Theme.BG2, fg=Theme.FG, insertbackground=Theme.FG,
                 font=("Consolas", 9)).pack(side=tk.LEFT, padx=2)

        ttk.Button(self.ctrl, text="▶ Iniciar Varrimento",
                   command=self._launch_sweep).pack(
                       anchor=tk.W, padx=10, pady=4)

        # ── Advanced ──
        self._sep()
        self._header("🔧  Parâmetros Avançados")
        self.damp_var = tk.DoubleVar(value=0.005)
        ttk.Label(self.ctrl, text="Amortecimento ζ:"
                  ).pack(anchor=tk.W, padx=10, pady=(4, 0))
        self._mk_scale(0.001, 0.10, 0.001, self.damp_var, self.full_update)
        self.damp_lbl = ttk.Label(self.ctrl, style="Val.TLabel")
        self.damp_lbl.pack(anchor=tk.W, padx=10)

        self.nmodes_var = tk.IntVar(value=8)
        ttk.Label(self.ctrl, text="Nº de modos (precisão):"
                  ).pack(anchor=tk.W, padx=10, pady=(6, 0))
        self._mk_scale(3, 15, 1, self.nmodes_var, self.full_update)

        # ── Info ──
        self._sep()
        self._header("ℹ  Informações")
        self.info_text = tk.Text(
            self.ctrl, height=10, bg=Theme.BG2, fg=Theme.FG,
            font=("Consolas", 8), wrap=tk.WORD,
            highlightthickness=0, borderwidth=0, relief="flat")
        self.info_text.pack(fill=tk.X, padx=10, pady=4)
        self.info_text.config(state=tk.DISABLED)
        self.warn_lbl = ttk.Label(self.ctrl, style="Warn.TLabel",
                                  wraplength=280)
        self.warn_lbl.pack(anchor=tk.W, padx=10, pady=(0, 14))

    # ── Geometry change ───────────────────────────────────────────────
    def _on_geometry_change(self):
        self._update_ly_visibility()
        # Reset transducers to safe default
        self.transducers = [(0.0, 0.0, 1.0, 0.0)]
        self._refresh_trans()
        self.full_update()

    def _update_ly_visibility(self):
        geom = self.geom_var.get()
        if geom == "Rectangular":
            self.Ly_label_widget.pack(anchor=tk.W, padx=10, pady=(4, 0))
            self.Ly_scale_frame.pack(fill=tk.X, padx=10)
            self.Ly_lbl.pack(anchor=tk.W, padx=10)
        else:
            self.Ly_label_widget.pack_forget()
            self.Ly_scale_frame.pack_forget()
            self.Ly_lbl.pack_forget()

    def _get_dims(self):
        """Return (Lx, Ly) based on geometry."""
        Lx = self.Lx_var.get()
        geom = self.geom_var.get()
        if geom == "Rectangular":
            Ly = self.Ly_var.get()
        else:
            Ly = Lx
        return Lx, Ly

    # ── Plots ─────────────────────────────────────────────────────────
    def _build_plots(self, parent):
        self.fig = Figure(figsize=(10, 8), facecolor=Theme.PL_BG, dpi=100)
        self.ax_pat = self.fig.add_axes([0.04, 0.34, 0.50, 0.62])
        self.ax_3d = self.fig.add_axes([0.56, 0.34, 0.42, 0.62],
                                       projection="3d")
        self.ax_spec = self.fig.add_axes([0.07, 0.07, 0.88, 0.22])
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.canvas.mpl_connect("button_press_event",   self._on_press)
        self.canvas.mpl_connect("motion_notify_event",  self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)

    # ══════════════════════════════════════════════════════════════════
    #  TRANSDUCER MANAGEMENT
    # ══════════════════════════════════════════════════════════════════

    def _refresh_trans(self):
        prev_idx = self._selected_trans_idx
        self.trans_lb.delete(0, tk.END)
        for i, (x, y, amp, phase) in enumerate(self.transducers):
            deg = np.degrees(phase)
            self.trans_lb.insert(
                tk.END,
                f"  T{i+1}: ({x:+.3f}, {y:+.3f})m  "
                f"A={amp:.2f} φ={deg:.0f}°")
        # Restore selection
        if prev_idx < len(self.transducers):
            self.trans_lb.selection_set(prev_idx)
            self.trans_lb.see(prev_idx)

    def _add_trans(self):
        Lx, Ly = self._get_dims()
        tx = round(np.random.uniform(-Lx / 3, Lx / 3), 4)
        ty = round(np.random.uniform(-Ly / 3, Ly / 3), 4)
        self.transducers.append((tx, ty, 1.0, 0.0))
        self._refresh_trans()
        self.full_update()

    def _rem_trans(self):
        sel = self.trans_lb.curselection()
        if sel:
            self.transducers.pop(sel[0])
        if not self.transducers:
            self.transducers = [(0.0, 0.0, 1.0, 0.0)]
        self._refresh_trans()
        self.full_update()

    def _flip_trans(self):
        sel = self.trans_lb.curselection()
        idx = sel[0] if sel else self._selected_trans_idx
        if idx < len(self.transducers):
            x, y, amp, phase = self.transducers[idx]
            # Shift phase by π (180°)
            self.transducers[idx] = (x, y, amp, (phase + np.pi) % (2 * np.pi))
        self._refresh_trans()
        self.full_update()

    def _center_trans(self):
        sel = self.trans_lb.curselection()
        idx = sel[0] if sel else self._selected_trans_idx
        if idx < len(self.transducers):
            _, _, amp, phase = self.transducers[idx]
            self.transducers[idx] = (0.0, 0.0, amp, phase)
        self._refresh_trans()
        self.full_update()

    def _on_trans_select(self, evt):
        sel = self.trans_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        self._selected_trans_idx = idx
        if idx < len(self.transducers):
            x, y, amp, phase = self.transducers[idx]
            self.tx_entry.delete(0, tk.END)
            self.tx_entry.insert(0, f"{x:.4f}")
            self.ty_entry.delete(0, tk.END)
            self.ty_entry.insert(0, f"{y:.4f}")
            self.tamp_entry.delete(0, tk.END)
            self.tamp_entry.insert(0, f"{amp:.2f}")
            self.tphase_entry.delete(0, tk.END)
            self.tphase_entry.insert(0, f"{np.degrees(phase):.0f}")
            self.phase_slider_var.set(np.degrees(phase) % 360)

    def _on_phase_slider(self, val):
        """Update the selected transducer's phase from the slider."""
        sel = self.trans_lb.curselection()
        idx = sel[0] if sel else self._selected_trans_idx
        if idx >= len(self.transducers):
            return
        x, y, amp, _ = self.transducers[idx]
        phase_rad = np.radians(float(val)) % (2 * np.pi)
        self.transducers[idx] = (x, y, amp, phase_rad)
        self.tphase_entry.delete(0, tk.END)
        self.tphase_entry.insert(0, f"{float(val):.0f}")
        self._refresh_trans()
        self._debounced_pattern()

    def _apply_pos(self):
        sel = self.trans_lb.curselection()
        idx = sel[0] if sel else self._selected_trans_idx
        if idx >= len(self.transducers):
            return
        try:
            x = float(self.tx_entry.get())
            y = float(self.ty_entry.get())
            amp = float(self.tamp_entry.get())
            phase_deg = float(self.tphase_entry.get())
        except ValueError:
            self.warn_lbl.config(
                text="⚠ Valor inválido. Usa números (ex: 0.05)")
            return
        Lx, Ly = self._get_dims()
        geom = self.geom_var.get()
        if geom == "Circular":
            R = Lx / 2.0
            r = np.sqrt(x**2 + y**2)
            if r > R:
                scale = R / r * 0.98
                x *= scale
                y *= scale
        else:
            x = max(-Lx / 2, min(Lx / 2, x))
            y = max(-Ly / 2, min(Ly / 2, y))
        amp = max(0.0, amp)
        phase_rad = np.radians(phase_deg) % (2 * np.pi)
        self.transducers[idx] = (round(x, 4), round(y, 4), amp, phase_rad)
        self.phase_slider_var.set(phase_deg % 360)
        self._refresh_trans()
        self.full_update()

    # ── Transducer presets ────────────────────────────────────────────
    def _preset_1_center(self):
        self.transducers = [(0.0, 0.0, 1.0, 0.0)]
        self._refresh_trans()
        self.full_update()

    def _preset_4_corners(self):
        Lx, Ly = self._get_dims()
        d = 0.35
        self.transducers = [
            (-Lx * d, -Ly * d, 1.0, 0.0),
            ( Lx * d, -Ly * d, 1.0, np.pi),
            (-Lx * d,  Ly * d, 1.0, np.pi),
            ( Lx * d,  Ly * d, 1.0, 0.0),
        ]
        self._refresh_trans()
        self.full_update()

    def _preset_4_edges(self):
        Lx, Ly = self._get_dims()
        d = 0.3
        self.transducers = [
            ( 0.0,    -Ly * d, 1.0, 0.0),
            ( 0.0,     Ly * d, 1.0, 0.0),
            (-Lx * d,  0.0,    1.0, np.pi),
            ( Lx * d,  0.0,    1.0, np.pi),
        ]
        self._refresh_trans()
        self.full_update()

    def _preset_8_ring(self):
        Lx, _ = self._get_dims()
        r = Lx * 0.3
        self.transducers = []
        for i in range(8):
            angle = i * np.pi / 4
            phase = 0.0 if i % 2 == 0 else np.pi
            self.transducers.append((
                round(r * np.cos(angle), 4),
                round(r * np.sin(angle), 4),
                1.0, phase))
        self._refresh_trans()
        self.full_update()

    # ── Plate interaction (click / drag / double-click) ───────────────
    def _on_press(self, evt):
        if evt.inaxes is not self.ax_pat or evt.button != 1:
            return
        Lx, Ly = self._get_dims()
        geom = self.geom_var.get()
        x, y = evt.xdata, evt.ydata
        if x is None or y is None:
            return

        # Check bounds
        if geom == "Circular":
            R = Lx / 2.0
            if x**2 + y**2 > R**2:
                return
        else:
            if abs(x) > Lx / 2 or abs(y) > Ly / 2:
                return

        # Double-click → flip phase
        if evt.dblclick:
            best_i, best_d = None, 1e18
            for i, (tx, ty, _, _) in enumerate(self.transducers):
                d = (x - tx)**2 + (y - ty)**2
                if d < best_d:
                    best_i, best_d = i, d
            if best_i is not None and best_d < (Lx * 0.06)**2:
                tx, ty, amp, phase = self.transducers[best_i]
                self.transducers[best_i] = (tx, ty, amp,
                                            (phase + np.pi) % (2 * np.pi))
                self._refresh_trans()
                self.full_update()
            return

        # Near existing → drag
        for i, (tx, ty, _, _) in enumerate(self.transducers):
            if (x - tx)**2 + (y - ty)**2 < (Lx * 0.04)**2:
                self._drag_idx = i
                self._dragging = True
                return

        # New transducer
        self.transducers.append((round(x, 4), round(y, 4), 1.0, 0.0))
        self._refresh_trans()
        self.full_update()

    def _on_motion(self, evt):
        if self._drag_idx is None or evt.inaxes is not self.ax_pat:
            return
        if evt.xdata is None or evt.ydata is None:
            return
        Lx, Ly = self._get_dims()
        geom = self.geom_var.get()
        x, y = float(evt.xdata), float(evt.ydata)

        if geom == "Circular":
            R = Lx / 2.0
            r = np.sqrt(x**2 + y**2)
            if r > R:
                x *= R / r * 0.98
                y *= R / r * 0.98
        else:
            x = float(np.clip(x, -Lx / 2, Lx / 2))
            y = float(np.clip(y, -Ly / 2, Ly / 2))

        _, _, amp, phase = self.transducers[self._drag_idx]
        self.transducers[self._drag_idx] = (round(x, 4), round(y, 4),
                                            amp, phase)
        self._refresh_trans()
        self._debounced_pattern()

    def _on_release(self, evt):
        if self._drag_idx is not None:
            self._drag_idx = None
            self._dragging = False
            self.full_update()

    # ── Particle system ───────────────────────────────────────────────
    def _toggle_particles(self):
        if self.particle_var.get():
            self._reset_particles()
            self._start_particle_anim()
        else:
            self._stop_particle_anim()
            self.full_update()

    def _reset_particles(self):
        Lx, Ly = self._get_dims()
        geom = self.geom_var.get()
        n = self.npart_var.get()
        self.physics.init_particles(n, Lx, Ly, geometry=geom)
        if self.particle_var.get():
            self.full_update()

    def _start_particle_anim(self):
        self._stop_particle_anim()
        self._animate_particles()

    def _stop_particle_anim(self):
        if self._particle_anim_id is not None:
            self.root.after_cancel(self._particle_anim_id)
            self._particle_anim_id = None

    def _animate_particles(self):
        if not self.particle_var.get():
            return
        Lx, Ly = self._get_dims()
        h = self.h_var.get()
        mat = MATERIALS[self.material_var.get()]
        D = self.physics.flexural_rigidity(mat["E"], h, mat["nu"])
        freq = self.freq_var.get()
        zeta = self.damp_var.get()
        sign = self.sign_var.get()
        nm = self.nmodes_var.get()
        geom = self.geom_var.get()

        resp = self.physics.driven_response_cartesian(
            freq, Lx, Ly, D, mat["rho"], h, self.transducers,
            n_modes=nm, damping=zeta, sign=sign, geometry=geom)

        # Step particles multiple sub-steps for stability
        for _ in range(5):
            self.physics.step_particles(resp, Lx, Ly, dt=0.003,
                                        friction=0.82, force_scale=0.8,
                                        geometry=geom)

        self._update_pattern(skip_3d=True)
        self.canvas.draw_idle()
        self._particle_anim_id = self.root.after(60,
                                                  self._animate_particles)

    # ── Debounce ──────────────────────────────────────────────────────
    def _debounced_pattern(self):
        if self._update_id is not None:
            self.root.after_cancel(self._update_id)
        self._update_id = self.root.after(40, self._do_pattern_update)

    def _do_pattern_update(self):
        self._update_id = None
        self._sync_labels()
        self._update_pattern(skip_3d=self._dragging)
        self.canvas.draw_idle()

    # ── Snap to resonance ─────────────────────────────────────────────
    def _snap(self, direction):
        Lx, Ly = self._get_dims()
        h = self.h_var.get()
        mat = MATERIALS[self.material_var.get()]
        D = self.physics.flexural_rigidity(mat["E"], h, mat["nu"])
        sign, nm = self.sign_var.get(), self.nmodes_var.get()
        cur = self.freq_var.get()
        geom = self.geom_var.get()

        if geom == "Circular":
            R = Lx / 2.0
            self.physics._build_cache_circ(R, nm, D, mat["rho"], h)
            F_nm = self.physics._coupling_circ(self.transducers, R)
        else:
            self.physics._build_cache_rect(Lx, Ly, sign, nm,
                                           D, mat["rho"], h)
            F_nm = self.physics._coupling_rect(self.transducers, Lx, Ly,
                                               sign)

        res_set = set()
        for k in range(len(self.physics._f_nm)):
            fnm = self.physics._f_nm[k]
            if abs(F_nm[k]) > 0.05 and 10 < fnm < 20000:
                res_set.add(round(float(fnm), 1))

        ordered = sorted(res_set)
        if not ordered:
            return
        if direction > 0:
            cands = [f for f in ordered if f > cur + 5]
        else:
            cands = [f for f in ordered if f < cur - 5]
        if cands:
            target = cands[0] if direction > 0 else cands[-1]
            self.freq_var.set(target)
            self.freq_sc.set(target)
            self.full_update()

    # ── Sweep launcher ────────────────────────────────────────────────
    def _launch_sweep(self):
        Lx, Ly = self._get_dims()
        h = self.h_var.get()
        mat = MATERIALS[self.material_var.get()]
        D = self.physics.flexural_rigidity(mat["E"], h, mat["nu"])
        params = {
            "Lx": Lx,
            "Ly": Ly,
            "D": D,
            "rho": mat["rho"],
            "h": h,
            "transducers": list(self.transducers),
            "n_modes": self.nmodes_var.get(),
            "damping": self.damp_var.get(),
            "sign": self.sign_var.get(),
            "geometry": self.geom_var.get(),
            "freq_start": self.sweep_start_var.get(),
            "freq_end": self.sweep_end_var.get(),
            "freq_step": self.sweep_step_var.get(),
            "material_name": self.material_var.get(),
        }
        SweepWindow(self.root, self.physics, params)

    # ══════════════════════════════════════════════════════════════════
    #  UPDATES
    # ══════════════════════════════════════════════════════════════════

    def full_update(self, *_):
        self._sync_labels()
        self._update_spectrum()
        self._update_pattern()
        self.canvas.draw_idle()

    def _update_spectrum_only(self, *_):
        self._sync_labels()
        self._update_spectrum()
        self.canvas.draw_idle()

    def _sync_labels(self):
        Lx, Ly = self._get_dims()
        h = self.h_var.get()
        geom = self.geom_var.get()

        if geom == "Circular":
            self.Lx_lbl.config(
                text=f"∅ {Lx:.2f} m  ({Lx*100:.0f} cm)")
        elif geom == "Rectangular":
            self.Lx_lbl.config(text=f"{Lx:.2f} m  ({Lx*100:.0f} cm)")
            self.Ly_lbl.config(text=f"{Ly:.2f} m  ({Ly*100:.0f} cm)")
        else:
            self.Lx_lbl.config(text=f"{Lx:.2f} m  ({Lx*100:.0f} cm)")

        self.h_lbl.config(text=f"{h*1000:.1f} mm")
        self.freq_lbl.config(text=f"{self.freq_var.get():.0f} Hz")
        self.damp_lbl.config(text=f"ζ = {self.damp_var.get():.3f}")
        mat = MATERIALS[self.material_var.get()]
        self.mat_info.config(
            text=f"E={mat['E']/1e9:.0f} GPa · ρ={mat['rho']} kg/m³ · "
                 f"ν={mat['nu']:.2f}")

    # ── Spectrum ──────────────────────────────────────────────────────
    def _update_spectrum(self):
        Lx, Ly = self._get_dims()
        h = self.h_var.get()
        mat = MATERIALS[self.material_var.get()]
        D = self.physics.flexural_rigidity(mat["E"], h, mat["nu"])
        zeta = self.damp_var.get()
        sign = self.sign_var.get()
        nm = self.nmodes_var.get()
        fmax = self.fmax_var.get()
        geom = self.geom_var.get()

        freqs, energy = self.physics.frequency_sweep(
            Lx, Ly, D, mat["rho"], h, self.transducers,
            freq_range=(20, fmax), n_modes=nm, damping=zeta,
            sign=sign, n_points=400, geometry=geom)

        mx = energy.max()
        edb = 10.0 * np.log10(energy / mx + 1e-15) if mx > 0 else \
              np.full_like(energy, -80.0)

        ax = self.ax_spec
        ax.clear()
        ax.fill_between(freqs, edb, -80, alpha=0.25, color=Theme.ACCENT)
        ax.plot(freqs, edb, color=Theme.ACCENT, linewidth=0.9)
        ax.axvline(self.freq_var.get(), color=Theme.RED, lw=1.4,
                   ls="--", alpha=0.85)
        try:
            peaks, _ = find_peaks(edb, height=-20, distance=5, prominence=3)
            if len(peaks):
                ax.plot(freqs[peaks], edb[peaks], "v",
                        color=Theme.YELLOW, ms=5, zorder=5)
        except Exception:
            pass
        ax.set_xlim(20, fmax)
        ax.set_ylim(-65, 5)
        ax.set_xlabel("Frequência (Hz)", color=Theme.FG_DIM, fontsize=9)
        ax.set_ylabel("dB", color=Theme.FG_DIM, fontsize=9)
        ax.set_title("Espectro de Ressonância", color=Theme.FG, fontsize=10)
        ax.set_facecolor(Theme.PL_BG)
        ax.tick_params(colors=Theme.FG_DIM, labelsize=7)
        for sp in ax.spines.values():
            sp.set_color(Theme.BG3)
        ax.grid(True, alpha=0.12, color=Theme.FG_DIM)

    # ── Pattern 2D + 3D ──────────────────────────────────────────────
    def _update_pattern(self, skip_3d=False):
        Lx, Ly = self._get_dims()
        h = self.h_var.get()
        mat = MATERIALS[self.material_var.get()]
        D = self.physics.flexural_rigidity(mat["E"], h, mat["nu"])
        n, m = self.n_var.get(), self.m_var.get()
        sign = self.sign_var.get()
        zeta = self.damp_var.get()
        nm = self.nmodes_var.get()
        freq = self.freq_var.get()
        view = self.view_var.get()
        geom = self.geom_var.get()

        if view == "mode":
            Z = self.physics.mode_shape(n, m, Lx, Ly, sign, geometry=geom)
            sand = np.exp(-40.0 * Z**2)
            Z_3d = Z
            f_mode = self.physics.mode_frequency(n, m, Lx, Ly, D,
                                                  mat["rho"], h,
                                                  geometry=geom)
            title = f"Modo ({n},{m}) — f = {f_mode:.1f} Hz"
        else:
            sand, Z_3d = self.physics.sand_and_3d(
                freq, Lx, Ly, D, mat["rho"], h, self.transducers,
                n_modes=nm, damping=zeta, sign=sign, geometry=geom)
            title = f"Padrão a {freq:.0f} Hz"

        # 2D
        ax = self.ax_pat
        ax.clear()

        show_waves = not (self.particle_var.get() and
                          self.particles_only_var.get())

        if geom == "Circular":
            R = Lx / 2.0
            if show_waves:
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
            if show_waves:
                ax.imshow(sand, cmap=SAND_CMAP, origin="lower", extent=ext,
                          interpolation="bilinear", vmin=0, vmax=1,
                          aspect="equal")
            else:
                ax.set_xlim(-Lx / 2, Lx / 2)
                ax.set_ylim(-Ly / 2, Ly / 2)
            ax.plot([-Lx/2, Lx/2, Lx/2, -Lx/2, -Lx/2],
                    [-Ly/2, -Ly/2, Ly/2, Ly/2, -Ly/2],
                    color="#555", lw=1.5)

        # Grid
        if self.grid_var.get() and geom != "Circular":
            n_div = max(4, int(round(Lx / 0.05)))
            n_div = min(n_div, 20)
            ticks = np.linspace(-Lx / 2, Lx / 2, n_div + 1)
            for t in ticks:
                ax.axhline(t, color="#ffffff", alpha=0.12, lw=0.5, zorder=2)
                ax.axvline(t, color="#ffffff", alpha=0.12, lw=0.5, zorder=2)
            ax.axhline(0, color="#ffffff", alpha=0.3, lw=0.8, ls="--",
                       zorder=2)
            ax.axvline(0, color="#ffffff", alpha=0.3, lw=0.8, ls="--",
                       zorder=2)

        # Transducers
        for i, (tx, ty, amp, phase) in enumerate(self.transducers):
            deg = np.degrees(phase)
            if abs(deg) < 10 or abs(deg - 360) < 10:
                c, mk = "#ff4444", "^"
            elif abs(deg - 180) < 10:
                c, mk = "#4488ff", "v"
            else:
                c, mk = "#44ff88", "D"
            ax.plot(tx, ty, mk, color=c, ms=11,
                    markeredgecolor="white", markeredgewidth=1.4, zorder=5)
            ax.annotate(f"T{i+1}", (tx, ty), textcoords="offset points",
                        xytext=(8, 8), fontsize=7, color=c,
                        fontweight="bold")

        # Particles
        if self.particle_var.get() and self.physics.particles is not None:
            pts = self.physics.particles
            ax.scatter(pts[:, 0], pts[:, 1], s=0.5, c="#f5ecd0",
                       alpha=0.8, zorder=4, linewidths=0)

        ax.set_title(title, color=Theme.FG, fontsize=12, fontweight="bold")
        ax.set_xlabel("x (m)", color=Theme.FG_DIM, fontsize=9)
        ax.set_ylabel("y (m)", color=Theme.FG_DIM, fontsize=9)
        ax.tick_params(colors=Theme.FG_DIM, labelsize=7)
        ax.set_facecolor(Theme.PL_BG)
        for sp in ax.spines.values():
            sp.set_color(Theme.BG3)
        ax.set_aspect("equal")

        # 3D
        if not skip_3d:
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
            ax3.set_title("Deformação da Placa", color=Theme.FG,
                          fontsize=10, pad=0)
            ax3.set_facecolor(Theme.PL_BG)
            ax3.tick_params(colors=Theme.FG_DIM, labelsize=5)
            ax3.set_xlabel("x", fontsize=6, color=Theme.FG_DIM, labelpad=-2)
            ax3.set_ylabel("y", fontsize=6, color=Theme.FG_DIM, labelpad=-2)
            ax3.set_zlabel("w", fontsize=6, color=Theme.FG_DIM, labelpad=-2)
            try:
                for a in (ax3.xaxis, ax3.yaxis, ax3.zaxis):
                    a.pane.fill = False
                    a.pane.set_edgecolor(Theme.BG3)
            except Exception:
                pass

        # Info panel
        self._write_info(
            freq if view == "driven" else
            self.physics.mode_frequency(n, m, Lx, Ly, D, mat["rho"], h,
                                        geometry=geom),
            n, m, Lx, Ly, h, mat, D, view, geom)

    # ── Info panel ────────────────────────────────────────────────────
    def _write_info(self, freq, n, m, Lx, Ly, h, mat, D, view, geom):
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete("1.0", tk.END)
        name = self.material_var.get()

        if geom == "Circular":
            dim_str = f"∅ {Lx*100:.1f} cm, h={h*1000:.1f} mm"
        elif geom == "Rectangular":
            dim_str = (f"{Lx*100:.1f}×{Ly*100:.1f} cm, "
                       f"h={h*1000:.1f} mm")
        else:
            dim_str = (f"{Lx*100:.1f}×{Lx*100:.1f} cm, "
                       f"h={h*1000:.1f} mm")

        n_up = sum(1 for _, _, _, ph in self.transducers
                   if abs(ph) < 0.1 or abs(ph - 2*np.pi) < 0.1)
        n_dn = sum(1 for _, _, _, ph in self.transducers
                   if abs(ph - np.pi) < 0.1)
        n_other = len(self.transducers) - n_up - n_dn

        lines = [
            f"Material: {name}",
            f"E={mat['E']/1e9:.1f} GPa  ρ={mat['rho']} kg/m³  "
            f"ν={mat['nu']:.2f}",
            f"D = {D:.6f} N·m",
            f"Geometria: {geom} — {dim_str}",
            f"Transdutores: {len(self.transducers)}"
            f"  ({n_up}↑ {n_dn}↓ {n_other}◇)",
        ]

        if view == "mode":
            fm = self.physics.mode_frequency(n, m, Lx, Ly, D,
                                              mat["rho"], h,
                                              geometry=geom)
            lines.append(f"Modo ({n},{m}) → f = {fm:.1f} Hz")
        else:
            lines.append(f"Freq. excitação: {freq:.1f} Hz")
            nm_max = self.nmodes_var.get()
            best, best_f = None, 1e18
            for ni in range(1, nm_max + 1):
                for mi in range(1, nm_max + 1):
                    fi = self.physics.mode_frequency(
                        ni, mi, Lx, Ly, D, mat["rho"], h,
                        geometry=geom)
                    if abs(fi - freq) < abs(best_f - freq):
                        best, best_f = (ni, mi), fi
            if best:
                lines.append(f"Modo +próximo: ({best[0]},{best[1]}) "
                             f"a {best_f:.1f} Hz")

        if self.particle_var.get() and self.physics.particles is not None:
            lines.append(f"Partículas: {len(self.physics.particles)}")

        self.info_text.insert("1.0", "\n".join(lines))
        self.info_text.config(state=tk.DISABLED)

        # Warning for weak excitation
        if view == "driven" and geom != "Circular":
            sign = self.sign_var.get()
            coup = sum(
                abs(self.physics.transducer_coupling_single(
                    tx, ty, n, m, Lx, Ly, sign))
                for tx, ty, _, _ in self.transducers)
            if coup < 0.05:
                self.warn_lbl.config(
                    text="⚠ Transdutores perto de nós — "
                         "excitação fraca!")
            else:
                self.warn_lbl.config(text="")
        else:
            self.warn_lbl.config(text="")
