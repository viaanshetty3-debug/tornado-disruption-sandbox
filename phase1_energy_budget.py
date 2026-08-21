"""
PHASE 1A: Momentum and energy budget for a physical disruptor.

The sandbox tests so far answered "if the velocity field were altered like
THIS, would the vortex survive?" They never asked where the altered momentum
comes from. A machine has to supply it. This script does that accounting.

Three questions:
  1. How much angular momentum does a tornado actually hold?
  2. How much can the specified tower deliver, per second?
  3. How long would the tower have to fire to cancel it?

All figures are order-of-magnitude estimates with stated assumptions.
"""

import numpy as np

RHO = 1.225          # kg/m^3, sea-level air density
L_VAP = 2.5e6        # J/kg, latent heat of vaporization


# ----------------------------------------------------------------------
# Tornado angular momentum and kinetic energy
# ----------------------------------------------------------------------

def vortex_budget(gamma, r_core, r_outer, height, rho=RHO):
    """
    Angular momentum and kinetic energy of a Rankine-like vortex column.

    Outside the core, v_theta = gamma / (2*pi*r), so the specific angular
    momentum r*v_theta = gamma/(2*pi) is CONSTANT with radius. That makes
    the volume integral straightforward:

        L = rho * (gamma / 2pi) * V

    Kinetic energy is dominated by the swirl and integrates as

        KE = 0.5 * rho * h * (gamma/2pi)^2 * 2*pi * ln(r_outer/r_core)

    The log means KE is only weakly sensitive to where we truncate, which
    is why KE is a less useful disruption target than L. Angular momentum
    is the conserved, un-hideable quantity: it scales with volume and there
    is no way to make it small by choosing a boundary cleverly.

    r_core is passed explicitly rather than scaled off r_outer, so peak
    winds come out at observed values instead of an artifact of the ratio.
    """
    volume = np.pi * r_outer ** 2 * height
    specific_L = gamma / (2.0 * np.pi)          # r * v_theta, m^2/s
    L = rho * specific_L * volume               # kg m^2 / s

    KE = 0.5 * rho * height * (specific_L ** 2) * 2.0 * np.pi * np.log(r_outer / r_core)

    # Lamb-Oseen peak: max of (1 - exp(-x^2))/x at x = r/r_core
    x = np.linspace(0.05, 5.0, 4000)
    peak_factor = np.max((1.0 - np.exp(-x ** 2)) / x)
    v_peak = peak_factor * gamma / (2.0 * np.pi * r_core)

    return {
        "gamma": gamma,
        "r_core": r_core,
        "r_outer": r_outer,
        "height": height,
        "volume": volume,
        "L": L,
        "KE": KE,
        "v_peak": v_peak,
    }


# ----------------------------------------------------------------------
# What the specified tower can actually deliver
# ----------------------------------------------------------------------

def tower_delivery(n_compressors=8, m3_per_min_each=100.0, jet_velocity=100.0,
                   lever_arm=50.0, shaft_power_each=650e3, rho=RHO):
    """
    Mass, momentum and angular-momentum flux from the tower spec.

    NOTE ON A SPEC ERROR: tower_design_overview.txt lists both
    "800 kg/s air injection" and "800 m^3/min = 13.3 kg/s". Those differ by
    ~50x. Compressor ratings are free-air delivery in m^3/min, so the
    volumetric figure is the real one: 800 m^3/min of air at 1.225 kg/m^3
    is ~16 kg/s, not 800 kg/s. The larger number was wrong.

    Two rows are reported:
      - "as specified": mass flux the listed compressors actually move.
      - "power-limited ideal": the most mass flux 5.2 MW could accelerate to
        the jet velocity if every watt became jet kinetic energy
        (P = 0.5 * mdot * V^2). Real compressors are ~10-20% efficient at
        this, so this is a hard upper bound, not a design point.
    """
    m3_per_s = n_compressors * m3_per_min_each / 60.0
    mdot_spec = rho * m3_per_s

    shaft_power = n_compressors * shaft_power_each
    mdot_ideal = 2.0 * shaft_power / jet_velocity ** 2

    def fluxes(mdot):
        return {
            "mdot": mdot,
            "thrust": mdot * jet_velocity,                       # N
            "Ldot": mdot * jet_velocity * lever_arm,             # kg m^2 / s^2
            "jet_power": 0.5 * mdot * jet_velocity ** 2,         # W
        }

    return {
        "shaft_power": shaft_power,
        "as_specified": fluxes(mdot_spec),
        "power_limited_ideal": fluxes(mdot_ideal),
    }


def storm_resupply(updraft_diameter=10e3, w=30.0, rho_mid=0.7,
                   condensate_ratio=0.010, ke_conversion=0.003):
    """
    Rate at which the parent supercell regenerates what you remove.

    Latent heat release is the storm's engine. Only a small fraction becomes
    organized kinetic energy (a few tenths of a percent is the usual estimate
    for deep convection); the rest goes to buoyancy, precipitation, mixing.
    """
    area = np.pi * (updraft_diameter / 2.0) ** 2
    mdot_updraft = rho_mid * w * area
    latent_power = mdot_updraft * condensate_ratio * L_VAP
    ke_power = latent_power * ke_conversion
    return {
        "mdot_updraft": mdot_updraft,
        "latent_power": latent_power,
        "ke_power": ke_power,
    }


def fmt_time(seconds):
    if seconds < 120:
        return f"{seconds:,.0f} s"
    if seconds < 7200:
        return f"{seconds/60:,.1f} min"
    if seconds < 2 * 86400:
        return f"{seconds/3600:,.1f} hours"
    return f"{seconds/86400:,.1f} days"


