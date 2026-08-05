"""
Extended Tornado Disruption Strategies
======================================

Five additional intervention strategies plus one stacked "combined arms" case,
built on the same physics framework as `tornado_intervention_sandbox` so every
method is scored against an identical baseline vortex.

The original three strategies all act on the *thermodynamics* (heat the RFD,
load the updraft with mass, chill the inflow). The strategies here deliberately
widen the search space along three new axes:

  * DYNAMIC     - remove momentum instead of heat.
        4. Surface Drag Field    - engineered roughness throttles the radial
                                   inflow that feeds the corner flow.
        5. Kinetic Jet Barrage   - anchored thrust units inject counter-swirl
                                   momentum directly into the core.

  * MICROPHYSICAL - act on the water cycle rather than on the air.
        6. Hygroscopic Seeding   - force early condensation to load the updraft
                                   with precipitation mass.

  * IMPULSIVE / PREVENTIVE - change *when* you act.
        7. Blast Overpressure    - the popular "just bomb it" proposal, costed.
        8. Aerosol Shading       - cut insolation over the inflow source region
                                   hours upstream, before the storm exists.

  * 9. Combined Arms - drag field + shading + polymer loading applied together,
       to test whether the effects add.

Scope
-----
Same caveats as the base sandbox, and they matter more here, not less: this is
a steady-state diagnostic model with no time integration, no moist
thermodynamics, no pressure solver, and no turbulence closure. Every number
below is an internally consistent comparison *within* the sandbox. None of them
is a prediction about a real storm, and nothing here should be read as a design
basis for hardware. The value of the exercise is the ranking and the sign of
the side effects, not the magnitudes.
"""

import numpy as np

from tornado_intervention_sandbox import (
    # physical constants
    G, CP_AIR, RHO_AIR, T_AMBIENT,
    # domain / vortex geometry
    DOMAIN_HEIGHT, CORE_CENTER_XY,
    INTERVENTION_DURATION_S, POLYMER_MASS_KG,
    # framework
    zone_mask, zone_air_mass, run_polymer_desiccation,
)


# ======================================================================
# Strategy parameters
# ======================================================================

# --- 4. Surface drag field ---
ROUGHNESS_CD = 0.02             # Bulk canopy drag coefficient of the array
ROUGHNESS_FIELD_RADIUS = 250.0  # Radius of the prepared ground (m)
ROUGHNESS_ELEMENT_H = 30.0      # Vertical influence depth of the elements (m)
ROUGHNESS_FETCH_M = 500.0       # Path length air traverses over the array (m)
ROUGHNESS_STEEL_KG_PER_M2 = 15.0    # Structural mass per m^2 of prepared ground
STEEL_EMBODIED_J_PER_KG = 30e6      # Embodied energy of structural steel (J/kg)
ROUGHNESS_LIFETIME_EVENTS = 100.0   # Tornado encounters amortized over service life

# --- 5. Kinetic jet barrage ---
JET_UNIT_THRUST_N = 400_000.0   # Per-unit thrust, ~ one large turbofan (N)
JET_UNIT_COUNT = 20             # Number of anchored units
JET_ENVELOPE_R = 60.0           # Horizontal reach of the thrust envelope (m)
JET_ENVELOPE_H = 300.0          # Vertical extent of the engaged column (m)
JET_TSFC_KG_PER_N_S = 1.0e-5    # Thrust-specific fuel consumption
JET_FUEL_J_PER_KG = 43e6        # Jet-A specific energy (J/kg)
MESOCYCLONE_RADIUS_M = 3000.0   # Radius of the real angular momentum reservoir (m)

# --- 6. Hygroscopic seeding ---
INFLOW_MIXING_RATIO = 0.016     # Water vapour mixing ratio of the inflow (kg/kg)
SEED_CONVERSION_EFFICIENCY = 0.10   # Extra vapour fraction condensed early
LATENT_HEAT_VAPORIZATION = 2.5e6    # L_v (J/kg)
SEED_MATERIAL_KG = 5_000.0          # Hygroscopic salt / flare mass (kg)
SEED_EMBODIED_J_PER_KG = 5e6        # Material + dispersal energy (J/kg)

