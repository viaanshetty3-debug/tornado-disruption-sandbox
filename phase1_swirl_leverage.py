"""
PHASE 1B: Is there a leverage point?

Phase 1A killed brute-force momentum cancellation. This asks the follow-up:
the tornado's peak wind is not set by its circulation alone, it is set by how
tightly that circulation is CONCENTRATED. Concentration is maintained by
vortex stretching. Stretching is fed by low-level convergent inflow, which is
a far smaller mass budget than the vortex's total angular momentum.

So: is it cheaper to stop the stretching than to remove the spin?

The sandbox's 3D model prescribes core radius independently of the stretching
rate, which is why the earlier "microwave heating" test showed almost nothing
(it cut the updraft but left the core radius, and therefore the winds, alone).
That decoupling is unphysical. In a true Burgers vortex the two are locked:

    r_c = sqrt(4 * nu_t / alpha)

Stretching (alpha) fights turbulent diffusion (nu_t); the core radius is where
they balance. Weaken alpha and the core MUST widen, spreading the same
circulation over more area and dropping the peak wind. This script uses that
consistent relation.
"""

import numpy as np

RHO = 1.225


# ----------------------------------------------------------------------
# Burgers-consistent vortex: core radius follows from the stretching rate
# ----------------------------------------------------------------------

def lamb_oseen_peak_factor():
    """max of (1 - exp(-x^2))/x, where x = r/r_c. About 0.638."""
    x = np.linspace(0.01, 6.0, 20000)
    return np.max((1.0 - np.exp(-x ** 2)) / x)


PEAK_FACTOR = lamb_oseen_peak_factor()


def core_radius(alpha, nu_t):
    """Burgers balance between stretching and turbulent diffusion."""
    return np.sqrt(4.0 * nu_t / alpha)


def peak_wind(gamma, alpha, nu_t):
    """Peak tangential wind of a Burgers vortex of given circulation."""
    return PEAK_FACTOR * gamma / (2.0 * np.pi * core_radius(alpha, nu_t))


def inflow_mass_flux(alpha, r_outer, h_inflow, rho=RHO):
    """
    Convergent mass flux feeding the stretching, through a cylinder of
    radius r_outer and depth h_inflow.

        v_r = -alpha * r / 2
        mdot = rho * (2*pi*r_outer*h_inflow) * (alpha*r_outer/2)
             = rho * pi * r_outer^2 * h_inflow * alpha
    """
    return rho * np.pi * r_outer ** 2 * h_inflow * alpha


# ----------------------------------------------------------------------
# Cost of each attack route, in a common currency (kg/s of mass flux)
# ----------------------------------------------------------------------

def cost_via_circulation(gamma, L_total, target_wind_ratio, window, jet_v, lever):
    """
    Route 1: remove angular momentum. v_peak scales linearly with gamma, so
    halving the wind means halving the circulation, i.e. removing half the
    vortex's angular momentum within the intervention window.
    """
    fraction_to_remove = 1.0 - target_wind_ratio
    Ldot_needed = fraction_to_remove * L_total / window
    mdot_needed = Ldot_needed / (jet_v * lever)
    return {"Ldot": Ldot_needed, "mdot": mdot_needed,
            "fraction": fraction_to_remove}


def cost_via_stretching(alpha, r_outer, h_inflow, target_wind_ratio):
    """
    Route 2: stop the stretching. v_peak ~ sqrt(alpha), so halving the wind
    needs alpha reduced to a quarter, i.e. blocking 75% of the convergent
    inflow. Cost is quoted as the inflow mass flux you must cancel.
    """
    alpha_ratio = target_wind_ratio ** 2
    fraction_to_block = 1.0 - alpha_ratio
    mdot_inflow = inflow_mass_flux(alpha, r_outer, h_inflow)
    return {"alpha_ratio": alpha_ratio, "fraction": fraction_to_block,
            "mdot": fraction_to_block * mdot_inflow,
            "mdot_total_inflow": mdot_inflow}


def passive_drag_requirement(target_wind_ratio, ring_width, c_d=1.2):
    """
    Route 3: block the inflow with a PASSIVE drag field instead of injecting
    momentum. This is a different cost model entirely: a drag element supplies
    no power. It removes momentum using the tornado's own kinetic energy.

    Inflow crossing a field of bluff elements with frontal area density
    a (m^2 of obstacle per m^3 of air) decays as

        dv/dR = -(C_d * a / 2) * v   ->   v(R) = v_0 * exp(-C_d*a*R/2)

    Solving for the density needed to cut inflow to the target ratio over a
    ring of the given width.
    """
    alpha_ratio = target_wind_ratio ** 2          # inflow ratio == alpha ratio
    a_density = -2.0 * np.log(alpha_ratio) / (c_d * ring_width)
    return {"a_density": a_density, "inflow_ratio": alpha_ratio}


