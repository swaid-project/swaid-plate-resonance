"""
Motor de física para o simulador de figuras de Chladni.
Suporta placas quadradas, rectangulares e circulares.
Inclui simulação de partículas e fases arbitrárias nos transdutores.
"""

import numpy as np
from scipy.special import jn, jn_zeros
from scipy.ndimage import map_coordinates
from .constants import BESSEL_ZEROS


class ChladniPhysics:
    """Motor de física vectorizado para vibrações de placas finas (Kirchhoff)."""

    def __init__(self, resolution: int = 200):
        self.res = resolution
        t = np.linspace(-0.5, 0.5, self.res)
        self.X_norm, self.Y_norm = np.meshgrid(t, t)

        # Cache
        self._cache_key = None
        self._modes = None
        self._omega_nm = None
        self._f_nm = None
        self._ns = None
        self._ms = None

        # Circular grid (polar)
        r = np.linspace(0, 0.5, self.res)
        theta = np.linspace(0, 2 * np.pi, self.res)
        self.R_norm, self.Theta_norm = np.meshgrid(r, theta)
        self.X_circ = self.R_norm * np.cos(self.Theta_norm)
        self.Y_circ = self.R_norm * np.sin(self.Theta_norm)

        # Particle state
        self._particles = None
        self._particle_vx = None
        self._particle_vy = None

    # ── Flexural rigidity ─────────────────────────────────────────────
    @staticmethod
    def flexural_rigidity(E, h, nu):
        """D = Eh³ / [12(1 - ν²)]"""
        return (E * h**3) / (12.0 * (1.0 - nu**2))

    # ══════════════════════════════════════════════════════════════════
    #  RECTANGULAR / SQUARE PLATE  (simply-supported)
    # ══════════════════════════════════════════════════════════════════

    def _build_cache_rect(self, Lx, Ly, sign, n_modes, D, rho, h):
        """Pre-compute modes for rectangular plate.
        Simply-supported plate: φ_nm = sin(nπx/Lx) sin(mπy/Ly)
        with natural frequency:
            f_nm = (π/2) √(D/(ρh)) [(n/Lx)² + (m/Ly)²]
        """
        key = ("rect", Lx, Ly, sign, n_modes, D, rho, h)
        if self._cache_key == key:
            return
        self._cache_key = key

        ns = np.arange(1, n_modes + 1)
        ms = np.arange(1, n_modes + 1)
        NN, MM = np.meshgrid(ns, ms)
        self._ns = NN.ravel()
        self._ms = MM.ravel()

        # Natural frequencies for simply-supported rectangular plate
        # ω_nm = π² √(D/(ρh)) [(n/Lx)² + (m/Ly)²]
        # f_nm = ω_nm / (2π) = (π/2) √(D/(ρh)) [(n/Lx)² + (m/Ly)²]
        f_nm = (np.pi / 2.0) * np.sqrt(D / (rho * h)) * \
               ((self._ns / Lx)**2 + (self._ms / Ly)**2)
        self._omega_nm = 2.0 * np.pi * f_nm
        self._f_nm = f_nm

        # Mode shapes: φ_nm(x,y) = sin(nπx/Lx)sin(mπy/Ly) ± sin(mπx/Lx)sin(nπy/Ly)
        X = (self.X_norm + 0.5) * Lx  # shift to [0, Lx]
        Y = (self.Y_norm + 0.5) * Ly  # shift to [0, Ly]

        n3 = self._ns[:, None, None]
        m3 = self._ms[:, None, None]
        piX_Lx = np.pi * X[None, :, :] / Lx
        piY_Ly = np.pi * Y[None, :, :] / Ly

        t1 = np.sin(n3 * piX_Lx) * np.sin(m3 * piY_Ly)
        t2 = np.sin(m3 * piX_Lx) * np.sin(n3 * piY_Ly)
        self._modes = t1 + sign * t2

    def _coupling_rect(self, transducers, Lx, Ly, sign):
        """Compute forcing coefficients for each mode.
        transducers: list of (tx, ty, amplitude, phase_rad).
        """
        F = np.zeros(len(self._ns), dtype=complex)
        for tx, ty, amp, phase in transducers:
            # Shift coords to [0, Lx] x [0, Ly]
            x_s = tx + Lx / 2.0
            y_s = ty + Ly / 2.0
            cn = np.sin(self._ns * np.pi * x_s / Lx)
            cm = np.sin(self._ms * np.pi * y_s / Ly)
            cn2 = np.sin(self._ms * np.pi * x_s / Lx)
            cm2 = np.sin(self._ns * np.pi * y_s / Ly)
            F += amp * np.exp(1j * phase) * (cn * cm + sign * cn2 * cm2)
        return F

    # ══════════════════════════════════════════════════════════════════
    #  CIRCULAR PLATE  (clamped edge)
    # ══════════════════════════════════════════════════════════════════

    def _build_cache_circ(self, R, n_modes, D, rho, h):
        """Pre-compute modes for circular plate (clamped edge).
        Mode shapes: φ_nm(r,θ) = J_n(λ_nm r/R) cos(nθ)
        Natural frequency:
            f_nm = λ_nm² / (2πR²) √(D/(ρh))
        """
        key = ("circ", R, n_modes, D, rho, h)
        if self._cache_key == key:
            return
        self._cache_key = key

        ns_list = []
        ms_list = []
        lambda_nm = []

        for n_circ in range(n_modes):
            n_radial = min(n_modes, 3)  # radial modes
            zeros = jn_zeros(n_circ, n_radial)
            for m_idx, z in enumerate(zeros):
                ns_list.append(n_circ)
                ms_list.append(m_idx + 1)
                lambda_nm.append(z)

        self._ns = np.array(ns_list)
        self._ms = np.array(ms_list)
        lam = np.array(lambda_nm)

        # f_nm = λ_nm² / (2πR²) √(D/(ρh))
        f_nm = (lam**2) / (2.0 * np.pi * R**2) * np.sqrt(D / (rho * h))
        self._omega_nm = 2.0 * np.pi * f_nm
        self._f_nm = f_nm
        self._lambda_nm = lam

        # Mode shapes on Cartesian grid
        r_grid = self.R_norm * 2.0 * R  # [0, R]
        theta_grid = self.Theta_norm

        n3 = self._ns[:, None, None]
        lam3 = lam[:, None, None]
        r3 = r_grid[None, :, :]
        t3 = theta_grid[None, :, :]

        # φ_nm = J_n(λ_nm r/R) cos(nθ)
        self._modes = jn(n3, lam3 * r3 / R) * np.cos(n3 * t3)

        # Mask outside circle
        self._circ_mask = (r_grid <= R)

    def _coupling_circ(self, transducers, R):
        """Coupling for circular plate transducers."""
        F = np.zeros(len(self._ns), dtype=complex)
        for tx, ty, amp, phase in transducers:
            r_t = np.sqrt(tx**2 + ty**2)
            theta_t = np.arctan2(ty, tx)
            for k in range(len(self._ns)):
                n_k = self._ns[k]
                lam_k = self._lambda_nm[k]
                mode_val = jn(n_k, lam_k * r_t / R) * np.cos(n_k * theta_t)
                F[k] += amp * np.exp(1j * phase) * mode_val
        return F

    # ══════════════════════════════════════════════════════════════════
    #  UNIFIED DRIVEN RESPONSE
    # ══════════════════════════════════════════════════════════════════

    def driven_response(self, freq, Lx, Ly, D, rho, h, transducers,
                        n_modes=8, damping=0.005, sign=1,
                        geometry="Quadrada"):
        """Compute driven response for any geometry.
        transducers: list of (tx, ty, amplitude, phase_rad)
        """
        omega = 2.0 * np.pi * freq

        if geometry == "Circular":
            R = Lx / 2.0
            self._build_cache_circ(R, n_modes, D, rho, h)
            F_nm = self._coupling_circ(transducers, R)
        else:
            self._build_cache_rect(Lx, Ly, sign, n_modes, D, rho, h)
            F_nm = self._coupling_rect(transducers, Lx, Ly, sign)

        denom = self._omega_nm**2 - omega**2 + \
                2j * damping * self._omega_nm * omega
        safe = np.abs(denom) > 1e-30
        coeffs = np.zeros(len(F_nm), dtype=complex)
        coeffs[safe] = F_nm[safe] / denom[safe]
        resp = np.einsum("k,kij->ij", coeffs, self._modes)
        return resp

    def driven_response_cartesian(self, freq, Lx, Ly, D, rho, h,
                                   transducers, n_modes=8, damping=0.005,
                                   sign=1, geometry="Quadrada"):
        """Compute driven response on the Cartesian (X_norm, Y_norm) grid.
        For circular plates, evaluates mode shapes at Cartesian grid points
        instead of the polar grid. Used by particle simulation.
        """
        if geometry != "Circular":
            return self.driven_response(freq, Lx, Ly, D, rho, h,
                                        transducers, n_modes, damping,
                                        sign, geometry)

        R = Lx / 2.0
        omega = 2.0 * np.pi * freq
        self._build_cache_circ(R, n_modes, D, rho, h)
        F_nm = self._coupling_circ(transducers, R)

        denom = self._omega_nm**2 - omega**2 + \
                2j * damping * self._omega_nm * omega
        safe = np.abs(denom) > 1e-30
        coeffs = np.zeros(len(F_nm), dtype=complex)
        coeffs[safe] = F_nm[safe] / denom[safe]

        # Evaluate modes on Cartesian grid
        X_phys = self.X_norm * Lx
        Y_phys = self.Y_norm * Lx  # Ly = Lx for circular
        R_phys = np.sqrt(X_phys**2 + Y_phys**2)
        Theta_phys = np.arctan2(Y_phys, X_phys)

        n3 = self._ns[:, None, None]
        lam3 = self._lambda_nm[:, None, None]
        R3 = R_phys[None, :, :]
        T3 = Theta_phys[None, :, :]

        modes_cart = jn(n3, lam3 * R3 / R) * np.cos(n3 * T3)
        resp = np.einsum("k,kij->ij", coeffs, modes_cart)
        resp[R_phys > R] = 0.0
        return resp

    def sand_and_3d(self, freq, Lx, Ly, D, rho, h, transducers,
                    n_modes=8, damping=0.005, sign=1,
                    geometry="Quadrada"):
        """Returns (sand_pattern, Z_3d_normalized)."""
        resp = self.driven_response(freq, Lx, Ly, D, rho, h, transducers,
                                    n_modes, damping, sign, geometry)
        amp = np.abs(resp)
        mx = amp.max()
        amp_n = amp / mx if mx > 0 else amp
        sand = np.exp(-35.0 * amp_n**2)

        if geometry == "Circular":
            sand = np.where(self._circ_mask, sand, 0.0)

        Z = np.real(resp)
        zmx = np.abs(Z).max()
        if zmx > 0:
            Z = Z / zmx
        return sand, Z

    def mode_shape(self, n, m, Lx, Ly, sign=1, geometry="Quadrada"):
        """Single mode shape for visualization."""
        if geometry == "Circular":
            R = Lx / 2.0
            r_grid = self.R_norm * 2.0 * R
            theta_grid = self.Theta_norm
            # Use n-th Bessel zero for the m-th radial mode
            zeros = jn_zeros(n, m)
            lam = zeros[-1]  # m-th zero
            Z = jn(n, lam * r_grid / R) * np.cos(n * theta_grid)
            Z[r_grid > R] = 0.0
            return Z
        else:
            X = (self.X_norm + 0.5) * Lx
            Y = (self.Y_norm + 0.5) * Ly
            t1 = np.sin(n * np.pi * X / Lx) * np.sin(m * np.pi * Y / Ly)
            t2 = np.sin(m * np.pi * X / Lx) * np.sin(n * np.pi * Y / Ly)
            return t1 + sign * t2

    def mode_frequency(self, n, m, Lx, Ly, D, rho, h, geometry="Quadrada"):
        """Natural frequency for mode (n,m)."""
        if geometry == "Circular":
            R = Lx / 2.0
            zeros = jn_zeros(n, m)
            lam = zeros[-1]
            return (lam**2) / (2.0 * np.pi * R**2) * np.sqrt(D / (rho * h))
        else:
            return (np.pi / 2.0) * np.sqrt(D / (rho * h)) * \
                   ((n / Lx)**2 + (m / Ly)**2)

    @staticmethod
    def transducer_coupling_single(tx, ty, n, m, Lx, Ly, sign=1):
        """Single-mode coupling for a transducer (for info display)."""
        x_s = tx + Lx / 2.0
        y_s = ty + Ly / 2.0
        return (np.sin(n * np.pi * x_s / Lx) * np.sin(m * np.pi * y_s / Ly) +
                sign * np.sin(m * np.pi * x_s / Lx) * np.sin(n * np.pi * y_s / Ly))

    # ── Frequency sweep ──────────────────────────────────────────────
    def frequency_sweep(self, Lx, Ly, D, rho, h, transducers,
                        freq_range=(20, 5000), n_modes=8,
                        damping=0.005, sign=1, n_points=400,
                        geometry="Quadrada"):
        """Vectorized frequency sweep."""
        if geometry == "Circular":
            R = Lx / 2.0
            self._build_cache_circ(R, n_modes, D, rho, h)
            F_nm = self._coupling_circ(transducers, R)
        else:
            self._build_cache_rect(Lx, Ly, sign, n_modes, D, rho, h)
            F_nm = self._coupling_rect(transducers, Lx, Ly, sign)

        freqs = np.linspace(freq_range[0], freq_range[1], n_points)
        omega = 2.0 * np.pi * freqs

        w_nm = self._omega_nm[None, :]
        w = omega[:, None]
        denom = w_nm**2 - w**2 + 2j * damping * w_nm * w
        abs_d2 = np.maximum(np.abs(denom)**2, 1e-60)
        energy = np.sum(np.abs(F_nm[None, :])**2 / abs_d2, axis=1)
        return freqs, energy

    # ══════════════════════════════════════════════════════════════════
    #  PARTICLE SIMULATION
    # ══════════════════════════════════════════════════════════════════

    def init_particles(self, n_particles, Lx, Ly, geometry="Quadrada"):
        """Initialize random particle positions on the plate."""
        if geometry == "Circular":
            R = Lx / 2.0
            r = R * np.sqrt(np.random.uniform(0, 1, n_particles))
            theta = np.random.uniform(0, 2 * np.pi, n_particles)
            self._particles = np.column_stack([
                r * np.cos(theta),
                r * np.sin(theta)
            ])
        else:
            self._particles = np.column_stack([
                np.random.uniform(-Lx / 2, Lx / 2, n_particles),
                np.random.uniform(-Ly / 2, Ly / 2, n_particles),
            ])
        self._particle_vx = np.zeros(n_particles)
        self._particle_vy = np.zeros(n_particles)

    def step_particles(self, resp, Lx, Ly, dt=0.002, friction=0.85,
                       force_scale=0.5, geometry="Quadrada"):
        """Advance particle positions using gradient of vibration energy.

        Particles move towards nodal lines (minima of |response|²).
        The force is proportional to -∇(|w(x,y)|²), matching real
        time-averaged acoustic radiation pressure on sand grains.
        Expects resp on the Cartesian (X_norm, Y_norm) grid.
        """
        if self._particles is None:
            return self._particles

        amp = np.abs(resp)
        mx = amp.max()
        if mx > 0:
            amp = amp / mx

        # Physical force ∝ -∇(A²): time-averaged radiation pressure
        amp_sq = amp ** 2
        res = amp.shape[0]
        dx = Lx / res
        dy = Ly / res
        gy, gx = np.gradient(amp_sq, dy, dx)

        # Map particle positions to floating-point grid coordinates
        px = self._particles[:, 0]
        py = self._particles[:, 1]
        gx_idx = (px / Lx + 0.5) * (res - 1)
        gy_idx = (py / Ly + 0.5) * (res - 1)
        gx_idx = np.clip(gx_idx, 0, res - 1)
        gy_idx = np.clip(gy_idx, 0, res - 1)

        # Bilinear interpolation of gradient at all particle positions
        coords = np.array([gy_idx, gx_idx])
        fx = -map_coordinates(gx, coords, order=1, mode='nearest') * force_scale
        fy = -map_coordinates(gy, coords, order=1, mode='nearest') * force_scale

        # Update velocities with friction
        self._particle_vx = self._particle_vx * friction + fx * dt
        self._particle_vy = self._particle_vy * friction + fy * dt

        # Update positions
        px_new = px + self._particle_vx * dt
        py_new = py + self._particle_vy * dt

        # Boundary conditions
        if geometry == "Circular":
            R = Lx / 2.0
            r = np.sqrt(px_new**2 + py_new**2)
            outside = r > R
            if np.any(outside):
                angles = np.arctan2(py_new[outside], px_new[outside])
                px_new[outside] = R * 0.98 * np.cos(angles)
                py_new[outside] = R * 0.98 * np.sin(angles)
                self._particle_vx[outside] *= -0.5
                self._particle_vy[outside] *= -0.5
        else:
            out_x = np.abs(px_new) > Lx / 2
            out_y = np.abs(py_new) > Ly / 2
            px_new = np.clip(px_new, -Lx / 2, Lx / 2)
            py_new = np.clip(py_new, -Ly / 2, Ly / 2)
            self._particle_vx[out_x] *= -0.5
            self._particle_vy[out_y] *= -0.5

        self._particles[:, 0] = px_new
        self._particles[:, 1] = py_new
        return self._particles

    @property
    def particles(self):
        return self._particles

    def get_grid_coords(self, Lx, Ly, geometry="Quadrada"):
        """Return (X, Y) grids in physical coordinates."""
        if geometry == "Circular":
            R = Lx / 2.0
            return self.X_circ * 2.0 * R, self.Y_circ * 2.0 * R
        else:
            return self.X_norm * Lx, self.Y_norm * Ly