# --- 7. Blast overpressure ---
BLAST_YIELD_TONNES_TNT = 1000.0     # 1 kt-equivalent (the usual proposal)
J_PER_TONNE_TNT = 4.184e9
BLAST_THERMAL_FRACTION = 0.35       # Yield fraction appearing as heat
BLAST_KINETIC_FRACTION = 0.50       # Yield fraction appearing as blast wave
BLAST_PERSISTENCE_S = 3.0           # Lifetime of the overpressure pulse (s)

# --- 8. Aerosol shading ---
SOLAR_FLUX_W_M2 = 800.0         # Clear-sky insolation over the source region
SHADE_FRACTION = 0.30           # Fraction of insolation blocked
SHADE_LEAD_TIME_S = 3.0 * 3600  # Hours of shading before the storm matures
MIXED_LAYER_DEPTH_M = 1000.0    # Boundary layer heated by the blocked flux
SHADE_AREA_M2 = 2.5e9           # Mesoscale footprint, ~50 x 50 km
AEROSOL_MASS_PER_M2 = 6.0e-5    # kg/m^2 for optical depth ~0.3
AEROSOL_DELIVERY_J_PER_KG = 26e6    # Airlift fuel + material embodied energy

# --- Continuity control surface (shared by the dynamic strategies) ---
CONTROL_RADIUS_M = 150.0        # Radius of the inflow accounting cylinder (m)
CONTROL_BAND_M = 40.0           # Radial thickness of the accounting band (m)
CONTROL_TOP_M = 150.0           # Depth of the inflow layer accounted for (m)


# ======================================================================
# Shared helpers
# ======================================================================

def _radius(state):
    """Horizontal distance from the vortex axis, desingularized."""
    r = np.hypot(state.X - CORE_CENTER_XY[0], state.Y - CORE_CENTER_XY[1])
    return r, np.maximum(r, 1e-6)


def inflow_mass_flux(state, u=None, v=None):
    """
    Inward mass flux through a control cylinder around the core.

    A tornado's intensity is set by the angular momentum the boundary layer
    delivers to the corner flow, so the radial inflow through a cylinder at
    r = CONTROL_RADIUS_M below CONTROL_TOP_M is the quantity that any
    momentum-removing intervention has to move. Only the *ratio* before and
    after matters, so this returns an unnormalized flux integral.
    """
    u = state.u if u is None else u
    v = state.v if v is None else v

    r, r_safe = _radius(state)
    band = np.abs(r - CONTROL_RADIUS_M) <= (0.5 * CONTROL_BAND_M)
    low = state.Z <= CONTROL_TOP_M
    sel = band & low

    # Radial component of the horizontal wind; inflow is negative v_r
    v_r = (u * (state.X - CORE_CENTER_XY[0])
           + v * (state.Y - CORE_CENTER_XY[1])) / r_safe
    inward = np.maximum(-v_r, 0.0)

    cell_volume = state.dx * state.dy * state.dz
    return float(np.sum(inward * state.rho * sel) * cell_volume)


def continuity_updraft_scale(state, u_new, v_new, floor=0.0, ceiling=1.5):
    """
    Scale factor for the stretching updraft implied by a change in radial inflow.

    Mass continuity ties the vertical flux out of the corner flow to the radial
    flux into it: throttle the inflow and the stretching updraft it feeds has to
    weaken in proportion. Returns 1.0 (no change) if the baseline flux is
    degenerate.
    """
    base_flux = inflow_mass_flux(state)
    if base_flux <= 0.0:
        return 1.0
    ratio = inflow_mass_flux(state, u_new, v_new) / base_flux
    return float(np.clip(ratio, floor, ceiling))


def _horizontal_speed(u, v):
    speed = np.hypot(u, v)
    return speed, np.maximum(speed, 1e-6)