def main():
    print("=" * 78)
    print("PHASE 1A - MOMENTUM AND ENERGY BUDGET FOR A PHYSICAL DISRUPTOR")
    print("=" * 78)

    # --- The three vortices we care about -----------------------------
    cases = {
        "Sandbox model (r_c=15m, r=60m, h=300m)":
            vortex_budget(gamma=8.0e3, r_core=15.0, r_outer=60.0, height=300.0),
        "Real EF2 (r_c=40m, r=150m, h=1000m)":
            vortex_budget(gamma=2.0e4, r_core=40.0, r_outer=150.0, height=1000.0),
        "Real EF4 (r_c=100m, r=400m, h=1500m)":
            vortex_budget(gamma=8.0e4, r_core=100.0, r_outer=400.0, height=1500.0),
    }

    print("\nVORTEX INVENTORY")
    print("-" * 78)
    print(f"{'Case':<40}{'peak wind':>12}{'Ang. momentum':>16}{'Kinetic energy':>16}")
    print(f"{'':<40}{'(m/s)':>12}{'(kg m^2/s)':>16}{'(J)':>16}")
    for name, c in cases.items():
        print(f"{name:<40}{c['v_peak']:>12.0f}{c['L']:>16.2e}{c['KE']:>16.2e}")

    print("\n  Peak winds are the check on whether these are real tornadoes:")
    print("  EF2 ~ 50-60 m/s, EF4 ~ 90 m/s. Circulations were chosen to land there.")

    # --- What the tower delivers --------------------------------------
    tower = tower_delivery()
    print("\n" + "=" * 78)
    print("TOWER DELIVERY (from tower_design_overview.txt, corrected)")
    print("-" * 78)
    print(f"Installed shaft power: {tower['shaft_power']/1e6:.1f} MW")
    print(f"{'':<24}{'mdot':>12}{'thrust':>14}{'Ldot':>14}{'jet power':>14}")
    print(f"{'':<24}{'(kg/s)':>12}{'(N)':>14}{'(kg m^2/s^2)':>14}{'(W)':>14}")
    for label, f in (("as specified", tower["as_specified"]),
                     ("power-limited ideal", tower["power_limited_ideal"])):
        print(f"{label:<24}{f['mdot']:>12.1f}{f['thrust']:>14.2e}"
              f"{f['Ldot']:>14.2e}{f['jet_power']:>14.2e}")

    print("\n  NOTE: the spec's '800 kg/s' is a unit error. 800 m^3/min of air")
    print("        is ~16 kg/s. The corrected figure is used throughout.")

    # --- Time to cancel -----------------------------------------------
    print("\n" + "=" * 78)
    print("TIME TO CANCEL THE VORTEX'S ANGULAR MOMENTUM")
    print("-" * 78)
    print("  tau = L / Ldot, assuming EVERY unit of injected angular momentum")
    print("  lands on the vortex with the right sign and none is lost to")
    print("  entrainment, mixing, or the ground. Wildly optimistic.\n")

    print(f"{'Case':<44}{'as specified':>16}{'ideal 5.2MW':>16}")
    for name, c in cases.items():
        tau_spec = c["L"] / tower["as_specified"]["Ldot"]
        tau_ideal = c["L"] / tower["power_limited_ideal"]["Ldot"]
        print(f"{name:<44}{fmt_time(tau_spec):>16}{fmt_time(tau_ideal):>16}")

    print("\n  Intervention window available: ~120 s (2 minutes).")

    # --- The gap ------------------------------------------------------
    print("\n" + "=" * 78)
    print("THE GAP")
    print("-" * 78)
    window = 120.0
    for name, c in cases.items():
        need = c["L"] / window
        gap_spec = need / tower["as_specified"]["Ldot"]
        gap_ideal = need / tower["power_limited_ideal"]["Ldot"]
        print(f"\n{name}")
        print(f"  Ldot needed to cancel in 120 s: {need:.2e} kg m^2/s^2")
        print(f"  Shortfall vs tower as specified: {gap_spec:>10,.0f}x")
        print(f"  Shortfall vs ideal 5.2 MW jets:  {gap_ideal:>10,.0f}x")

    # --- Resupply -----------------------------------------------------
    storm = storm_resupply()
    print("\n" + "=" * 78)
    print("AND THE STORM IS REFILLING IT")
    print("-" * 78)
    print(f"  Supercell updraft mass flux:   {storm['mdot_updraft']:.2e} kg/s")
    print(f"  Latent heat release:           {storm['latent_power']:.2e} W "
          f"({storm['latent_power']/1e12:.0f} TW)")
    print(f"  Fraction becoming kinetic:     {storm['ke_power']:.2e} W "
          f"({storm['ke_power']/1e9:.0f} GW)")
    print(f"  Tower jet power (ideal):       {tower['power_limited_ideal']['jet_power']:.2e} W")
    print(f"\n  The storm generates kinetic energy "
          f"{storm['ke_power']/tower['power_limited_ideal']['jet_power']:,.0f}x "
          f"faster\n  than the tower can inject it.")

    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    print("""
  Brute-force momentum cancellation does not work, and not by a small
  margin. Against a real EF4 the tower is short by ~7 orders of magnitude,
  and the parent storm resupplies kinetic energy thousands of times faster
  than the tower removes it.

  Every earlier sandbox "success" assumed the counter-rotation was simply
  present. Applying -0.3 * v_theta and then measuring a 50% energy drop is
  arithmetic, not physics: energy goes as v^2, so scaling v by 0.7 gives
  1 - 0.49 = 51% by construction. The model never charged us for the
  momentum. This does.

  A machine at tower scale cannot win this fight by force. The only
  remaining route is leverage: perturbing something the vortex is sensitive
  to, rather than paying for its angular momentum directly. That is what
  phase1_swirl_leverage.py tests.
""")


if __name__ == "__main__":
    main()
