"""
Simulador de Figuras de Chladni  (v2 — optimizado)
====================================================
Modelo físico de Kirchhoff para placas finas com superposição modal,
totalmente vectorizado com NumPy para desempenho em tempo real.

Cada transdutor tem uma **fase** (+1 para cima, −1 para baixo),
modelando excitação bipolar realista.
"""

import numpy as np
from scipy.signal import find_peaks
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap
import tkinter as tk
from tkinter import ttk

# ── Materiais ─────────────────────────────────────────────────────────────
MATERIALS = {
    "Alumínio": {"E": 69e9,  "rho": 2700, "nu": 0.33},
    "Aço":      {"E": 200e9, "rho": 7800, "nu": 0.30},
    "Latão":    {"E": 100e9, "rho": 8500, "nu": 0.34},
    "Vidro":    {"E": 70e9,  "rho": 2500, "nu": 0.24},
    "Cobre":    {"E": 117e9, "rho": 8960, "nu": 0.34},
    "Titânio":  {"E": 116e9, "rho": 4507, "nu": 0.32},
}

# ── Colormap areia ────────────────────────────────────────────────────────
SAND_CMAP = LinearSegmentedColormap.from_list("sand", [
    "#080808", "#12100a", "#2a2010", "#503c1a",
    "#806830", "#b09050", "#d4b870", "#e8d8a8",
    "#f5ecd0", "#fffbf0",
], N=256)


# ═══════════════════════════════════════════════════════════════════════════
#  Motor de física — totalmente vectorizado
# ═══════════════════════════════════════════════════════════════════════════
class ChladniPhysics:
    def __init__(self, resolution: int = 200):
        self.res = resolution
        t = np.linspace(-0.5, 0.5, self.res)
        self.X_norm, self.Y_norm = np.meshgrid(t, t)  # em [-0.5, 0.5]

        # cache
        self._cache_key = None          # (L, sign, n_modes)
        self._modes = None              # (N*N, res, res)
        self._omega_nm = None           # (N*N,)
        self._ns = None; self._ms = None

    @staticmethod
    def flexural_rigidity(E, h, nu):
        return (E * h**3) / (12.0 * (1.0 - nu**2))

    # ── Pre-computa todas as formas modais ────────────────────────────
    def _build_cache(self, L, sign, n_modes, D, rho, h):
        key = (L, sign, n_modes, D, rho, h)
        if self._cache_key == key:
            return
        self._cache_key = key

        ns = np.arange(1, n_modes + 1)
        ms = np.arange(1, n_modes + 1)
        NN, MM = np.meshgrid(ns, ms)           # (N, N)
        self._ns = NN.ravel()                   # (N²,)
        self._ms = MM.ravel()

        # frequências naturais  ω_nm
        f_nm = (np.pi / (2.0 * L**2)) * np.sqrt(D / (rho * h)) * \
               (self._ns**2 + self._ms**2)
        self._omega_nm = 2.0 * np.pi * f_nm    # (N²,)
        self._f_nm = f_nm

        # formas modais: φ_nm(x,y) = cos(n π x/L) cos(m π y/L) ± …
        X = self.X_norm * L                     # (res, res)
        Y = self.Y_norm * L
        # → (N², 1, 1) para broadcast
        n3 = self._ns[:, None, None]
        m3 = self._ms[:, None, None]
        piX = np.pi * X[None, :, :] / L        # (1, res, res)
        piY = np.pi * Y[None, :, :] / L

        t1 = np.cos(n3 * piX) * np.cos(m3 * piY)
        t2 = np.cos(m3 * piX) * np.cos(n3 * piY)
        self._modes = t1 + sign * t2            # (N², res, res)

    # ── Acoplamento dos transdutores (vectorizado) ────────────────────
    def _coupling(self, transducers, L, sign):
        """Retorna F_nm  shape (N²,).
        transducers: lista de (tx, ty, phase)."""
        F = np.zeros(len(self._ns))
        for tx, ty, phase in transducers:
            cn = np.cos(self._ns * np.pi * tx / L)
            cm = np.cos(self._ms * np.pi * ty / L)
            cn2 = np.cos(self._ms * np.pi * tx / L)
            cm2 = np.cos(self._ns * np.pi * ty / L)
            F += phase * (cn * cm + sign * cn2 * cm2)
        return F                                # (N²,)

    # ── Resposta forçada (uma frequência) ─────────────────────────────
    def driven_response(self, freq, L, D, rho, h, transducers,
                        n_modes=8, damping=0.005, sign=1):
        self._build_cache(L, sign, n_modes, D, rho, h)
        omega = 2.0 * np.pi * freq
        F_nm = self._coupling(transducers, L, sign)  # (N²,)
        denom = self._omega_nm**2 - omega**2 + \
                2j * damping * self._omega_nm * omega  # (N²,)
        # evitar divisão por zero
        safe = np.abs(denom) > 1e-30
        coeffs = np.zeros(len(F_nm), dtype=complex)
        coeffs[safe] = F_nm[safe] / denom[safe]
        # resp = Σ coeff_k · mode_k
        resp = np.einsum("k,kij->ij", coeffs, self._modes)
        return resp

    def sand_and_3d(self, freq, L, D, rho, h, transducers,
                    n_modes=8, damping=0.005, sign=1):
        """Retorna (sand, Z_3d_normalizado) numa única chamada."""
        resp = self.driven_response(freq, L, D, rho, h, transducers,
                                    n_modes, damping, sign)
        amp = np.abs(resp)
        mx = amp.max()
        if mx > 0:
            amp_n = amp / mx
        else:
            amp_n = amp
        sand = np.exp(-35.0 * amp_n**2)
        Z = np.real(resp)
        zmx = np.abs(Z).max()
        if zmx > 0:
            Z = Z / zmx
        return sand, Z

    def mode_shape(self, n, m, L, sign=1):
        X = self.X_norm * L; Y = self.Y_norm * L
        t1 = np.cos(n * np.pi * X / L) * np.cos(m * np.pi * Y / L)
        t2 = np.cos(m * np.pi * X / L) * np.cos(n * np.pi * Y / L)
        return t1 + sign * t2

    def mode_frequency(self, n, m, L, D, rho, h):
        return (np.pi / (2.0 * L**2)) * np.sqrt(D / (rho * h)) * (n**2 + m**2)

    # ── Varrimento de frequência (vectorizado) ────────────────────────
    def frequency_sweep(self, L, D, rho, h, transducers,
                        freq_range=(20, 5000), n_modes=8,
                        damping=0.005, sign=1, n_points=400):
        self._build_cache(L, sign, n_modes, D, rho, h)
        F_nm = self._coupling(transducers, L, sign)  # (K,)
        freqs = np.linspace(freq_range[0], freq_range[1], n_points)
        omega = 2.0 * np.pi * freqs                  # (P,)

        # denom(p, k) = ω_k² − ω_p² + 2jζω_k·ω_p
        # shapes: omega_nm (K,) → (1,K);  omega (P,) → (P,1)
        w_nm = self._omega_nm[None, :]                # (1, K)
        w = omega[:, None]                            # (P, 1)
        denom = w_nm**2 - w**2 + 2j * damping * w_nm * w  # (P, K)
        abs_d2 = np.abs(denom)**2
        abs_d2 = np.maximum(abs_d2, 1e-60)
        energy = np.sum(np.abs(F_nm[None, :])**2 / abs_d2, axis=1)
        return freqs, energy