def decompose_horizontal(state, u=None, v=None):
    """
    Split the horizontal wind into radial and tangential components about the
    vortex axis. Returns (r, e_x, e_y, v_r, v_theta) where (e_x, e_y) is the
    outward radial unit vector; v_r > 0 is outflow and v_theta > 0 is
    counter-clockwise swirl.
    """
    u = state.u if u is None else u
    v = state.v if v is None else v
    r, r_safe = _radius(state)
    ex = (state.X - CORE_CENTER_XY[0]) / r_safe
    ey = (state.Y - CORE_CENTER_XY[1]) / r_safe
    v_r = u * ex + v * ey
    v_theta = -u * ey + v * ex
    return r, ex, ey, v_r, v_theta


def recompose_horizontal(ex, ey, v_r, v_theta):
    """Inverse of `decompose_horizontal`."""
    return v_r * ex - v_theta * ey, v_r * ey + v_theta * ex


def angular_momentum_influx(state):
    """
    Rate at which the boundary-layer inflow delivers angular momentum through
    the control cylinder (kg m^2 / s^2, i.e. N m).

    This is the torque the storm supplies to keep the core spinning, and it is
    the quantity any counter-swirl device has to beat. The shell is a volume of
    finite radial thickness, so dividing the volume integral by that thickness
    recovers the surface integral over the cylinder.
    """
    r, _, _, v_r, v_theta = decompose_horizontal(state)
    sel = (np.abs(r - CONTROL_RADIUS_M) <= 0.5 * CONTROL_BAND_M) & (state.Z <= CONTROL_TOP_M)
    inward = np.maximum(-v_r, 0.0)
    cell_volume = state.dx * state.dy * state.dz
    integral = float(np.sum(state.rho * inward * v_theta * r * sel) * cell_volume)
    return integral / CONTROL_BAND_M


# ======================================================================
# 4. Surface drag field
# ======================================================================

def run_surface_roughness(state, drag_coefficient=ROUGHNESS_CD,
                          field_radius=ROUGHNESS_FIELD_RADIUS,
                          element_height=ROUGHNESS_ELEMENT_H,
                          fetch_m=ROUGHNESS_FETCH_M):
    """
    (d) SURFACE DRAG FIELD

    Cover the ground around the expected track with engineered roughness -
    dense baffle arrays, berms, or planted windbreaks - so the boundary-layer
    inflow loses momentum before it reaches the corner flow.

    Unlike every other method here this one attacks the *dynamics*, not the
    thermodynamics. Tornado intensity is governed by the angular momentum the
    surface layer transports inward; a canopy drag law removes a fixed fraction
    of that momentum per unit fetch:

        d|V| / dx = -(C_d / h) * |V|      ->      |V|_out / |V|_in = exp(-C_d L / h)

    The surviving fraction depends only on the drag coefficient, the element
    height h, and the fetch L the air crosses - not on wind speed - so the
    method does not weaken as the vortex strengthens. The throttled inflow is
    then fed back into the stretching updraft through mass continuity.
    """
    r, _ = _radius(state)

    # Where the array actually sits: prepared ground out to `field_radius`,
    # with influence decaying above the element tops.
    footprint = np.exp(-(r ** 2) / (2.0 * field_radius ** 2))
    vertical = np.exp(-state.Z / element_height)
    coverage = footprint * vertical

    # Canopy drag law: fraction of horizontal momentum surviving the fetch
    surviving = np.exp(-drag_coefficient * fetch_m / element_height)
    drag_factor = 1.0 - coverage * (1.0 - surviving)

    u_new = state.u * drag_factor
    v_new = state.v * drag_factor

    # Continuity: less inflow means less vertical stretching
    scale = continuity_updraft_scale(state, u_new, v_new)
    w_base_new = state.w_base * scale

    # Cost: this is infrastructure, not an operating expense. Charge the
    # embodied energy of the structure, amortized over its service life.
    # A canopy's drag coefficient scales with the frontal area density of its
    # elements, so buying more C_d means proportionally more structure.
    prepared_area = np.pi * field_radius ** 2
    mass_per_m2 = ROUGHNESS_STEEL_KG_PER_M2 * (drag_coefficient / ROUGHNESS_CD)
    steel_kg = prepared_area * mass_per_m2
    total_embodied_j = steel_kg * STEEL_EMBODIED_J_PER_KG
    per_event_j = total_embodied_j / ROUGHNESS_LIFETIME_EVENTS

    notes = (f"C_d = {drag_coefficient:.3f} over {fetch_m:.0f} m fetch, "
             f"{element_height:.0f} m elements -> {(1-surviving)*100:.0f}% of "
             f"inflow momentum removed; continuity scales the stretching "
             f"updraft to {scale*100:.1f}%; {steel_kg/1e6:.2f} kt of structure "
             f"over {prepared_area/1e4:.1f} ha ({total_embodied_j/1e12:.1f} TJ "
             f"embodied, amortized over {ROUGHNESS_LIFETIME_EVENTS:.0f} events). "
             f"Caveat: static infrastructure only helps where it was built, and "
             f"tornado tracks are not known in advance.")

    new_state = state.derive(u=u_new, v=v_new, w_base=w_base_new,
                             label="Surface Drag Field", notes=notes)
    new_state.energy_cost_j = per_event_j
    new_state.inflow_scale = scale
    new_state.resource_note = (f"{steel_kg/1e6:.2f} kt structure over "
                               f"{prepared_area/1e4:.0f} ha, permanent")
    return new_state


