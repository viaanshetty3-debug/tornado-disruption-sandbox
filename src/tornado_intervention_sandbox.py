"""
Tornado Intervention Sandbox
============================

A modular 3D simulation sandbox for comparing three proposed (and highly
speculative) tornado disruption methods against a common baseline vortex:

  1. Microwave beaming    - heat the cold rear-flank downdraft (RFD) to erase
                            the thermal contrast that generates baroclinic
                            vorticity along the gust front.
  2. Polymer desiccation  - dump a heavy water-absorbing gel into the updraft,
                            loading it with mass so gravity drags it down and
                            centrifugal force flings it outward.
  3. Cryogenic cooling    - chill the warm, moist low-level inflow layer to
                            kill the positive buoyancy feeding the updraft.

Physics basis
-------------
The velocity field is a Burgers-Rott vortex (tangential swirl with a
boundary-layer jet profile, radial convergence, and a vertically stretching
updraft). On top of that sit a temperature field T(x, y, z) and a density
field rho(x, y, z), coupled to the vertical momentum through the buoyancy
acceleration

    w_accel = g * (T_local - T_ambient) / T_ambient

and to horizontal vorticity through the baroclinic generation term, which for
a horizontal buoyancy gradient reduces to the curl of the buoyancy field.

IMPORTANT - scope and honesty about the model
---------------------------------------------
This is a *comparative sandbox*, not a forecast model. It is diagnostic and
steady-state: an intervention perturbs T / rho / mass loading, and the code
re-derives the resulting buoyancy, updraft, and vorticity fields analytically.
There is no time integration, no moist thermodynamics, no pressure solver, and
no turbulence closure. The numbers it prints are internally consistent
comparisons between the three methods under identical assumptions - they are
NOT predictions of real-world efficacy. The real-world verdict for all three
methods is "energetically absurd," and the feasibility scoring below is
deliberately built to surface that rather than hide it.
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")  # headless rendering; must precede pyplot import
import matplotlib.pyplot as plt

from pathlib import Path

# Generated figures are written to the repository's output/ folder
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


# ======================================================================
# Physical constants and tunable parameters
# ======================================================================

G = 9.81                  # Gravitational acceleration (m/s^2)
CP_AIR = 1005.0           # Specific heat of air at constant pressure (J/kg/K)
RHO_AIR = 1.225           # Reference air density at sea level (kg/m^3)
T_AMBIENT = 293.0         # Ambient reference temperature (K, ~20 C)

# --- Vortex structure (Burgers-Rott) ---
GAMMA = 8000.0            # Reference circulation strength (m^2/s)
RC0 = 15.0                # Core radius at the surface (m)
FUNNEL_WIDENING = 0.8     # Fractional core-radius growth surface -> domain top
BL_PEAK_HEIGHT = 40.0     # Altitude of peak tangential wind (m)
ALPHA = 0.03              # Burgers vertical-stretching rate (1/s)
CORE_CENTER_XY = (0.0, 0.0)

# --- Domain ---
DOMAIN_HALF_WIDTH = 300.0   # Horizontal half-span (m)
DOMAIN_HEIGHT = 1000.0      # Vertical extent, surface -> cloud base (m)
NX, NY, NZ = 48, 48, 32

# --- Thermodynamic structure ---
INFLOW_EXCESS_K = 4.0       # Warm moist inflow, K above ambient
RFD_DEFICIT_K = -6.0        # Cold rear-flank downdraft, K below ambient
INFLOW_TOP_M = 250.0        # Depth of the warm inflow layer (m)
RFD_CENTER = (-120.0, 0.0)  # (x, y) center of the RFD cold pool
RFD_RADIUS = 110.0          # Horizontal scale of the RFD cold pool (m)
INFLOW_CENTER_X = 150.0     # Inflow air arrives from +x side

# --- Intervention defaults ---
MICROWAVE_GIGAWATTS = 10.0
POLYMER_MASS_KG = 100_000.0
CRYO_DELTA_K = -50.0
INTERVENTION_DURATION_S = 600.0   # 10-minute engagement window for all methods


# ======================================================================
# 1. Base physics framework
# ======================================================================

def build_grid():
    """Create the 3D coordinate grid and cell spacings."""
    x = np.linspace(-DOMAIN_HALF_WIDTH, DOMAIN_HALF_WIDTH, NX)
    y = np.linspace(-DOMAIN_HALF_WIDTH, DOMAIN_HALF_WIDTH, NY)
    z = np.linspace(0.0, DOMAIN_HEIGHT, NZ)
    X, Y, Z = np.meshgrid(x, y, z, indexing="ij")
    return X, Y, Z, x[1] - x[0], y[1] - y[0], z[1] - z[0]


def core_radius_profile(Z):
    """Core radius grows with altitude - the funnel flare."""
    return RC0 * (1.0 + FUNNEL_WIDENING * (Z / DOMAIN_HEIGHT))


def boundary_layer_profile(Z):
    """Tangential-wind height scaling: zero at surface, peak in the BL jet."""
    z_safe = np.maximum(Z, 1e-6)
    return (z_safe / BL_PEAK_HEIGHT) * np.exp(1.0 - z_safe / BL_PEAK_HEIGHT)


def build_velocity_field(X, Y, Z):
    """Burgers-Rott velocity field (u, v, w) - the dynamical baseline."""
    x0, y0 = CORE_CENTER_XY
    dx, dy = X - x0, Y - y0
    r = np.hypot(dx, dy)
    r_safe = np.where(r < 1e-6, 1e-6, r)
    theta = np.arctan2(dy, dx)

    rc_z = core_radius_profile(Z)
    v_theta = (GAMMA / (2.0 * np.pi * r_safe)) * (1.0 - np.exp(-(r_safe ** 2) / rc_z ** 2)) \
        * boundary_layer_profile(Z)
    v_r = -(ALPHA * r_safe / 2.0) * np.exp(-Z / (2.0 * BL_PEAK_HEIGHT))

    u = v_r * np.cos(theta) - v_theta * np.sin(theta)
    v = v_r * np.sin(theta) + v_theta * np.cos(theta)
    w = ALPHA * Z * np.exp(-(r_safe ** 2) / rc_z ** 2)

    u = np.where(r < 1e-6, 0.0, u)
    v = np.where(r < 1e-6, 0.0, v)
    return u, v, w


def build_temperature_field(X, Y, Z):
    """
    Temperature field T(x, y, z) with the two features that matter for
    tornadogenesis: a warm moist inflow layer at low altitude on the +x side,
    and a cold rear-flank downdraft (RFD) pool on the -x side. The horizontal
    boundary between them is the baroclinic zone.
    """
    T = np.full_like(X, T_AMBIENT)

    # Warm, moist inflow: shallow layer, strongest at low altitude on +x side
    inflow_shape = np.exp(-((X - INFLOW_CENTER_X) ** 2) / (2.0 * 150.0 ** 2)) \
        * np.exp(-Z / INFLOW_TOP_M)
    T += INFLOW_EXCESS_K * inflow_shape

    # Cold RFD pool: dense surface-based cold air on the -x side
    rfd_dist_sq = (X - RFD_CENTER[0]) ** 2 + (Y - RFD_CENTER[1]) ** 2
    rfd_shape = np.exp(-rfd_dist_sq / (2.0 * RFD_RADIUS ** 2)) * np.exp(-Z / 200.0)
    T += RFD_DEFICIT_K * rfd_shape

    return T


def density_from_temperature(T, mass_loading=None):
    """
    Air density from the ideal gas law at constant pressure: rho ~ 1/T.
    Optional `mass_loading` (kg/m^3) adds suspended condensate/polymer mass.
    """
    rho = RHO_AIR * (T_AMBIENT / T)
    if mass_loading is not None:
        rho = rho + mass_loading
    return rho


def buoyancy_acceleration(T, mass_loading=None):
    """
    Vertical buoyancy acceleration:

        w_accel = g * (T_local - T_ambient) / T_ambient

    Suspended mass loading acts as negative buoyancy (the classic water-loading
    term): it subtracts g * (rho_load / rho_air) from the acceleration.
    """
    accel = G * (T - T_AMBIENT) / T_AMBIENT
    if mass_loading is not None:
        accel = accel - G * (mass_loading / RHO_AIR)
    return accel


def equilibrium_updraft(w_base, buoy, dz):
    """
    Re-derive the updraft from the buoyancy field.

    Steady-state parcel energetics: a parcel rising through a buoyancy field
    accumulates kinetic energy w^2/2 = integral(B dz). We integrate buoyancy
    upward to get the buoyancy-driven updraft, then blend it with the
    dynamically-forced (vortex stretching) updraft w_base, which persists even
    with zero buoyancy. Negative integrated buoyancy suppresses the updraft.
    """
    # Cumulative buoyancy work from the surface upward, along the z axis
    work = np.cumsum(buoy, axis=2) * dz
    w_buoy = np.sign(work) * np.sqrt(2.0 * np.abs(work))

    # Dynamic (stretching) and thermodynamic (buoyant) contributions combine;
    # clip at zero since a net-negative column cannot sustain an updraft.
    return np.maximum(w_base + w_buoy, 0.0)


def vorticity_3d(u, v, w, dx, dy, dz):
    """Full 3D vorticity vector (curl of velocity)."""
    dudy = np.gradient(u, dy, axis=1)
    dudz = np.gradient(u, dz, axis=2)
    dvdx = np.gradient(v, dx, axis=0)
    dvdz = np.gradient(v, dz, axis=2)
    dwdx = np.gradient(w, dx, axis=0)
    dwdy = np.gradient(w, dy, axis=1)
    return (dwdy - dvdz, dudz - dwdx, dvdx - dudy)


def baroclinic_generation(buoy, dx, dy):
    """
    Baroclinic vorticity generation rate = curl of the buoyancy field.

    For a buoyancy B acting in the vertical, horizontal gradients of B tilt
    into horizontal vorticity at rate:
        d(omega_x)/dt =  dB/dy
        d(omega_y)/dt = -dB/dx
    Returns the magnitude of that generation vector (1/s^2). This is the term
    that builds the horizontal vorticity later tilted upright into the tornado.
    """
    dBdx = np.gradient(buoy, dx, axis=0)
    dBdy = np.gradient(buoy, dy, axis=1)
    return np.sqrt(dBdx ** 2 + dBdy ** 2)


def kinetic_energy(u, v, w, rho, dx, dy, dz):
    """Volumetric kinetic energy: KE = integral(0.5 * rho * |V|^2) dV, in joules."""
    return float(np.sum(0.5 * rho * (u ** 2 + v ** 2 + w ** 2)) * dx * dy * dz)


class TornadoState:
    """
    Container bundling every field describing one scenario, plus the derived
    diagnostics. Interventions consume a state and return a NEW state, so the
    baseline is never mutated and methods can be compared independently.
    """

    def __init__(self, X, Y, Z, dx, dy, dz, T, mass_loading=None,
                 u=None, v=None, w_base=None, label="Base Tornado", notes=""):
        self.X, self.Y, self.Z = X, Y, Z
        self.dx, self.dy, self.dz = dx, dy, dz
        self.label = label
        self.notes = notes

        if u is None:
            u, v, w_base = build_velocity_field(X, Y, Z)
        self.u, self.v, self.w_base = u, v, w_base

        self.T = T
        self.mass_loading = mass_loading

        # Derived thermodynamic / dynamic fields
        self.rho = density_from_temperature(T, mass_loading)
        self.buoyancy = buoyancy_acceleration(T, mass_loading)
        self.w = equilibrium_updraft(w_base, self.buoyancy, dz)
        self.omega = vorticity_3d(self.u, self.v, self.w, dx, dy, dz)
        self.baroclinic = baroclinic_generation(self.buoyancy, dx, dy)

    # --- Scalar diagnostics -------------------------------------------
    @property
    def peak_updraft(self):
        return float(np.max(self.w))

    @property
    def total_vorticity(self):
        ox, oy, oz = self.omega
        return float(np.mean(np.sqrt(ox ** 2 + oy ** 2 + oz ** 2)))

    @property
    def mean_baroclinic(self):
        return float(np.mean(self.baroclinic))

    @property
    def kinetic_energy(self):
        return kinetic_energy(self.u, self.v, self.w, self.rho,
                              self.dx, self.dy, self.dz)

    def derive(self, T=None, mass_loading=None, u=None, v=None, w_base=None,
               label=None, notes=""):
        """
        Produce a new state with selected fields replaced.

        `w_base` is the dynamically-forced (vortex-stretching) updraft, kept
        separate from the buoyancy-driven part. Thermodynamic interventions
        leave it alone; interventions that act on the *dynamics* - surface
        drag, momentum injection - override it, since throttling the radial
        inflow throttles the stretching that drives it.
        """
        return TornadoState(
            self.X, self.Y, self.Z, self.dx, self.dy, self.dz,
            T=self.T if T is None else T,
            mass_loading=self.mass_loading if mass_loading is None else mass_loading,
            u=self.u if u is None else u,
            v=self.v if v is None else v,
            w_base=self.w_base if w_base is None else w_base,
            label=label or self.label,
            notes=notes,
        )


# ======================================================================
# Target-zone masks
# ======================================================================

def zone_mask(X, Y, Z, target_zone):
    """
    Return a smooth [0, 1] weighting field selecting a named region.

    'RFD'     - the cold rear-flank downdraft pool (-x side, surface-based)
    'updraft' - the rotating core column that carries the updraft
    'inflow'  - the warm moist low-level inflow layer (+x side, shallow)
    """
    if target_zone == "RFD":
        dist_sq = (X - RFD_CENTER[0]) ** 2 + (Y - RFD_CENTER[1]) ** 2
        return np.exp(-dist_sq / (2.0 * RFD_RADIUS ** 2)) * np.exp(-Z / 200.0)

    if target_zone == "updraft":
        r_sq = (X - CORE_CENTER_XY[0]) ** 2 + (Y - CORE_CENTER_XY[1]) ** 2
        rc_z = core_radius_profile(Z)
        # Slightly wider than the core so the payload envelops the updraft
        return np.exp(-r_sq / (2.0 * (1.8 * rc_z) ** 2))

    if target_zone == "inflow":
        return np.exp(-((X - INFLOW_CENTER_X) ** 2) / (2.0 * 150.0 ** 2)) \
            * np.exp(-Z / INFLOW_TOP_M)

    raise ValueError(f"Unknown target_zone: {target_zone!r} "
                     "(expected 'RFD', 'updraft', or 'inflow')")


def zone_air_mass(state, mask):
    """Total mass of air (kg) contained in a weighted target zone."""
    cell_volume = state.dx * state.dy * state.dz
    return float(np.sum(mask * state.rho) * cell_volume)


# ======================================================================
# 2. Intervention modules
# ======================================================================

def run_microwave_beaming(state, target_zone="RFD", energy_gigawatts=MICROWAVE_GIGAWATTS,
                          duration_s=INTERVENTION_DURATION_S):
    """
    (a) MICROWAVE BEAMING

    Beam microwave energy into the cold rear-flank downdraft to warm it toward
    ambient, erasing the thermal contrast across the gust front. Because
    baroclinic vorticity generation is the curl of buoyancy, flattening the
    horizontal temperature gradient directly cuts the vorticity source term.

    Heating is computed from real energy: dT = E / (m_air * cp), where E is the
    beamed energy over the engagement window and m_air is the air mass in the
    target zone. Warming is clipped so the RFD can be neutralized to ambient
    but not overshoot into a spurious warm anomaly.
    """
    mask = zone_mask(state.X, state.Y, state.Z, target_zone)
    energy_j = energy_gigawatts * 1e9 * duration_s
    air_mass = zone_air_mass(state, mask)

    # Uniform-in-zone temperature rise from the deposited energy
    dT_available = energy_j / (air_mass * CP_AIR)
    delta_T = mask * dT_available

    # Cap warming at the local cold deficit: the goal is to reach ambient,
    # not to build an artificial warm bubble.
    deficit = np.maximum(T_AMBIENT - state.T, 0.0)
    delta_T = np.minimum(delta_T, deficit)

    T_new = state.T + delta_T
    notes = (f"{energy_gigawatts:.1f} GW x {duration_s/60:.0f} min = "
             f"{energy_j/1e12:.1f} TJ into {air_mass/1e9:.2f} Mt of air; "
             f"available dT = {dT_available:.2f} K, applied max "
             f"{float(np.max(delta_T)):.2f} K")
    return state.derive(T=T_new, label="Microwave Beaming", notes=notes)


def run_polymer_desiccation(state, target_zone="updraft", payload_mass_kg=POLYMER_MASS_KG):
    """
    (b) POLYMER DESICCATION

    Disperse a superabsorbent polymer gel into the updraft. The payload adds
    suspended mass to the air, producing two effects:

      1. Gravitational drag  - the loaded parcels weigh more, so buoyancy drops
         by g * (rho_gel / rho_air). This is the water-loading term.
      2. Centrifugal dispersion - the vortex flings dense particles outward at
         a_c = v_theta^2 / r, so a large fraction of the payload leaves the core
         before it can do useful work. This is modeled as a retention factor.

    The centrifugal term is what makes this method structurally self-defeating:
    the stronger the vortex, the faster it ejects the payload meant to stop it.
    """
    mask = zone_mask(state.X, state.Y, state.Z, target_zone)
    cell_volume = state.dx * state.dy * state.dz

    # --- Centrifugal ejection: what fraction of the payload stays in the core?
    r = np.hypot(state.X - CORE_CENTER_XY[0], state.Y - CORE_CENTER_XY[1])
    r_safe = np.maximum(r, 1e-6)
    v_theta = np.hypot(state.u, state.v)
    a_centrifugal = v_theta ** 2 / r_safe

    # A parcel is retained where gravity/drag can hold it against the outward
    # centrifugal acceleration. Retention falls off as a_c exceeds g.
    retention = 1.0 / (1.0 + a_centrifugal / G)
    mean_retention = float(np.sum(retention * mask) / np.sum(mask))

    # --- Distribute the retained payload over the target zone
    zone_volume = float(np.sum(mask) * cell_volume)
    effective_mass = payload_mass_kg * mean_retention
    loading = (effective_mass / zone_volume) * mask * retention  # kg/m^3

    # --- Downward gravitational drag force from the retained payload
    drag_force_n = effective_mass * G  # F = -m_gel * g (magnitude, downward)

    notes = (f"{payload_mass_kg/1e3:.0f} t payload, centrifugal retention "
             f"{mean_retention*100:.1f}% -> {effective_mass/1e3:.1f} t effective; "
             f"drag F = {drag_force_n/1e6:.2f} MN; peak loading "
             f"{float(np.max(loading))*1e3:.3f} g/m^3")
    new_state = state.derive(mass_loading=loading, label="Polymer Desiccation", notes=notes)
    new_state.drag_force_n = drag_force_n
    new_state.retention = mean_retention
    return new_state


def run_cryogenic_cooling(state, target_zone="inflow", cooling_capacity_kelvin=CRYO_DELTA_K):
    """
    (c) CRYOGENIC COOLING

    Flood the warm, moist low-level inflow with cryogenic coolant to strip its
    positive buoyancy. The inflow layer is the tornado's fuel supply: chilling
    it below ambient turns buoyant fuel into dense, stable air that resists
    being lifted, directly cutting the buoyancy force B and the updraft w.

    `cooling_capacity_kelvin` is the peak temperature drop achievable at the
    heart of the treated zone (negative). The refrigeration energy required is
    reported for the feasibility comparison.
    """
    mask = zone_mask(state.X, state.Y, state.Z, target_zone)
    delta_T = cooling_capacity_kelvin * mask
    T_new = state.T + delta_T

    # Thermal energy that must be removed to achieve this cooling
    cell_volume = state.dx * state.dy * state.dz
    heat_removed_j = float(np.sum(np.abs(delta_T) * state.rho * CP_AIR) * cell_volume)

    notes = (f"peak dT = {cooling_capacity_kelvin:+.0f} K over the inflow layer; "
             f"heat extraction = {heat_removed_j/1e12:.1f} TJ "
             f"({heat_removed_j/INTERVENTION_DURATION_S/1e9:.1f} GW-equivalent)")
    new_state = state.derive(T=T_new, label="Cryogenic Cooling", notes=notes)
    new_state.heat_removed_j = heat_removed_j
    return new_state


# ======================================================================
# 3. Comparative benchmark
# ======================================================================

def energy_cost_joules(method_name, state):
    """
    Real energy/resource cost of each intervention, normalized to joules so the
    methods can be compared on one axis.

    Strategies defined outside this module report their own cost by setting an
    `energy_cost_j` attribute on the state they return; that always wins over
    the built-in dispatch below.
    """
    explicit = getattr(state, "energy_cost_j", None)
    if explicit is not None:
        return float(explicit)

    if method_name == "Microwave Beaming":
        return MICROWAVE_GIGAWATTS * 1e9 * INTERVENTION_DURATION_S
    if method_name == "Cryogenic Cooling":
        # Refrigeration is not free: apply a generous Carnot-ish COP of 3.
        return getattr(state, "heat_removed_j", 0.0) / 3.0
    if method_name == "Polymer Desiccation":
        # Manufacturing + lofting the payload to ~1 km, plus polymer embodied
        # energy (~100 MJ/t is optimistic for a superabsorbent polymer).
        lift = POLYMER_MASS_KG * G * DOMAIN_HEIGHT
        embodied = (POLYMER_MASS_KG / 1000.0) * 100e6
        return lift + embodied
    return 0.0


def feasibility_score(method_name, state, vort_reduction_pct):
    """
    Feasibility on a 0-10 scale (10 = trivially deployable today).

    Deliberately harsh and grounded in delivered energy: every one of these
    methods is many orders of magnitude short of practical, and the score is
    built to make that visible rather than to flatter the concepts. The score
    blends the energy cost against a reference (the ~10 TJ kinetic energy
    budget of a strong tornado) with the achieved vorticity reduction.
    """
    cost_j = energy_cost_joules(method_name, state)
    reference_j = 1e13  # ~10 TJ, order of a strong tornado's energy budget

    # Cost penalty: log-scaled, since costs span many decades
    cost_ratio = cost_j / reference_j
    cost_penalty = np.log10(max(cost_ratio, 1e-6)) + 6.0  # 0 at 1e-6x, 6 at 1x

    # Effectiveness reward
    effectiveness = np.clip(vort_reduction_pct / 10.0, 0.0, 5.0)

    score = np.clip(5.0 - cost_penalty * 0.8 + effectiveness, 0.0, 10.0)
    return float(score), cost_j


def resource_scale(method_name, state):
    """
    Human-readable statement of the resources the method demands. Externally
    defined strategies supply their own via a `resource_note` attribute.
    """
    explicit = getattr(state, "resource_note", None)
    if explicit is not None:
        return str(explicit)

    if method_name == "Microwave Beaming":
        gw = MICROWAVE_GIGAWATTS
        return f"{gw:.0f} GW beam ({gw/1.0:.0f}x a large nuclear reactor)"
    if method_name == "Polymer Desiccation":
        tonnes = POLYMER_MASS_KG / 1000.0
        c17_loads = tonnes / 77.0  # C-17 max payload ~77 t
        return f"{tonnes:.0f} t gel (~{c17_loads:.0f} C-17 sorties, airborne)"
    if method_name == "Cryogenic Cooling":
        heat = getattr(state, "heat_removed_j", 0.0)
        gw_equiv = heat / INTERVENTION_DURATION_S / 1e9 / 3.0
        return f"{gw_equiv:,.0f} GW refrigeration plant (COP 3)"
    return "n/a"


def fmt_energy(joules):
    """Adaptive energy formatting: pick GJ or TJ so small costs don't print as 0.0."""
    if joules >= 1e12:
        return f"{joules/1e12:.1f} TJ"
    return f"{joules/1e9:.1f} GJ"


