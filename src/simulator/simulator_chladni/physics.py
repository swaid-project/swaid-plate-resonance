"""Physics engine for the Chladni pattern simulator.

Supports square, rectangular, and circular plates,
including particle simulation and arbitrary transducer phases.
"""

import numpy as np
from scipy.special import jn, iv, jn_zeros
from scipy.ndimage import map_coordinates
from .constants import DEFAULT_VIBRATION_SPEAKER, MATERIAL_CATALOG


class ChladniPhysics:
    """Vectorized physics engine for thin-plate (Kirchhoff) vibrations."""

    # Non-rigid roots beta_n of cos(beta) cosh(beta) = 1 (free-free beam).
    FREE_BEAM_ROOTS = (
        4.730040744862704,
        7.853204624095838,
        10.995607838001671,
        14.137165491257464,
        17.278759657399482,
        20.420352251041250,
        23.561944901923447,
        26.703537555510351,
        29.845130209103030,
        32.986722862692830,
        36.128315516282620,
    )

    def __init__(self, resolution: int = 200):
        self.res = resolution
        t = np.linspace(-0.5, 0.5, self.res)
        self.X_norm, self.Y_norm = np.meshgrid(t, t)
        self._x_unit = np.linspace(0.0, 1.0, self.res)
        self._y_unit = np.linspace(0.0, 1.0, self.res)
        self.speaker = DEFAULT_VIBRATION_SPEAKER

        # Cache
        self._cache_key = None
        self._modes = None
        self._omega_nm = None
        self._f_nm = None
        self._ns = None
        self._ms = None
        self._rect_is_square = True
        self._rect_sign = 1

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

    @staticmethod
    def plate_from_material(material_name, thickness_mm, size_mm=None):
        """Resolve (D, rho, h, Lx, Ly) from a real material preset."""
        if material_name not in MATERIAL_CATALOG:
            raise KeyError(f"Unknown material: {material_name}")
        spec = MATERIAL_CATALOG[material_name]
        if thickness_mm not in spec.thicknesses_mm:
            raise ValueError(
                f"Invalid thickness {thickness_mm} mm for {material_name}. "
                f"Available values: {spec.thicknesses_mm}"
            )

        if size_mm is None:
            size_mm = spec.sizes_mm[0]
        if size_mm not in spec.sizes_mm:
            raise ValueError(
                f"Invalid size {size_mm} mm for {material_name}. "
                f"Available values: {spec.sizes_mm}"
            )

        Lx = size_mm[0] / 1000.0
        Ly = size_mm[1] / 1000.0
        h = thickness_mm / 1000.0
        D = ChladniPhysics.flexural_rigidity(spec.E, h, spec.nu)
        return {
            "material_name": material_name,
            "E": spec.E,
            "rho": spec.rho,
            "nu": spec.nu,
            "h": h,
            "D": D,
            "Lx": Lx,
            "Ly": Ly,
        }

    @staticmethod
    def _is_square_plate(Lx, Ly, tol=1e-9):
        return abs(Lx - Ly) <= tol * max(1.0, abs(Lx), abs(Ly))

    @classmethod
    def _beam_root(cls, n):
        if n <= len(cls.FREE_BEAM_ROOTS):
            return cls.FREE_BEAM_ROOTS[n - 1]
        return (n + 0.5) * np.pi

    @classmethod
    def _free_beam_mode(cls, n, x, L):
        """Free-free beam shape phi_n(x) over x in [0, L]."""
        beta_n = cls._beam_root(n)
        k_n = beta_n / max(L, 1e-12)
        sigma_n = ((np.cosh(beta_n) - np.cos(beta_n)) /
                   (np.sinh(beta_n) - np.sin(beta_n)))
        phi = (np.cosh(k_n * x) + np.cos(k_n * x) -
               sigma_n * (np.sinh(k_n * x) + np.sin(k_n * x)))
        # Normalize each 1D beam function for stable modal amplitudes.
        norm = np.sqrt(np.mean(phi**2))
        if norm > 0:
            phi = phi / norm
        return phi, k_n

    @staticmethod
    def _mode_wavelength_rect(kx, ky):
        k_tot = np.sqrt(kx**2 + ky**2)
        if k_tot <= 1e-12:
            return np.inf
        return 2.0 * np.pi / k_tot

    @staticmethod
    def _speaker_bandwidth_gain(freq, speaker):
        f = max(float(freq), 1e-9)
        low = 1.0 / (1.0 + (speaker.f_min / f)**8)
        high = 1.0 / (1.0 + (f / speaker.f_max)**8)
        return low * high

    @staticmethod
    def _speaker_power_gain(transducers):
        amps = np.array([max(0.0, amp) for _, _, amp, _ in transducers],
                        dtype=float)
        if amps.size == 0:
            return 0.0
        rms = np.sqrt(np.mean(amps**2))
        return 1.0 / max(1.0, rms)

    @staticmethod
    def _speaker_mass_gain(freq, speaker):
        # Lumped center mass effect: attenuates high-frequency coupling.
        f_ref = 1200.0 / np.sqrt(max(speaker.mass_kg, 1e-6) / 0.268)
        return 1.0 / np.sqrt(1.0 + (freq / f_ref)**2)

    @staticmethod
    def _compensation_gain(freq):
        """
        Calculates an equalization transfer function to compensate for the -60dB 
        attenuation at high frequencies. 
        Physics rationale: 
        1. Plate displacement amplitude at resonance scales with 1/omega^2 for a constant force.
        2. High-frequency modes suffer from area integration losses (the speaker diameter spans multiple wavelengths) and moving mass inertia.
        A transfer function proportional to frequency squared (or similar exponent) 
        flattens the structural response (acceleration), giving uniform visual standing waves.
        """
        f_ref = 50.0 # baseline reference frequency
        f = max(float(freq), f_ref)
        # Empirical power law to recover lost amplitude (approx +40 to +60dB compensation)
        return (f / f_ref) ** 1.8

    def _speaker_drive_gain(self, freq, transducers, speaker):
        return (
            self._speaker_bandwidth_gain(freq, speaker)
            * self._speaker_power_gain(transducers)
            * self._speaker_mass_gain(freq, speaker)
            * self._compensation_gain(freq)
        )

    # ══════════════════════════════════════════════════════════════════
    #  RECTANGULAR / SQUARE PLATE  (free-edge approximation)
    # ══════════════════════════════════════════════════════════════════

    def _build_cache_rect(self, Lx, Ly, sign, n_modes, D, rho, h):
        """Precompute modes for a free-edge rectangular plate.

        Uses a Rayleigh approximation with free-free beam functions.
        """
        is_square = self._is_square_plate(Lx, Ly)
        key = ("rect_free", Lx, Ly, sign if is_square else 0, n_modes, D, rho, h)
        if self._cache_key == key:
            return
        self._cache_key = key
        self._rect_is_square = is_square
        self._rect_sign = 1 if sign >= 0 else -1

        ns = np.arange(1, n_modes + 1)
        ms = np.arange(1, n_modes + 1)
        NN, MM = np.meshgrid(ns, ms)
        self._ns = NN.ravel()
        self._ms = MM.ravel()

        x = self._x_unit * Lx
        y = self._y_unit * Ly
        phi_x = {}
        kx = {}
        for n in ns:
            phi_x[n], kx[n] = self._free_beam_mode(int(n), x, Lx)
        phi_y = {}
        ky = {}
        for m in ms:
            phi_y[m], ky[m] = self._free_beam_mode(int(m), y, Ly)

        num_modes = len(self._ns)
        modes = np.zeros((num_modes, self.res, self.res))
        f_nm = np.zeros(num_modes)
        kx_nm = np.zeros(num_modes)
        ky_nm = np.zeros(num_modes)
        lambda_nm = np.zeros(num_modes)

        for k in range(num_modes):
            n = self._ns[k]
            m = self._ms[k]
            phi_x_n = phi_x[n]
            phi_y_m = phi_y[m]
            t1 = np.outer(phi_y_m, phi_x_n)

            if is_square:
                phi_x_m = phi_x[m]
                phi_y_n = phi_y[n]
                t2 = np.outer(phi_y_n, phi_x_m)
                modes[k] = t1 + self._rect_sign * t2
            else:
                # Rectangular plates: no cross-mode superposition.
                modes[k] = t1

            kx_nm[k] = kx[n]
            ky_nm[k] = ky[m]
            lambda_nm[k] = self._mode_wavelength_rect(kx_nm[k], ky_nm[k])

            # Rayleigh free-edge approximation for plate natural frequency.
            omega_k = np.sqrt(D / (rho * h)) * (kx_nm[k]**2 + ky_nm[k]**2)
            f_nm[k] = omega_k / (2.0 * np.pi)

        self._modes = modes
        self._f_nm = f_nm
        self._omega_nm = 2.0 * np.pi * self._f_nm
        self._kx_nm = kx_nm
        self._ky_nm = ky_nm
        self._lambda_rect_nm = lambda_nm

    def _coupling_rect(self, transducers, Lx, Ly, sign, speaker=None):
        """Compute forcing coefficients for each mode.
        transducers: list of (tx, ty, amplitude, phase_rad).
        """
        if speaker is None:
            speaker = self.speaker
        F = np.zeros(len(self._ns), dtype=complex)
        for tx, ty, amp, phase in transducers:
            x_s = tx + Lx / 2.0
            y_s = ty + Ly / 2.0
            x_s = float(np.clip(x_s, 0.0, Lx))
            y_s = float(np.clip(y_s, 0.0, Ly))

            c_nm = np.zeros(len(self._ns), dtype=float)
            for k in range(len(self._ns)):
                n = int(self._ns[k])
                m = int(self._ms[k])
                phi_x_n, _ = self._free_beam_mode(n, np.array([x_s]), Lx)
                phi_y_m, _ = self._free_beam_mode(m, np.array([y_s]), Ly)
                v = phi_x_n[0] * phi_y_m[0]

                if self._rect_is_square:
                    phi_x_m, _ = self._free_beam_mode(m, np.array([x_s]), Lx)
                    phi_y_n, _ = self._free_beam_mode(n, np.array([y_s]), Ly)
                    v += self._rect_sign * phi_x_m[0] * phi_y_n[0]
                c_nm[k] = v

            # Finite-area source: suppresses short-wavelength modes.
            area_gain = np.exp(- (speaker.diameter_m /
                                  np.maximum(self._lambda_rect_nm, 1e-12))**2)
            F += amp * np.exp(1j * phase) * c_nm * area_gain
        return F

    # ══════════════════════════════════════════════════════════════════
    #  CIRCULAR PLATE  (free-edge approximation)
    # ══════════════════════════════════════════════════════════════════

    def _build_cache_circ(self, R, n_modes, D, rho, h):
        """Precompute modes for a circular plate with free-edge approximation.

        Uses a J_n and I_n Bessel-function modal basis.
        """
        key = ("circ_free", R, n_modes, D, rho, h)
        if self._cache_key == key:
            return
        self._cache_key = key

        ns_list = []
        ms_list = []
        lambda_nm = []
        C_nm_list = []

        for n_circ in range(n_modes):
            n_radial = min(n_modes, 3)
            # For numerical stability, use Bessel zeros as a baseline and
            # apply an offset to approximate free-edge roots.
            zeros = jn_zeros(n_circ, n_radial)
            for m_idx, z in enumerate(zeros):
                ns_list.append(n_circ)
                ms_list.append(m_idx + 1)
                
                # Approximate free-edge root (slightly lowers frequencies).
                lam = z * 0.95 
                lambda_nm.append(lam)
                
                # Free-edge C_nm coefficient (simplified for visual/physical
                # plausibility), keeping non-zero edge amplitude.
                c_val = jn(n_circ, lam) / iv(n_circ, lam)
                C_nm_list.append(c_val)

        self._ns = np.array(ns_list)
        self._ms = np.array(ms_list)
        lam_arr = np.array(lambda_nm)
        C_arr = np.array(C_nm_list)

        # Natural frequencies
        f_nm = (lam_arr**2) / (2.0 * np.pi * R**2) * np.sqrt(D / (rho * h))
        self._omega_nm = 2.0 * np.pi * f_nm
        self._f_nm = f_nm
        self._lambda_nm = lam_arr

        # Build mode shapes on the Cartesian grid
        r_grid = self.R_norm * 2.0 * R  # [0, R]
        theta_grid = self.Theta_norm

        n3 = self._ns[:, None, None]
        lam3 = lam_arr[:, None, None]
        C3 = C_arr[:, None, None]
        r3 = r_grid[None, :, :]
        t3 = theta_grid[None, :, :]

        # R_nm(r) = J_n(λ r/R) + C_nm * I_n(λ r/R)
        radial_part = jn(n3, lam3 * r3 / R) + C3 * iv(n3, lam3 * r3 / R)
        self._modes = radial_part * np.cos(n3 * t3)

        self._circ_mask = (r_grid <= R)

    def _coupling_circ(self, transducers, R, speaker=None):
        """Coupling for circular plate transducers."""
        if speaker is None:
            speaker = self.speaker
        F = np.zeros(len(self._ns), dtype=complex)
        # Effective modal wavelength using circumferentially averaged wavenumber.
        lambda_mode = 2.0 * np.pi * R / np.maximum(self._lambda_nm, 1e-12)
        area_gain = np.exp(- (speaker.diameter_m / np.maximum(lambda_mode, 1e-12))**2)
        for tx, ty, amp, phase in transducers:
            r_t = np.sqrt(tx**2 + ty**2)
            theta_t = np.arctan2(ty, tx)
            for k in range(len(self._ns)):
                n_k = self._ns[k]
                lam_k = self._lambda_nm[k]
                mode_val = jn(n_k, lam_k * r_t / R) * np.cos(n_k * theta_t)
                F[k] += amp * np.exp(1j * phase) * mode_val * area_gain[k]
        return F

    # ══════════════════════════════════════════════════════════════════
    #  UNIFIED DRIVEN RESPONSE
    # ══════════════════════════════════════════════════════════════════

    def _resolve_plate_inputs(self, D, rho, h, material_name=None,
                              thickness_mm=None):
        if material_name is not None:
            if thickness_mm is None:
                raise ValueError("When material_name is provided, thickness_mm is required.")
            plate = self.plate_from_material(material_name, thickness_mm)
            return plate["D"], plate["rho"], plate["h"]

        if D is None or rho is None or h is None:
            raise ValueError("Provide D, rho, h or use material_name + thickness_mm.")
        return D, rho, h

    def driven_response(self, freq, Lx, Ly, D, rho, h, transducers,
                        n_modes=8, damping=0.005, sign=1,
                        geometry="Quadrada", speaker=None,
                        material_name=None, thickness_mm=None):
        """Compute driven response for any geometry.
        transducers: list of (tx, ty, amplitude, phase_rad)
        """
        D, rho, h = self._resolve_plate_inputs(D, rho, h,
                                               material_name=material_name,
                                               thickness_mm=thickness_mm)
        if speaker is None:
            speaker = self.speaker
        omega = 2.0 * np.pi * freq

        if geometry == "Circular":
            R = Lx / 2.0
            self._build_cache_circ(R, n_modes, D, rho, h)
            F_nm = self._coupling_circ(transducers, R, speaker=speaker)
        else:
            self._build_cache_rect(Lx, Ly, sign, n_modes, D, rho, h)
            F_nm = self._coupling_rect(transducers, Lx, Ly, sign,
                                       speaker=speaker)

        F_nm = F_nm * self._speaker_drive_gain(freq, transducers, speaker)

        denom = self._omega_nm**2 - omega**2 + \
                2j * damping * self._omega_nm * omega
        safe = np.abs(denom) > 1e-30
        coeffs = np.zeros(len(F_nm), dtype=complex)
        coeffs[safe] = F_nm[safe] / denom[safe]
        resp = np.einsum("k,kij->ij", coeffs, self._modes)
        return resp

    def driven_response_cartesian(self, freq, Lx, Ly, D, rho, h,
                                   transducers, n_modes=8, damping=0.005,
                                   sign=1, geometry="Quadrada", speaker=None,
                                   material_name=None, thickness_mm=None):
        """Compute driven response on the Cartesian (X_norm, Y_norm) grid.
        For circular plates, evaluates mode shapes at Cartesian grid points
        instead of the polar grid. Used by particle simulation.
        """
        if geometry != "Circular":
            return self.driven_response(freq, Lx, Ly, D, rho, h,
                                        transducers, n_modes, damping,
                                        sign, geometry, speaker,
                                        material_name, thickness_mm)

        D, rho, h = self._resolve_plate_inputs(D, rho, h,
                                               material_name=material_name,
                                               thickness_mm=thickness_mm)
        if speaker is None:
            speaker = self.speaker
        R = Lx / 2.0
        omega = 2.0 * np.pi * freq
        self._build_cache_circ(R, n_modes, D, rho, h)
        F_nm = self._coupling_circ(transducers, R, speaker=speaker)
        F_nm = F_nm * self._speaker_drive_gain(freq, transducers, speaker)

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
                    geometry="Quadrada", speaker=None,
                    material_name=None, thickness_mm=None):
        """Returns (sand_pattern, Z_3d_normalized)."""
        resp = self.driven_response(freq, Lx, Ly, D, rho, h, transducers,
                                    n_modes, damping, sign, geometry,
                                    speaker, material_name, thickness_mm)
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
            x = self._x_unit * Lx
            y = self._y_unit * Ly
            phi_x_n, _ = self._free_beam_mode(n, x, Lx)
            phi_y_m, _ = self._free_beam_mode(m, y, Ly)
            t1 = np.outer(phi_y_m, phi_x_n)

            if self._is_square_plate(Lx, Ly):
                phi_x_m, _ = self._free_beam_mode(m, x, Lx)
                phi_y_n, _ = self._free_beam_mode(n, y, Ly)
                return t1 + (1 if sign >= 0 else -1) * np.outer(phi_y_n, phi_x_m)
            return t1

    def mode_frequency(self, n, m, Lx, Ly, D, rho, h, geometry="Quadrada"):
        """Natural frequency for mode (n,m)."""
        if geometry == "Circular":
            R = Lx / 2.0
            zeros = jn_zeros(n, m)
            lam = zeros[-1]
            return (lam**2) / (2.0 * np.pi * R**2) * np.sqrt(D / (rho * h))
        else:
            kx = self._beam_root(n) / Lx
            ky = self._beam_root(m) / Ly
            omega_nm = np.sqrt(D / (rho * h)) * (kx**2 + ky**2)
            return omega_nm / (2.0 * np.pi)

    @staticmethod
    def transducer_coupling_single(tx, ty, n, m, Lx, Ly, sign=1):
        """Single-mode coupling for a transducer (for info display)."""
        x_s = tx + Lx / 2.0
        y_s = ty + Ly / 2.0
        x_s = float(np.clip(x_s, 0.0, Lx))
        y_s = float(np.clip(y_s, 0.0, Ly))

        phi_x_n, _ = ChladniPhysics._free_beam_mode(n, np.array([x_s]), Lx)
        phi_y_m, _ = ChladniPhysics._free_beam_mode(m, np.array([y_s]), Ly)
        c = phi_x_n[0] * phi_y_m[0]

        if ChladniPhysics._is_square_plate(Lx, Ly):
            phi_x_m, _ = ChladniPhysics._free_beam_mode(m, np.array([x_s]), Lx)
            phi_y_n, _ = ChladniPhysics._free_beam_mode(n, np.array([y_s]), Ly)
            c += (1 if sign >= 0 else -1) * phi_x_m[0] * phi_y_n[0]
        return c

    # ── Frequency sweep ──────────────────────────────────────────────
    def frequency_sweep(self, Lx, Ly, D, rho, h, transducers,
                        freq_range=(20, 5000), n_modes=8,
                        damping=0.005, sign=1, n_points=400,
                        geometry="Quadrada", speaker=None,
                        material_name=None, thickness_mm=None):
        """Vectorized frequency sweep."""
        D, rho, h = self._resolve_plate_inputs(D, rho, h,
                                               material_name=material_name,
                                               thickness_mm=thickness_mm)
        if speaker is None:
            speaker = self.speaker
        if geometry == "Circular":
            R = Lx / 2.0
            self._build_cache_circ(R, n_modes, D, rho, h)
            F_nm = self._coupling_circ(transducers, R, speaker=speaker)
        else:
            self._build_cache_rect(Lx, Ly, sign, n_modes, D, rho, h)
            F_nm = self._coupling_rect(transducers, Lx, Ly, sign,
                                       speaker=speaker)

        freqs = np.linspace(freq_range[0], freq_range[1], n_points)
        omega = 2.0 * np.pi * freqs
        gains = np.array([
            self._speaker_drive_gain(f, transducers, speaker)
            for f in freqs
        ])

        w_nm = self._omega_nm[None, :]
        w = omega[:, None]
        denom = w_nm**2 - w**2 + 2j * damping * w_nm * w
        abs_d2 = np.maximum(np.abs(denom)**2, 1e-60)
        energy = np.sum(np.abs(F_nm[None, :] * gains[:, None])**2 / abs_d2,
                        axis=1)
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