# ======================================================================
# 5. Kinetic jet barrage
# ======================================================================

def run_kinetic_jet_barrage(state, unit_thrust_n=JET_UNIT_THRUST_N,
                            unit_count=JET_UNIT_COUNT,
                            envelope_radius=JET_ENVELOPE_R,
                            envelope_height=JET_ENVELOPE_H,
                            duration_s=INTERVENTION_DURATION_S):
    """
    (e) KINETIC JET BARRAGE

    Ring the core with anchored turbofan or rocket units firing against the
    rotation, injecting counter-swirl momentum directly.

    Swirl is an angular momentum problem, so thrust alone is the wrong figure
    of merit - what matters is torque measured against the torque the storm
    itself supplies. The boundary-layer inflow continuously carries angular
    momentum inward through the control cylinder at a rate

        L_dot = integral( rho * (-v_r) * v_theta * r ) dA

    and the barrage applies a counter-torque F_total * R_lever. The steady
    fractional reduction in core swirl is the ratio of the two, capped at a
    full stop:

        f = min( F_total * R_lever / L_dot , 1 )

    Because L_dot scales with the product of inflow and swirl, the same
    hardware buys less as the vortex intensifies - the same self-defeating
    structure the polymer method has, arrived at independently.

    IMPORTANT - this method flatters itself in this sandbox. L_dot is measured
    at CONTROL_RADIUS_M, inside a 600 m domain, so it accounts only for the
    angular momentum already close to the axis. A real tornado draws from a
    mesocyclone kilometres across, and for roughly constant circulation and
    inflow speed L_dot grows linearly with reservoir radius. The notes
    therefore report both the in-domain fraction and a reservoir-corrected
    figure scaled by CONTROL_RADIUS_M / MESOCYCLONE_RADIUS_M. Treat the
    in-domain number as an upper bound on what the hardware could achieve, and
    the corrected one as the honest order of magnitude.
    """
    r, ex, ey, v_r, v_theta = decompose_horizontal(state)

    envelope = (np.exp(-(r ** 2) / (2.0 * envelope_radius ** 2))
                * np.exp(-state.Z / envelope_height))
    envelope_norm = envelope / max(float(np.max(envelope)), 1e-12)

    total_thrust = unit_thrust_n * unit_count
    torque = total_thrust * envelope_radius
    supplied_torque = angular_momentum_influx(state)
    fraction = float(np.clip(torque / max(supplied_torque, 1e-9), 0.0, 1.0))

    # Remove swirl only; the radial inflow is left to the drag-field method.
    v_theta_new = v_theta * (1.0 - fraction * envelope_norm)
    u_new, v_new = recompose_horizontal(ex, ey, v_r, v_theta_new)

    scale = continuity_updraft_scale(state, u_new, v_new)
    w_base_new = state.w_base * scale

    fuel_kg = total_thrust * JET_TSFC_KG_PER_N_S * duration_s
    energy_j = fuel_kg * JET_FUEL_J_PER_KG

    peak_swirl = float(np.max(np.abs(v_theta)))
    reservoir_fraction = fraction * (CONTROL_RADIUS_M / MESOCYCLONE_RADIUS_M)
    units_for_reservoir = unit_count * (MESOCYCLONE_RADIUS_M / CONTROL_RADIUS_M)

    notes = (f"{unit_count} x {unit_thrust_n/1e3:.0f} kN = "
             f"{total_thrust/1e6:.1f} MN at a {envelope_radius:.0f} m lever = "
             f"{torque/1e6:.0f} MN m of counter-torque, against "
             f"{supplied_torque/1e6:.0f} MN m/s the inflow delivers across the "
             f"{CONTROL_RADIUS_M:.0f} m control cylinder -> {fraction*100:.1f}% "
             f"of core swirl removed in-domain (peak tangential wind "
             f"{peak_swirl:.0f} m/s); {fuel_kg/1e3:.1f} t fuel burned. "
             f"SCALE CORRECTION: against a {MESOCYCLONE_RADIUS_M/1e3:.0f} km "
             f"mesocyclone reservoir the same hardware is worth about "
             f"{reservoir_fraction*100:.1f}%, and matching this result would "
             f"take ~{units_for_reservoir:.0f} units. Caveats: the units need "
             f"foundations that survive the wind field they are fighting, and "
             f"stripping swirl without throttling inflow lowers the swirl ratio, "
             f"which in a real corner flow can intensify the low-level updraft "
             f"rather than kill it.")

    new_state = state.derive(u=u_new, v=v_new, w_base=w_base_new,
                             label="Kinetic Jet Barrage", notes=notes)
    new_state.energy_cost_j = energy_j
    new_state.swirl_fraction_removed = fraction
    new_state.supplied_torque = supplied_torque
    new_state.resource_note = (f"{unit_count} anchored {unit_thrust_n/1e3:.0f} kN "
                               f"units, {fuel_kg/1e3:.1f} t fuel")
    return new_state