def main():
    print("=" * 78)
    print("PHASE 1B - IS THERE A LEVERAGE POINT?")
    print("=" * 78)

    # EF4-class reference vortex, matched to phase 1A
    gamma = 8.0e4
    r_core_obs = 100.0
    r_outer = 400.0
    height = 1500.0
    h_inflow = 100.0
    window = 120.0

    # Turbulent viscosity implied by the observed core radius
    nu_t = 0.0
    alpha = 0.02                                  # 1/s, typical stretching rate
    nu_t = alpha * r_core_obs ** 2 / 4.0
    print(f"\nReference EF4 vortex")
    print(f"  circulation gamma      = {gamma:.1e} m^2/s")
    print(f"  stretching rate alpha  = {alpha:.3f} 1/s")
    print(f"  implied turb. visc.    = {nu_t:.0f} m^2/s   "
          f"(literature range for tornado-scale: 30-100)")
    print(f"  core radius            = {core_radius(alpha, nu_t):.0f} m")
    print(f"  peak wind              = {peak_wind(gamma, alpha, nu_t):.0f} m/s")

    # --- Sweep: what weakening the stretching does to the winds -------
    print("\n" + "=" * 78)
    print("WEAKENING THE STRETCHING (circulation held FIXED)")
    print("-" * 78)
    print(f"{'alpha/alpha_0':>14}{'core radius':>14}{'peak wind':>12}"
          f"{'wind ratio':>12}{'inflow mdot':>15}")
    print(f"{'':>14}{'(m)':>14}{'(m/s)':>12}{'':>12}{'(kg/s)':>15}")

    v0 = peak_wind(gamma, alpha, nu_t)
    for ratio in [1.0, 0.75, 0.5, 0.25, 0.1]:
        a = alpha * ratio
        rc = core_radius(a, nu_t)
        v = peak_wind(gamma, a, nu_t)
        mdot = inflow_mass_flux(a, r_outer, h_inflow)
        print(f"{ratio:>14.2f}{rc:>14.0f}{v:>12.0f}{v/v0:>12.2f}{mdot:>15.2e}")

    print("\n  The circulation never changed. Every unit of angular momentum")
    print("  the tornado had, it still has -- just spread over a wider core.")
    print("  Peak wind goes as sqrt(alpha), so a 4x cut in stretching halves")
    print("  the winds.")

    # --- Head-to-head cost -------------------------------------------
    L_total = RHO * (gamma / (2.0 * np.pi)) * np.pi * r_outer ** 2 * height
    target = 0.5              # halve the peak wind

    route1 = cost_via_circulation(gamma, L_total, target, window,
                                  jet_v=100.0, lever=100.0)
    route2 = cost_via_stretching(alpha, r_outer, h_inflow, target)

    print("\n" + "=" * 78)
    print(f"COST TO HALVE PEAK WIND ({v0:.0f} -> {v0/2:.0f} m/s)")
    print("-" * 78)
    print(f"\n  ROUTE 1 - remove angular momentum")
    print(f"    must remove {route1['fraction']*100:.0f}% of "
          f"{L_total:.2e} kg m^2/s")
    print(f"    active jet mass flux required: {route1['mdot']:.2e} kg/s")
    print(f"\n  ROUTE 2 - block the convergent inflow")
    print(f"    must block {route2['fraction']*100:.0f}% of "
          f"{route2['mdot_total_inflow']:.2e} kg/s inflow")
    print(f"    active jet mass flux required: {route2['mdot']:.2e} kg/s")
    print(f"\n  Route 2 is cheaper by {route1['mdot']/route2['mdot']:.1f}x.")
    print(f"  Tower delivers ~16 kg/s (1,040 kg/s at ideal 5.2 MW).")
    print(f"  Route 2 shortfall vs ideal tower: "
          f"{route2['mdot']/1040.0:,.0f}x")
    print("\n  Better. Still hopeless, if you have to SUPPLY the momentum.")

    # --- The route that changes the cost model ------------------------
    print("\n" + "=" * 78)
    print("ROUTE 3 - PASSIVE DRAG (supply no momentum at all)")
    print("-" * 78)
    print("""
  Routes 1 and 2 both assume a machine pushes air. A drag element does not:
  it removes momentum from the inflow using the tornado's own energy, and
  its power budget is zero. That is a different cost model, so the six
  orders of magnitude do not apply to it.
""")
    print(f"{'ring width (m)':>16}{'frontal area density':>24}"
          f"{'blockage per m^2 ground':>26}")
    print(f"{'':>16}{'(m^2 obstacle / m^3 air)':>24}{'(m^2/m^2, 100m layer)':>26}")
    for ring in [200.0, 500.0, 1000.0, 2000.0]:
        d = passive_drag_requirement(target, ring)
        print(f"{ring:>16.0f}{d['a_density']:>24.4f}"
              f"{d['a_density']*h_inflow:>26.2f}")

    print("""
  Read the last column as "projected obstacle area per unit ground area".
  0.5 is roughly a mature forest. 0.28 is an open woodland or a dense grid
  of poles. These are civil-engineering numbers, not machine numbers: a
  500-2000 m wide roughness ring around what you want to protect.

  This is also the one route with observational support -- tornado damage
  intensity is known to vary with surface roughness and terrain, and the
  corner-flow inflow layer is exactly where that sensitivity lives.
""")

    # --- The caveat that could invert the whole thing ------------------
    print("=" * 78)
    print("THE CAVEAT THAT COULD INVERT THIS")
    print("=" * 78)
    print("""
  Changing the swirl-to-inflow balance does not slide the tornado smoothly
  down a ramp. It moves it across a BIFURCATION. As the corner-flow swirl
  ratio rises past roughly 0.4-1.0, laboratory vortex chambers show the flow
  jump from a single-cell vortex, to a breakdown bubble, to a two-cell
  vortex, to multiple suction vortices.

  Two-cell and multi-vortex states can carry HIGHER peak near-surface winds
  than the single-cell state they came from. So an intervention that changes
  the swirl ratio in the wrong direction, or overshoots, can intensify the
  damage swath rather than reduce it.

  This model cannot tell you which side of the bifurcation you are on. It
  has no time integration, no boundary layer, no pressure solver. That is
  precisely the question a laboratory vortex chamber CAN answer, and it is
  why the phase 1 experiment should be a swirl-ratio perturbation study in a
  Ward-type chamber -- not the aerosol-cancellation test proposed earlier.
""")


if __name__ == "__main__":
    main()