# ═══════════════════════════════════════════════════════════════════════════
#  GUI
# ═══════════════════════════════════════════════════════════════════════════
class ChladniApp:
    BG     = "#1e1e2e";  BG2    = "#282840";  BG3    = "#353560"
    FG     = "#cdd6f4";  FG_DIM = "#9399b2";  ACCENT = "#89b4fa"
    RED    = "#f38ba8";  GREEN  = "#a6e3a1";  YELLOW = "#f9e2af"
    PL_BG  = "#111118"

    def __init__(self, root):
        self.root = root
        root.title("Simulador de Figuras de Chladni")
        root.geometry("1440x900")
        root.minsize(1100, 650)
        root.configure(bg=self.BG)

        self.physics = ChladniPhysics(resolution=200)
        # transdutores: [(x, y, phase), ...]   phase ∈ {+1, -1}
        self.transducers = [(0.0, 0.0, +1)]
        self._drag_idx = None
        self._update_id = None           # debounce
        self._dragging = False

        self._configure_styles()
        self._build_ui()
        root.after(100, self.full_update)

    # ── Estilos ───────────────────────────────────────────────────────
    def _configure_styles(self):
        s = ttk.Style(); s.theme_use("clam")
        for name, kw in [
            (".",            {"background": self.BG, "foreground": self.FG}),
            ("TFrame",       {"background": self.BG}),
            ("TLabel",       {"background": self.BG, "foreground": self.FG,
                              "font": ("Segoe UI", 10)}),
            ("H.TLabel",     {"background": self.BG, "foreground": self.ACCENT,
                              "font": ("Segoe UI", 11, "bold")}),
            ("Val.TLabel",   {"background": self.BG, "foreground": self.YELLOW,
                              "font": ("Segoe UI", 10, "bold")}),
            ("Freq.TLabel",  {"background": self.BG, "foreground": self.GREEN,
                              "font": ("Segoe UI", 16, "bold")}),
            ("Warn.TLabel",  {"background": self.BG, "foreground": self.RED,
                              "font": ("Segoe UI", 9)}),
            ("Small.TLabel", {"background": self.BG, "foreground": self.FG_DIM,
                              "font": ("Segoe UI", 8)}),
            ("TButton",      {"font": ("Segoe UI", 9)}),
            ("TRadiobutton", {"background": self.BG, "foreground": self.FG,
                              "font": ("Segoe UI", 10)}),
            ("TCombobox",    {"font": ("Segoe UI", 10)}),
        ]:
            s.configure(name, **kw)
        s.map("TCombobox", fieldbackground=[("readonly", self.BG2)])

    # ── Layout ────────────────────────────────────────────────────────
    def _build_ui(self):
        outer = ttk.Frame(self.root)
        outer.pack(fill=tk.BOTH, expand=True)

        left_box = ttk.Frame(outer, width=330)
        left_box.pack(side=tk.LEFT, fill=tk.Y)
        left_box.pack_propagate(False)

        self._scv = tk.Canvas(left_box, bg=self.BG, highlightthickness=0,
                              width=310)
        sb = ttk.Scrollbar(left_box, orient="vertical", command=self._scv.yview)
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
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._build_controls()
        self._build_plots(right)

    # helpers
    def _sep(self):
        ttk.Separator(self.ctrl, orient="horizontal").pack(
            fill=tk.X, padx=5, pady=(14, 4))

    def _header(self, txt):
        ttk.Label(self.ctrl, text=txt, style="H.TLabel").pack(
            anchor=tk.W, padx=10, pady=(2, 2))

    def _mk_scale(self, lo, hi, res, var, cmd):
        f = ttk.Frame(self.ctrl); f.pack(fill=tk.X, padx=10)
        sc = tk.Scale(f, from_=lo, to=hi, resolution=res,
                      orient=tk.HORIZONTAL, variable=var,
                      command=lambda _: cmd(),
                      bg=self.BG, fg=self.FG, troughcolor=self.BG2,
                      highlightthickness=0, length=260,
                      sliderrelief="flat", activebackground=self.ACCENT)
        sc.pack(fill=tk.X)
        return sc

    # ── Controlos ─────────────────────────────────────────────────────
    def _build_controls(self):
        ttk.Label(self.ctrl, text="🔊  Simulador Chladni",
                  font=("Segoe UI", 16, "bold"),
                  foreground=self.ACCENT, background=self.BG
                  ).pack(anchor=tk.W, padx=10, pady=(10, 0))
        ttk.Label(self.ctrl, text="Vibração de placas — padrões de areia",
                  style="Small.TLabel").pack(anchor=tk.W, padx=10)

        # Material
        self._sep(); self._header("⚙  Material do Prato")
        self.material_var = tk.StringVar(value="Alumínio")
        cb = ttk.Combobox(self.ctrl, textvariable=self.material_var,
                          values=list(MATERIALS.keys()), state="readonly",
                          width=22)
        cb.pack(fill=tk.X, padx=10, pady=2)
        cb.bind("<<ComboboxSelected>>", lambda e: self.full_update())
        self.mat_info = ttk.Label(self.ctrl, style="Small.TLabel")
        self.mat_info.pack(anchor=tk.W, padx=10)

        # Geometria
        self._sep(); self._header("📐  Geometria (placa quadrada)")
        self.L_var = tk.DoubleVar(value=0.30)
        ttk.Label(self.ctrl, text="Lado L (m):").pack(
            anchor=tk.W, padx=10, pady=(4, 0))
        self._mk_scale(0.05, 1.0, 0.01, self.L_var, self.full_update)
        self.L_lbl = ttk.Label(self.ctrl, style="Val.TLabel")
        self.L_lbl.pack(anchor=tk.W, padx=10)

        self.h_var = tk.DoubleVar(value=0.002)
        ttk.Label(self.ctrl, text="Grossura h (m):").pack(
            anchor=tk.W, padx=10, pady=(6, 0))
        self._mk_scale(0.0005, 0.02, 0.0005, self.h_var, self.full_update)
        self.h_lbl = ttk.Label(self.ctrl, style="Val.TLabel")
        self.h_lbl.pack(anchor=tk.W, padx=10)

        # Visualização
        self._sep(); self._header("🎵  Modo de Visualização")
        self.view_var = tk.StringVar(value="driven")
        vf = ttk.Frame(self.ctrl); vf.pack(fill=tk.X, padx=10)
        ttk.Radiobutton(vf, text="Resposta forçada (transdutores)",
                        variable=self.view_var, value="driven",
                        command=self.full_update).pack(anchor=tk.W)
        ttk.Radiobutton(vf, text="Modo individual (n, m)",
                        variable=self.view_var, value="mode",
                        command=self.full_update).pack(anchor=tk.W)

        nf = ttk.Frame(self.ctrl); nf.pack(fill=tk.X, padx=10, pady=3)
        self.n_var = tk.IntVar(value=3)
        self.m_var = tk.IntVar(value=2)
        ttk.Label(nf, text="n:").pack(side=tk.LEFT)
        tk.Spinbox(nf, from_=1, to=15, textvariable=self.n_var, width=4,
                   command=self.full_update, bg=self.BG2, fg=self.FG,
                   buttonbackground=self.BG3).pack(side=tk.LEFT, padx=(2, 12))
        ttk.Label(nf, text="m:").pack(side=tk.LEFT)
        tk.Spinbox(nf, from_=1, to=15, textvariable=self.m_var, width=4,
                   command=self.full_update, bg=self.BG2, fg=self.FG,
                   buttonbackground=self.BG3).pack(side=tk.LEFT, padx=2)

        self.sign_var = tk.IntVar(value=1)
        sf = ttk.Frame(self.ctrl); sf.pack(fill=tk.X, padx=10)
        ttk.Label(sf, text="Simetria:").pack(side=tk.LEFT)
        ttk.Radiobutton(sf, text=" + ", variable=self.sign_var, value=1,
                        command=self.full_update).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(sf, text=" − ", variable=self.sign_var, value=-1,
                        command=self.full_update).pack(side=tk.LEFT, padx=4)

        # Transdutores
        self._sep(); self._header("📍  Transdutores (bipolares)")
        ttk.Label(self.ctrl,
                  text="Clica no prato → adicionar\n"
                       "Arrasta → mover · Duplo-clique → inverter fase\n"
                       "🔴 empurra p/ cima (+)  🔵 empurra p/ baixo (−)",
                  style="Small.TLabel").pack(anchor=tk.W, padx=10)
        self.trans_lb = tk.Listbox(
            self.ctrl, height=5, bg=self.BG2, fg=self.FG,
            selectbackground=self.ACCENT, font=("Consolas", 9),
            highlightthickness=0, borderwidth=1, relief="flat")
        self.trans_lb.pack(fill=tk.X, padx=10, pady=3)
        bf = ttk.Frame(self.ctrl); bf.pack(fill=tk.X, padx=10, pady=2)
        ttk.Button(bf, text="＋ Adicionar",
                   command=self._add_trans).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="✕ Remover",
                   command=self._rem_trans).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="↕ Inv. Fase",
                   command=self._flip_trans).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="⌖ Centro",
                   command=self._center_trans).pack(side=tk.LEFT, padx=2)
        self._refresh_trans()

        # Entrada manual de posição
        ttk.Label(self.ctrl, text="Definir posição (selecionado):",
                  style="Small.TLabel").pack(anchor=tk.W, padx=10, pady=(6,0))
        pf = ttk.Frame(self.ctrl); pf.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(pf, text="x:", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.tx_entry = tk.Entry(pf, width=8, bg=self.BG2, fg=self.FG,
                                 insertbackground=self.FG,
                                 font=("Consolas", 9))
        self.tx_entry.pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(pf, text="y:", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.ty_entry = tk.Entry(pf, width=8, bg=self.BG2, fg=self.FG,
                                 insertbackground=self.FG,
                                 font=("Consolas", 9))
        self.ty_entry.pack(side=tk.LEFT, padx=2)
        ttk.Button(pf, text="✓", width=2,
                   command=self._apply_pos).pack(side=tk.LEFT, padx=4)
        self.trans_lb.bind("<<ListboxSelect>>", self._on_trans_select)

        # Grid toggle
        self.grid_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.ctrl, text="Mostrar grelha no prato",
                        variable=self.grid_var,
                        command=self.full_update).pack(
                            anchor=tk.W, padx=10, pady=(4, 0))

        # Frequência
        self._sep(); self._header("🔊  Frequência de Excitação")
        self.freq_var = tk.DoubleVar(value=500.0)
        self.freq_sc = self._mk_scale(20, 10000, 1, self.freq_var,
                                      self._debounced_pattern)
        self.freq_lbl = ttk.Label(self.ctrl, style="Freq.TLabel")
        self.freq_lbl.pack(anchor=tk.W, padx=10)
        rf = ttk.Frame(self.ctrl); rf.pack(fill=tk.X, padx=10, pady=2)
        ttk.Button(rf, text="◀ Ressonância",
                   command=lambda: self._snap(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(rf, text="Próxima ▶",
                   command=lambda: self._snap(1)).pack(side=tk.LEFT, padx=2)

        self.fmax_var = tk.DoubleVar(value=5000)
        ttk.Label(self.ctrl, text="Freq. máx. espectro (Hz):"
                  ).pack(anchor=tk.W, padx=10, pady=(6, 0))
        self._mk_scale(500, 20000, 100, self.fmax_var,
                       self._update_spectrum_only)

        # Avançados
        self._sep(); self._header("🔧  Parâmetros Avançados")
        self.damp_var = tk.DoubleVar(value=0.005)
        ttk.Label(self.ctrl, text="Amortecimento ζ:").pack(
            anchor=tk.W, padx=10, pady=(4, 0))
        self._mk_scale(0.001, 0.10, 0.001, self.damp_var, self.full_update)
        self.damp_lbl = ttk.Label(self.ctrl, style="Val.TLabel")
        self.damp_lbl.pack(anchor=tk.W, padx=10)

        self.nmodes_var = tk.IntVar(value=8)
        ttk.Label(self.ctrl, text="Nº de modos (precisão):"
                  ).pack(anchor=tk.W, padx=10, pady=(6, 0))
        self._mk_scale(3, 15, 1, self.nmodes_var, self.full_update)

        # Info
        self._sep(); self._header("ℹ  Informações")
        self.info_text = tk.Text(
            self.ctrl, height=10, bg=self.BG2, fg=self.FG,
            font=("Consolas", 8), wrap=tk.WORD,
            highlightthickness=0, borderwidth=0, relief="flat")
        self.info_text.pack(fill=tk.X, padx=10, pady=4)
        self.info_text.config(state=tk.DISABLED)
        self.warn_lbl = ttk.Label(self.ctrl, style="Warn.TLabel",
                                  wraplength=280)
        self.warn_lbl.pack(anchor=tk.W, padx=10, pady=(0, 14))

    # ── Gráficos ──────────────────────────────────────────────────────
    def _build_plots(self, parent):
        self.fig = Figure(figsize=(10, 8), facecolor=self.PL_BG, dpi=100)
        self.ax_pat  = self.fig.add_axes([0.04, 0.34, 0.50, 0.62])
        self.ax_3d   = self.fig.add_axes([0.56, 0.34, 0.42, 0.62],
                                         projection="3d")
        self.ax_spec = self.fig.add_axes([0.07, 0.07, 0.88, 0.22])
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.canvas.mpl_connect("button_press_event",   self._on_press)
        self.canvas.mpl_connect("motion_notify_event",  self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)

    # ── Transdutores ──────────────────────────────────────────────────
    def _refresh_trans(self):
        self.trans_lb.delete(0, tk.END)
        for i, (x, y, p) in enumerate(self.transducers):
            sym = "▲+" if p > 0 else "▼−"
            self.trans_lb.insert(
                tk.END, f"  T{i+1} {sym}: ({x:+.3f}, {y:+.3f}) m")

    def _add_trans(self):
        L = self.L_var.get()
        tx = round(np.random.uniform(-L/3, L/3), 4)
        ty = round(np.random.uniform(-L/3, L/3), 4)
        self.transducers.append((tx, ty, +1))
        self._refresh_trans(); self.full_update()

    def _rem_trans(self):
        sel = self.trans_lb.curselection()
        if sel:
            self.transducers.pop(sel[0])
        if not self.transducers:
            self.transducers = [(0.0, 0.0, +1)]
        self._refresh_trans(); self.full_update()

    def _flip_trans(self):
        sel = self.trans_lb.curselection()
        idx = sel[0] if sel else 0
        if idx < len(self.transducers):
            x, y, p = self.transducers[idx]
            self.transducers[idx] = (x, y, -p)
        self._refresh_trans(); self.full_update()

    def _center_trans(self):
        sel = self.trans_lb.curselection()
        idx = sel[0] if sel else 0
        if idx < len(self.transducers):
            _, _, p = self.transducers[idx]
            self.transducers[idx] = (0.0, 0.0, p)
        self._refresh_trans(); self.full_update()

    def _on_trans_select(self, evt):
        """Preenche os campos x/y ao selecionar um transdutor na lista."""
        sel = self.trans_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self.transducers):
            x, y, _ = self.transducers[idx]
            self.tx_entry.delete(0, tk.END)
            self.tx_entry.insert(0, f"{x:.4f}")
            self.ty_entry.delete(0, tk.END)
            self.ty_entry.insert(0, f"{y:.4f}")

    def _apply_pos(self):
        """Aplica a posição digitada ao transdutor selecionado."""
        sel = self.trans_lb.curselection()
        idx = sel[0] if sel else 0
        if idx >= len(self.transducers):
            return
        try:
            x = float(self.tx_entry.get())
            y = float(self.ty_entry.get())
        except ValueError:
            self.warn_lbl.config(text="⚠ Valor inválido. Usa números (ex: 0.05)")
            return
        L = self.L_var.get()
        x = max(-L/2, min(L/2, x))
        y = max(-L/2, min(L/2, y))
        _, _, p = self.transducers[idx]
        self.transducers[idx] = (round(x, 4), round(y, 4), p)
        self._refresh_trans(); self.full_update()

    # ── Interação com o prato (click / drag / double-click) ──────────
    def _on_press(self, evt):
        if evt.inaxes is not self.ax_pat or evt.button != 1:
            return
        L = self.L_var.get()
        x, y = evt.xdata, evt.ydata
        if x is None or y is None or abs(x) > L/2 or abs(y) > L/2:
            return

        # duplo-clique → inverter fase do transdutor mais próximo
        if evt.dblclick:
            best_i, best_d = None, 1e18
            for i, (tx, ty, _) in enumerate(self.transducers):
                d = (x - tx)**2 + (y - ty)**2
                if d < best_d:
                    best_i, best_d = i, d
            if best_i is not None and best_d < (L * 0.06)**2:
                tx, ty, p = self.transducers[best_i]
                self.transducers[best_i] = (tx, ty, -p)
                self._refresh_trans(); self.full_update()
            return

        # perto de existente → arrastar
        for i, (tx, ty, _) in enumerate(self.transducers):
            if (x - tx)**2 + (y - ty)**2 < (L * 0.04)**2:
                self._drag_idx = i
                self._dragging = True
                return

        # novo transdutor
        self.transducers.append((round(x, 4), round(y, 4), +1))
        self._refresh_trans(); self.full_update()

    def _on_motion(self, evt):
        if self._drag_idx is None or evt.inaxes is not self.ax_pat:
            return
        if evt.xdata is None or evt.ydata is None:
            return
        L = self.L_var.get()
        x = float(np.clip(evt.xdata, -L/2, L/2))
        y = float(np.clip(evt.ydata, -L/2, L/2))
        _, _, p = self.transducers[self._drag_idx]
        self.transducers[self._drag_idx] = (round(x, 4), round(y, 4), p)
        self._refresh_trans()
        self._debounced_pattern()

    def _on_release(self, evt):
        if self._drag_idx is not None:
            self._drag_idx = None
            self._dragging = False
            self.full_update()

    # ── Debounce para sliders e drag ──────────────────────────────────
    def _debounced_pattern(self):
        if self._update_id is not None:
            self.root.after_cancel(self._update_id)
        self._update_id = self.root.after(40, self._do_pattern_update)

    def _do_pattern_update(self):
        self._update_id = None
        self._sync_labels()
        self._update_pattern(skip_3d=self._dragging)
        self.canvas.draw_idle()

    # ── Snap ressonância ──────────────────────────────────────────────
    def _snap(self, direction):
        L, h = self.L_var.get(), self.h_var.get()
        mat = MATERIALS[self.material_var.get()]
        D = self.physics.flexural_rigidity(mat["E"], h, mat["nu"])
        sign, nm = self.sign_var.get(), self.nmodes_var.get()
        cur = self.freq_var.get()

        self.physics._build_cache(L, sign, nm, D, mat["rho"], h)
        F_nm = self.physics._coupling(self.transducers, L, sign)

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

    # ── Actualizações ─────────────────────────────────────────────────
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
        L, h = self.L_var.get(), self.h_var.get()
        self.L_lbl.config(text=f"{L:.2f} m  ({L*100:.0f} cm)")
        self.h_lbl.config(text=f"{h*1000:.1f} mm")
        self.freq_lbl.config(text=f"{self.freq_var.get():.0f} Hz")
        self.damp_lbl.config(text=f"ζ = {self.damp_var.get():.3f}")
        mat = MATERIALS[self.material_var.get()]
        self.mat_info.config(
            text=f"E={mat['E']/1e9:.0f} GPa · ρ={mat['rho']} kg/m³ · "
                 f"ν={mat['nu']:.2f}")

    # ── Espectro ──────────────────────────────────────────────────────
    def _update_spectrum(self):
        L, h = self.L_var.get(), self.h_var.get()
        mat = MATERIALS[self.material_var.get()]
        D = self.physics.flexural_rigidity(mat["E"], h, mat["nu"])
        zeta, sign, nm = self.damp_var.get(), self.sign_var.get(), \
                         self.nmodes_var.get()
        fmax = self.fmax_var.get()

        freqs, energy = self.physics.frequency_sweep(
            L, D, mat["rho"], h, self.transducers,
            freq_range=(20, fmax), n_modes=nm, damping=zeta,
            sign=sign, n_points=400)

        mx = energy.max()
        edb = 10.0 * np.log10(energy / mx + 1e-15) if mx > 0 else \
              np.full_like(energy, -80.0)

        ax = self.ax_spec; ax.clear()
        ax.fill_between(freqs, edb, -80, alpha=0.25, color=self.ACCENT)
        ax.plot(freqs, edb, color=self.ACCENT, linewidth=0.9)
        ax.axvline(self.freq_var.get(), color=self.RED, lw=1.4,
                   ls="--", alpha=0.85)
        try:
            peaks, _ = find_peaks(edb, height=-20, distance=5, prominence=3)
            if len(peaks):
                ax.plot(freqs[peaks], edb[peaks], "v",
                        color=self.YELLOW, ms=5, zorder=5)
        except Exception:
            pass
        ax.set_xlim(20, fmax); ax.set_ylim(-65, 5)
        ax.set_xlabel("Frequência (Hz)", color=self.FG_DIM, fontsize=9)
        ax.set_ylabel("dB", color=self.FG_DIM, fontsize=9)
        ax.set_title("Espectro de Ressonância", color=self.FG, fontsize=10)
        ax.set_facecolor(self.PL_BG)
        ax.tick_params(colors=self.FG_DIM, labelsize=7)
        for sp in ax.spines.values():
            sp.set_color(self.BG3)
        ax.grid(True, alpha=0.12, color=self.FG_DIM)

    # ── Padrão 2D + 3D ───────────────────────────────────────────────
    def _update_pattern(self, skip_3d=False):
        L, h = self.L_var.get(), self.h_var.get()
        mat = MATERIALS[self.material_var.get()]
        D = self.physics.flexural_rigidity(mat["E"], h, mat["nu"])
        n, m = self.n_var.get(), self.m_var.get()
        sign, zeta = self.sign_var.get(), self.damp_var.get()
        nm = self.nmodes_var.get()
        freq = self.freq_var.get()
        view = self.view_var.get()

        if view == "mode":
            Z = self.physics.mode_shape(n, m, L, sign)
            sand = np.exp(-40.0 * Z**2)
            Z_3d = Z
            f_mode = self.physics.mode_frequency(n, m, L, D, mat["rho"], h)
            title = f"Modo ({n},{m}) — f = {f_mode:.1f} Hz"
        else:
            # UMA SÓ chamada para sand + 3D
            sand, Z_3d = self.physics.sand_and_3d(
                freq, L, D, mat["rho"], h, self.transducers,
                n_modes=nm, damping=zeta, sign=sign)
            title = f"Padrão a {freq:.0f} Hz"

        ext = [-L/2, L/2, -L/2, L/2]

        # 2D
        ax = self.ax_pat; ax.clear()
        ax.imshow(sand, cmap=SAND_CMAP, origin="lower", extent=ext,
                  interpolation="bilinear", vmin=0, vmax=1, aspect="equal")
        ax.plot([-L/2, L/2, L/2, -L/2, -L/2],
                [-L/2, -L/2, L/2, L/2, -L/2], color="#555", lw=1.5)
        # Grid sobre o prato
        if self.grid_var.get():
            n_div = max(4, int(round(L / 0.05)))  # ~5 cm por divisão
            n_div = min(n_div, 20)                 # não mais que 20 linhas
            ticks = np.linspace(-L/2, L/2, n_div + 1)
            for t in ticks:
                ax.axhline(t, color="#ffffff", alpha=0.12, lw=0.5,
                           zorder=2)
                ax.axvline(t, color="#ffffff", alpha=0.12, lw=0.5,
                           zorder=2)
            # linhas centrais mais fortes
            ax.axhline(0, color="#ffffff", alpha=0.3, lw=0.8, ls="--",
                       zorder=2)
            ax.axvline(0, color="#ffffff", alpha=0.3, lw=0.8, ls="--",
                       zorder=2)
        for i, (tx, ty, p) in enumerate(self.transducers):
            c = "#ff4444" if p > 0 else "#4488ff"
            mk = "^" if p > 0 else "v"
            ax.plot(tx, ty, mk, color=c, ms=11,
                    markeredgecolor="white", markeredgewidth=1.4, zorder=5)
            ax.annotate(f"T{i+1}", (tx, ty), textcoords="offset points",
                        xytext=(8, 8), fontsize=7, color=c,
                        fontweight="bold")
        ax.set_title(title, color=self.FG, fontsize=12, fontweight="bold")
        ax.set_xlabel("x (m)", color=self.FG_DIM, fontsize=9)
        ax.set_ylabel("y (m)", color=self.FG_DIM, fontsize=9)
        ax.tick_params(colors=self.FG_DIM, labelsize=7)
        ax.set_facecolor(self.PL_BG)
        for sp in ax.spines.values():
            sp.set_color(self.BG3)

        # 3D  (saltar durante drag para fluidez)
        if not skip_3d:
            ax3 = self.ax_3d; ax3.clear()
            step = max(1, self.physics.res // 50)
            Xs = (self.physics.X_norm * L)[::step, ::step]
            Ys = (self.physics.Y_norm * L)[::step, ::step]
            Zs = Z_3d[::step, ::step]
            ax3.plot_surface(Xs, Ys, Zs, cmap="coolwarm", alpha=0.88,
                             edgecolor="none", antialiased=True)
            ax3.set_title("Deformação da Placa", color=self.FG,
                          fontsize=10, pad=0)
            ax3.set_facecolor(self.PL_BG)
            ax3.tick_params(colors=self.FG_DIM, labelsize=5)
            ax3.set_xlabel("x", fontsize=6, color=self.FG_DIM, labelpad=-2)
            ax3.set_ylabel("y", fontsize=6, color=self.FG_DIM, labelpad=-2)
            ax3.set_zlabel("w", fontsize=6, color=self.FG_DIM, labelpad=-2)
            try:
                for a in (ax3.xaxis, ax3.yaxis, ax3.zaxis):
                    a.pane.fill = False
                    a.pane.set_edgecolor(self.BG3)
            except Exception:
                pass

        # info
        self._write_info(
            freq if view == "driven" else
            self.physics.mode_frequency(n, m, L, D, mat["rho"], h),
            n, m, L, h, mat, D, view)

    # ── Info panel ────────────────────────────────────────────────────
    def _write_info(self, freq, n, m, L, h, mat, D, view):
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete("1.0", tk.END)
        name = self.material_var.get()
        lines = [
            f"Material: {name}",
            f"E={mat['E']/1e9:.1f} GPa  ρ={mat['rho']} kg/m³  ν={mat['nu']:.2f}",
            f"D = {D:.6f} N·m",
            f"Placa: {L*100:.1f}×{L*100:.1f} cm, h={h*1000:.1f} mm",
            f"Transdutores: {len(self.transducers)}"
            f"  ({sum(1 for _,_,p in self.transducers if p>0)}▲ "
            f"{sum(1 for _,_,p in self.transducers if p<0)}▼)",
        ]
        if view == "mode":
            fm = self.physics.mode_frequency(n, m, L, D, mat["rho"], h)
            lines.append(f"Modo ({n},{m}) → f = {fm:.1f} Hz")
        else:
            lines.append(f"Freq. excitação: {freq:.1f} Hz")
            nm_max = self.nmodes_var.get()
            best, best_f = None, 1e18
            for ni in range(1, nm_max + 1):
                for mi in range(1, nm_max + 1):
                    fi = self.physics.mode_frequency(ni, mi, L, D,
                                                     mat["rho"], h)
                    if abs(fi - freq) < abs(best_f - freq):
                        best, best_f = (ni, mi), fi
            if best:
                lines.append(f"Modo +próximo: ({best[0]},{best[1]}) "
                             f"a {best_f:.1f} Hz")
        self.info_text.insert("1.0", "\n".join(lines))
        self.info_text.config(state=tk.DISABLED)

        sign = self.sign_var.get()
        coup = sum(abs(self.physics.transducer_coupling_single(
            tx, ty, n, m, L, sign)) for tx, ty, _ in self.transducers)
        if coup < 0.05 and view == "driven":
            self.warn_lbl.config(
                text="⚠ Transdutores perto de nós — excitação fraca!")
        else:
            self.warn_lbl.config(text="")


# Adicionar método helper rápido para info
ChladniPhysics.transducer_coupling_single = staticmethod(
    lambda tx, ty, n, m, L, sign=1: (
        np.cos(n*np.pi*tx/L)*np.cos(m*np.pi*ty/L) +
        sign * np.cos(m*np.pi*tx/L)*np.cos(n*np.pi*ty/L)
    )
)


# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    ChladniApp(root)
    root.mainloop()