# ======================================================================
# 6. Hygroscopic seeding
# ======================================================================

def run_hygroscopic_seeding(state, target_zone="updraft",
                            conversion_efficiency=SEED_CONVERSION_EFFICIENCY,
                            mixing_ratio=INFLOW_MIXING_RATIO,
                            seed_mass_kg=None):
    """
    (f) HYGROSCOPIC SEEDING

    Release hygroscopic nuclei (salt flares, the standard rain-enhancement
    payload) into the updraft to force water vapour to condense early. The
    intent is to convert vapour into precipitation mass while it is still
    inside the core, loading the updraft with water the way the polymer method
    loads it with gel - but using the storm's own water, so the payload is
    grams instead of tonnes.

    The catch is thermodynamic bookkeeping. Condensing water does two opposite
    things at once:

        mass loading      B -= g * (rho_condensate / rho_air)
        latent heating    B += g * (L_v * m_cond) / (m_air * c_p * T_ambient)

    Both terms are proportional to the condensed mass, so their ratio is a pure
    material constant - L_v / (c_p * T_ambient) versus 1 - and it does not
    depend on how much you seed. That ratio is roughly 8.5 to 1 in favour of
    heating. The method's failure is structural, not a matter of dosage.
    """
    mask = zone_mask(state.X, state.Y, state.Z, target_zone)
    cell_volume = state.dx * state.dy * state.dz

    # More conversion needs proportionally more nuclei
    if seed_mass_kg is None:
        seed_mass_kg = SEED_MATERIAL_KG * (conversion_efficiency
                                           / SEED_CONVERSION_EFFICIENCY)

    air_mass = zone_air_mass(state, mask)
    zone_volume = float(np.sum(mask) * cell_volume)

    # Extra vapour converted to condensate by the seeding
    condensate_kg = conversion_efficiency * mixing_ratio * air_mass

    # (i) mass loading, distributed over the treated zone
    loading = (condensate_kg / zone_volume) * mask

    # (ii) latent heat released into the same air
    delta_T = (LATENT_HEAT_VAPORIZATION * condensate_kg) / (air_mass * CP_AIR)
    T_new = state.T + delta_T * mask

    # The two competing buoyancy terms, for the record
    warming_accel = G * delta_T / T_AMBIENT
    loading_accel = G * (condensate_kg / zone_volume) / RHO_AIR
    ratio = warming_accel / max(loading_accel, 1e-12)

    energy_j = seed_mass_kg * SEED_EMBODIED_J_PER_KG

    notes = (f"{seed_mass_kg/1e3:.1f} t of nuclei condense "
             f"{condensate_kg/1e3:.0f} t of the storm's own vapour "
             f"({conversion_efficiency*100:.0f}% of {mixing_ratio*1e3:.0f} g/kg); "
             f"loading {loading_accel:.3f} m/s^2 down vs latent heating "
             f"{warming_accel:.3f} m/s^2 up ({ratio:.1f}x) for a net "
             f"{delta_T:+.2f} K. Caveat: real precipitation falls out and is "
             f"advected away, so the loading term here is an upper bound - "
             f"which makes the heating penalty a lower bound.")

    new_state = state.derive(T=T_new, mass_loading=loading,
                             label="Hygroscopic Seeding", notes=notes)
    new_state.energy_cost_j = energy_j
    new_state.condensate_kg = condensate_kg
    new_state.heating_to_loading_ratio = ratio
    new_state.resource_note = (f"{seed_mass_kg/1e3:.1f} t salt flares, "
                               f"2-3 aircraft sorties")
    return new_state