def benchmark(base, results):
    """Print the comparative summary table."""
    print("=" * 108)
    print("TORNADO INTERVENTION COMPARATIVE BENCHMARK".center(108))
    print("=" * 108)
    print(f"Baseline vortex: peak updraft {base.peak_updraft:.2f} m/s | "
          f"mean vorticity {base.total_vorticity:.4f} 1/s | "
          f"KE {base.kinetic_energy/1e9:.2f} GJ")
    print(f"Engagement window: {INTERVENTION_DURATION_S/60:.0f} minutes | "
          f"Domain: {2*DOMAIN_HALF_WIDTH:.0f} x {2*DOMAIN_HALF_WIDTH:.0f} x {DOMAIN_HEIGHT:.0f} m")
    print("-" * 108)

    header = (f"{'Method':<22} {'Updraft Red.':>13} {'Vorticity Red.':>15} "
              f"{'Baroclinic Red.':>16} {'KE Loss (GJ)':>14} {'Feasibility':>12} {'Energy Cost':>12}")
    print(header)
    print("-" * 108)

    rows = []
    for state in results:
        updraft_red = 100.0 * (base.peak_updraft - state.peak_updraft) / base.peak_updraft
        vort_red = 100.0 * (base.total_vorticity - state.total_vorticity) / base.total_vorticity
        baro_red = 100.0 * (base.mean_baroclinic - state.mean_baroclinic) / base.mean_baroclinic
        ke_loss_gj = (base.kinetic_energy - state.kinetic_energy) / 1e9
        score, cost_j = feasibility_score(state.label, state, vort_red)

        print(f"{state.label:<22} {updraft_red:>12.2f}% {vort_red:>14.2f}% "
              f"{baro_red:>15.2f}% {ke_loss_gj:>14.2f} {score:>11.1f}/10 "
              f"{fmt_energy(cost_j):>12}")
        rows.append((state, updraft_red, vort_red, baro_red, ke_loss_gj, score, cost_j))

    print("-" * 108)
    print("\nRESOURCE SCALE REQUIRED")
    print("-" * 108)
    for state, *_ in rows:
        print(f"  {state.label:<22} {resource_scale(state.label, state)}")

    print("\nMETHOD NOTES")
    print("-" * 108)
    for state, *_ in rows:
        print(f"  {state.label}:\n    {state.notes}")

    print("\n" + "=" * 108)
    best = max(rows, key=lambda r: r[2])
    print(f"Largest vorticity reduction: {best[0].label} ({best[2]:.2f}%)")
    cheapest = min(rows, key=lambda r: r[6])
    print(f"Lowest energy cost:          {cheapest[0].label} ({fmt_energy(cheapest[6])})")
    print("\nREALITY CHECK: all three remain many orders of magnitude from practical.")
    print("A single supercell continuously reprocesses solar-scale energy; these")
    print("interventions perturb a steady-state diagnostic model, not a real storm.")
    print("=" * 108)
    return rows