# ======================================================================
# 7. Blast overpressure
# ======================================================================

def run_blast_overpressure(state, target_zone="updraft",
                           yield_tonnes_tnt=BLAST_YIELD_TONNES_TNT,
                           persistence_s=BLAST_PERSISTENCE_S,
                           duration_s=INTERVENTION_DURATION_S):
    """
    (g) BLAST OVERPRESSURE

    The perennial public suggestion - detonate something large in the core -
    evaluated rather than dismissed. The result is the point of including it.

    A detonation partitions its yield roughly into a blast wave and thermal
    radiation. Those two products have very different lifetimes in this problem:

      * The blast wave is an acoustic transient. It crosses the core in the
        few seconds it takes sound to traverse it, so over a ten-minute
        engagement its time-averaged contribution is scaled by
        persistence / duration - a factor of order 0.005.

      * The heat does not leave. Deposited thermal energy raises the core's
        temperature, and warm air is exactly what an updraft is made of. That
        contribution persists for the whole window.

    So the intervention delivers a fleeting outward shove and a durable buoyancy
    increase. The model does not need to be told that this is counterproductive;
    it falls out of the partition.
    """
    mask = zone_mask(state.X, state.Y, state.Z, target_zone)

    yield_j = yield_tonnes_tnt * J_PER_TONNE_TNT
    thermal_j = yield_j * BLAST_THERMAL_FRACTION
    kinetic_j = yield_j * BLAST_KINETIC_FRACTION

    air_mass = zone_air_mass(state, mask)

    # --- Thermal deposition: persists for the whole engagement window
    delta_T = thermal_j / (air_mass * CP_AIR)
    T_new = state.T + delta_T * mask

    # --- Blast wave: energy-equivalent radial velocity, time-averaged over the
    #     engagement window because the pulse itself lasts only seconds.
    v_blast = np.sqrt(2.0 * kinetic_j / max(air_mass, 1e-9))
    duty_cycle = min(persistence_s / duration_s, 1.0)
    v_effective = v_blast * duty_cycle

    r, r_safe = _radius(state)
    u_new = state.u + v_effective * mask * ((state.X - CORE_CENTER_XY[0]) / r_safe)
    v_new = state.v + v_effective * mask * ((state.Y - CORE_CENTER_XY[1]) / r_safe)

    scale = continuity_updraft_scale(state, u_new, v_new)
    w_base_new = state.w_base * scale

    notes = (f"{yield_tonnes_tnt:.0f} t TNT ({yield_j/1e12:.1f} TJ) into "
             f"{air_mass/1e6:.1f} kt of core air: {thermal_j/1e12:.1f} TJ of heat "
             f"raises it {delta_T:+.1f} K and stays; {kinetic_j/1e12:.1f} TJ of "
             f"blast gives {v_blast:.0f} m/s outflow that survives "
             f"{persistence_s:.0f} s of a {duration_s/60:.0f}-minute window "
             f"({duty_cycle*100:.1f}% duty). Heating the core is the opposite "
             f"of the intended effect.")

    new_state = state.derive(T=T_new, u=u_new, v=v_new, w_base=w_base_new,
                             label="Blast Overpressure", notes=notes)
    new_state.energy_cost_j = yield_j
    new_state.blast_delta_T = delta_T
    new_state.resource_note = (f"{yield_tonnes_tnt:.0f} t TNT-equivalent "
                               f"detonated in the core")
    return new_state