# ======================================================================
# 4. Visualization
# ======================================================================

def plot_comparison(states, save_path=None):
    """
    2x2 comparison of the X-Z plane (slice through y = 0): temperature shading
    with flow streamlines overlaid, one panel per scenario.
    """
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))

    # Common temperature scale so panels are directly comparable
    iy = NY // 2
    all_T = np.concatenate([s.T[:, iy, :].ravel() for s in states])
    vmin, vmax = np.min(all_T), np.max(all_T)

    for ax, state in zip(axes.ravel(), states):
        Xs = state.X[:, iy, :]
        Zs = state.Z[:, iy, :]
        Ts = state.T[:, iy, :]
        Us = state.u[:, iy, :]
        Ws = state.w[:, iy, :]

        # Temperature field: diverging map centered on ambient, since the
        # meaningful quantity is the signed anomaly about T_AMBIENT.
        span = max(abs(vmin - T_AMBIENT), abs(vmax - T_AMBIENT))
        mesh = ax.pcolormesh(Xs, Zs, Ts, cmap="RdBu_r", shading="auto",
                             vmin=T_AMBIENT - span, vmax=T_AMBIENT + span)

        # Streamlines need a strictly ascending, evenly spaced grid
        x_line = Xs[:, 0]
        z_line = Zs[0, :]
        ax.streamplot(x_line, z_line, Us.T, Ws.T, color="black",
                      density=1.1, linewidth=0.8, arrowsize=0.8)

        peak_w = state.peak_updraft
        ax.set_title(f"{state.label}\npeak updraft {peak_w:.1f} m/s | "
                     f"mean vorticity {state.total_vorticity:.3f} 1/s",
                     fontsize=11)
        ax.set_xlabel("x (m)")
        ax.set_ylabel("z (m, altitude)")
        ax.set_xlim(x_line.min(), x_line.max())
        ax.set_ylim(0, DOMAIN_HEIGHT)

        cbar = fig.colorbar(mesh, ax=ax, pad=0.02)
        cbar.set_label("Temperature (K)")

    fig.suptitle("Tornado Intervention Comparison - X-Z Plane (y = 0)\n"
                 "Temperature field with in-plane flow streamlines",
                 fontsize=14)
    fig.tight_layout()

    if save_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        save_path = OUTPUT_DIR / "tornado_interventions_comparison.png"
    fig.savefig(save_path, dpi=140)
    plt.close(fig)
    print(f"\nComparison chart saved to: {save_path}")


# ======================================================================
# Main
# ======================================================================

def main():
    X, Y, Z, dx, dy, dz = build_grid()
    T = build_temperature_field(X, Y, Z)
    base = TornadoState(X, Y, Z, dx, dy, dz, T, label="Base Tornado",
                        notes="Undisturbed Burgers-Rott vortex with warm inflow "
                              "and cold RFD pool")

    microwave = run_microwave_beaming(base, target_zone="RFD",
                                      energy_gigawatts=MICROWAVE_GIGAWATTS)
    polymer = run_polymer_desiccation(base, target_zone="updraft",
                                      payload_mass_kg=POLYMER_MASS_KG)
    cryo = run_cryogenic_cooling(base, target_zone="inflow",
                                 cooling_capacity_kelvin=CRYO_DELTA_K)

    benchmark(base, [microwave, polymer, cryo])
    plot_comparison([base, microwave, polymer, cryo])


if __name__ == "__main__":
    main()