# ======================================================================
# 8. Aerosol shading
# ======================================================================

def run_aerosol_shading(state, shade_fraction=SHADE_FRACTION,
                        lead_time_s=SHADE_LEAD_TIME_S,
                        solar_flux=SOLAR_FLUX_W_M2,
                        mixed_layer_depth=MIXED_LAYER_DEPTH_M):
    """
    (h) AEROSOL SHADING

    Every other strategy here fights the tornado. This one refuses the
    engagement: disperse a reflective aerosol layer over the inflow *source
    region* hours before the storm matures, cutting the surface heating that
    builds the warm moist boundary layer in the first place.

    The cooling is straightforward surface energy budget - blocked flux over
    lead time, spread through the mixed layer:

        dT = -(F_solar * shade_fraction * t_lead) / (rho * h_mixed * c_p)

    The important structural difference from cryogenic cooling is not the
    magnitude, it is the *gradient*. Cryogenic cooling carves a small, sharp
    cold plume whose edges are a baroclinic vorticity factory. A shading
    footprint is mesoscale and its edges are tens of kilometres apart, so the
    same amount of cooling produces a horizontal buoyancy gradient orders of
    magnitude gentler. Baroclinic generation depends on the gradient, not the
    anomaly, which is why the two methods score so differently on side effects.
    """
    energy_deficit_j_m2 = solar_flux * shade_fraction * lead_time_s
    delta_T = -energy_deficit_j_m2 / (RHO_AIR * mixed_layer_depth * CP_AIR)

    # Mesoscale footprint: the shaded region is tens of kilometres across, so
    # across these 600 m of domain the cooling is uniform in the horizontal.
    # That uniformity is the whole point - it is what keeps the horizontal
    # buoyancy gradient, and therefore the baroclinic side effect, near zero.
    # Only the vertical structure of the mixed layer is resolved here.
    mask = np.exp(-state.Z / mixed_layer_depth)

    T_new = state.T + delta_T * mask

    # Aerosol mass follows the optical depth needed for the requested
    # attenuation, tau = -ln(1 - f). The reference loading is calibrated at the
    # default shade fraction; the log divergence as f -> 1 is real - the last
    # few percent of blocked light cost more than all the rest.
    tau_ref = -np.log(1.0 - SHADE_FRACTION)
    tau = -np.log(max(1.0 - shade_fraction, 1e-6))
    aerosol_kg = AEROSOL_MASS_PER_M2 * SHADE_AREA_M2 * (tau / tau_ref)
    energy_j = aerosol_kg * AEROSOL_DELIVERY_J_PER_KG

    notes = (f"{shade_fraction*100:.0f}% of {solar_flux:.0f} W/m^2 blocked for "
             f"{lead_time_s/3600:.1f} h = {energy_deficit_j_m2/1e6:.1f} MJ/m^2 "
             f"withheld -> {delta_T:+.2f} K through a {mixed_layer_depth:.0f} m "
             f"mixed layer, applied uniformly (mesoscale footprint, no sharp "
             f"edge); {aerosol_kg/1e3:.0f} t of aerosol over "
             f"{SHADE_AREA_M2/1e6:.0f} km^2. Caveat: needs hours of warning and "
             f"the right upwind region, and it suppresses convection "
             f"indiscriminately - including rain someone was counting on.")

    new_state = state.derive(T=T_new, label="Aerosol Shading", notes=notes)
    new_state.energy_cost_j = energy_j
    new_state.shading_delta_T = delta_T
    new_state.resource_note = (f"{aerosol_kg/1e3:.0f} t aerosol over "
                               f"{SHADE_AREA_M2/1e6:.0f} km^2, {lead_time_s/3600:.0f} h lead")
    return new_state


# ======================================================================
# 9. Combined arms
# ======================================================================

def run_combined_arms(state, drag_coefficient=ROUGHNESS_CD,
                      shade_fraction=SHADE_FRACTION,
                      payload_mass_kg=POLYMER_MASS_KG):
    """
    (i) COMBINED ARMS

    Apply the three methods that are not actively counterproductive, in the
    order their timescales demand: shading hours upstream, the drag field as
    the vortex crosses prepared ground, and the polymer payload last.

    The reason to test this is that the effects are not independent. Polymer
    retention depends on the ratio of centrifugal acceleration to gravity, so
    it improves once the drag field has already slowed the swirl - the mass
    loading works better on a vortex that has been weakened first. Stacking is
    therefore expected to beat the sum of the parts on that term, and the
    benchmark checks whether it actually does.
    """
    shaded = run_aerosol_shading(state, shade_fraction=shade_fraction)
    roughened = run_surface_roughness(shaded, drag_coefficient=drag_coefficient)
    loaded = run_polymer_desiccation(roughened, payload_mass_kg=payload_mass_kg)

    cost = (getattr(shaded, "energy_cost_j", 0.0)
            + getattr(roughened, "energy_cost_j", 0.0)
            + POLYMER_MASS_KG * G * DOMAIN_HEIGHT
            + (payload_mass_kg / 1000.0) * 100e6)

    notes = (f"shading {getattr(shaded, 'shading_delta_T', 0.0):+.2f} K, then "
             f"drag field (inflow -> "
             f"{getattr(roughened, 'inflow_scale', 1.0)*100:.0f}% of baseline), "
             f"then {payload_mass_kg/1e3:.0f} t polymer at "
             f"{getattr(loaded, 'retention', 0.0)*100:.1f}% retention "
             f"(vs {run_polymer_desiccation(state).retention*100:.1f}% on the "
             f"undisturbed vortex - the drag field makes the payload stick).")

    loaded.label = "Combined Arms"
    loaded.notes = notes
    loaded.energy_cost_j = cost
    loaded.resource_note = "aerosol + drag field + 100 t polymer, layered"
    return loaded


# ======================================================================
# Registry - used by the arena for benchmarking and dose-response sweeps
# ======================================================================

STRATEGY_REGISTRY = [
    # (label, function, dose kwarg, dose values, dose unit label)
    ("Surface Drag Field", run_surface_roughness, "drag_coefficient",
     [0.002, 0.005, 0.01, 0.02, 0.05, 0.1], "canopy C_d"),
    ("Kinetic Jet Barrage", run_kinetic_jet_barrage, "unit_count",
     [1, 2, 5, 10, 20, 50], "thrust units"),
    ("Hygroscopic Seeding", run_hygroscopic_seeding, "conversion_efficiency",
     [0.01, 0.025, 0.05, 0.1, 0.2, 0.4], "vapour converted"),
    ("Blast Overpressure", run_blast_overpressure, "yield_tonnes_tnt",
     [1.0, 10.0, 100.0, 1000.0, 10000.0, 100000.0], "t TNT"),
    ("Aerosol Shading", run_aerosol_shading, "shade_fraction",
     [0.05, 0.1, 0.2, 0.3, 0.5, 0.8], "insolation blocked"),
]


def build_all_strategies(base):
    """Run every extended strategy against a shared baseline state."""
    return [
        run_surface_roughness(base),
        run_kinetic_jet_barrage(base),
        run_hygroscopic_seeding(base),
        run_blast_overpressure(base),
        run_aerosol_shading(base),
        run_combined_arms(base),
    ]
