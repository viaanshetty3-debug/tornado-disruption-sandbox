"""
Run every mechanism that scored a net WIN in comprehensive_disruption_suite.py,
all at once, and score the result two ways.

Winners from that suite (energy loss > 0, threshold met):
    reverse rotation torque   50.6% - 95.2%   (all strengths 0.3-0.8)
    drag force                improves any torque setting
    altitude-band targeting   50.8%   (50-150 m, 70%)
Losers, excluded:
    pressure pulse alone     -37.3%   (ADDED energy)
    vertical shear alone     -27.0%   (ADDED energy)
    core-only targeting       15.8%   (too localized)

Two scores are reported for the combination:

  SCORE A - volumetric kinetic energy loss. This is what the original suite
  measured. It is also very close to meaningless: every one of these
  mechanisms is a multiplicative scaling of a velocity component, and energy
  goes as v^2, so the number falls out of algebra rather than physics. The
  script computes the closed-form prediction alongside the measured value to
  show they agree, i.e. that nothing physical is being learned.

  SCORE B - the momentum bill. To produce this velocity field a machine must
  supply the difference between the disrupted field and the original one.
  This integrates that difference into a momentum, an angular momentum, and
  the energy floor required to deliver it, then compares against what the
  proposed tower can actually put out (phase1_energy_budget.py).

SCORE A says the combination is spectacular. SCORE B says what it costs.
"""

from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "src"))
from tornado_vortex_3d import (
    build_grid_3d, burgers_rott_field, vorticity_3d, kinetic_energy_3d,
    core_vorticity_3d, GAMMA, ALPHA, CORE_CENTER_XY, DOMAIN_HEIGHT,
    AIR_DENSITY,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# Tower capability, corrected, from phase1_energy_budget.py
TOWER_LDOT_SPEC = 8.17e4      # kg m^2/s^2, 16 kg/s of air as actually specced
TOWER_LDOT_IDEAL = 5.20e6     # kg m^2/s^2, 5.2 MW converted perfectly to jets
TOWER_JET_POWER_IDEAL = 5.20e6  # W
WINDOW = 120.0                # s, intervention window

# Angular momentum ratio between the sandbox domain and a real EF4
# (1.18e13 / 5.29e9), from phase1_energy_budget.py
EF4_SCALE = 2230.0

# --- Settings: the strongest winning configuration of each mechanism ----
TORQUE_STRENGTH = 0.8         # best single result in the suite (95.2%)
DRAG_COEFF = 0.15
ALT_BAND = (50.0, 150.0)
ALT_STRENGTH = 0.7


def reverse_torque(X, Y, u, v, strength):
    """Counter-rotating azimuthal injection. Scales v_theta by (1 - strength)."""
    dx = X - CORE_CENTER_XY[0]
    dy = Y - CORE_CENTER_XY[1]
    r = np.hypot(dx, dy)
    r_safe = np.where(r < 1e-6, 1e-6, r)
    cos_t, sin_t = dx / r_safe, dy / r_safe
    v_theta = -u * sin_t + v * cos_t
    return strength * v_theta * sin_t, -strength * v_theta * cos_t


def drag(u, v, w, c):
    return -c * u, -c * v, -c * w


def altitude_band(u, v, Z, z_min, z_max, strength):
    mask = (Z >= z_min) & (Z <= z_max)
    du = np.zeros_like(u)
    dv = np.zeros_like(v)
    du[mask] = -strength * u[mask]
    dv[mask] = -strength * v[mask]
    return du, dv


def momentum_bill(du, dv, dw, X, Y, dx, dy, dz, rho=AIR_DENSITY):
    """
    What a machine must supply to turn the original field into the new one.

      linear momentum   = integral rho |dv| dV                    [kg m/s]
      angular momentum  = integral rho (x*dv_y - y*dv_x) dV       [kg m^2/s]
      energy floor      = integral 0.5 rho |dv|^2 dV              [J]

    The angular momentum term is the one that matters: it is signed, it is
    conserved, and it cannot be evaded by clever geometry. The energy floor
    is a floor only - it assumes every joule lands perfectly, with no losses
    to entrainment, mixing, or the ground.
    """
    cell = dx * dy * dz
    speed = np.sqrt(du ** 2 + dv ** 2 + dw ** 2)
    p_lin = rho * np.sum(speed) * cell
    L_z = rho * np.sum((X - CORE_CENTER_XY[0]) * dv
                       - (Y - CORE_CENTER_XY[1]) * du) * cell
    e_floor = 0.5 * rho * np.sum(speed ** 2) * cell
    return p_lin, abs(L_z), e_floor


def main():
    print("=" * 78)
    print("ALL WINNING MECHANISMS, APPLIED SIMULTANEOUSLY")
    print("=" * 78)

    X, Y, Z, dx, dy, dz = build_grid_3d()
    u0, v0, w0 = burgers_rott_field(X, Y, Z, center_xy=CORE_CENTER_XY,
                                    gamma=GAMMA, alpha=ALPHA)

    ke0 = kinetic_energy_3d(u0, v0, w0, dx, dy, dz)
    ox, oy, oz = vorticity_3d(u0, v0, w0, dx, dy, dz)
    vort0 = core_vorticity_3d(ox, oy, oz, X, Y, Z, center_xy=CORE_CENTER_XY)

    print(f"\nBaseline: KE = {ke0:,.0f} J, core vorticity = {vort0:.4f} 1/s")
    print(f"\nStacking: reverse torque {TORQUE_STRENGTH}, drag {DRAG_COEFF}, "
          f"altitude band {ALT_BAND[0]:.0f}-{ALT_BAND[1]:.0f} m "
          f"at {ALT_STRENGTH}")

    # --- Apply all three in sequence -----------------------------------
    u, v, w = u0.copy(), v0.copy(), w0.copy()

    du_t, dv_t = reverse_torque(X, Y, u, v, TORQUE_STRENGTH)
    u, v = u + du_t, v + dv_t

    du_a, dv_a = altitude_band(u, v, Z, *ALT_BAND, ALT_STRENGTH)
    u, v = u + du_a, v + dv_a

    du_d, dv_d, dw_d = drag(u, v, w, DRAG_COEFF)
    u, v, w = u + du_d, v + dv_d, w + dw_d

    ke1 = kinetic_energy_3d(u, v, w, dx, dy, dz)
    ox, oy, oz = vorticity_3d(u, v, w, dx, dy, dz)
    vort1 = core_vorticity_3d(ox, oy, oz, X, Y, Z, center_xy=CORE_CENTER_XY)

    loss = 100.0 * (1.0 - ke1 / ke0)
    vort_left = 100.0 * vort1 / vort0

    # --- SCORE A: the number the old suite would report -----------------
    print("\n" + "=" * 78)
    print("SCORE A - VOLUMETRIC KINETIC ENERGY (what the old suite measured)")
    print("-" * 78)
    print(f"  KE after:            {ke1:,.0f} J")
    print(f"  Energy loss:         {loss:.2f} %")
    print(f"  Core vorticity left: {vort_left:.2f} %")

    # Closed-form prediction: torque and drag are uniform multiplicative
    # scalings of the swirl, so the swirl survives as the product of both.
    # The altitude band applies over part of the domain only, so this is a
    # bound rather than an identity - the gap between them is exactly the
    # band's contribution.
    swirl_factor = (1.0 - TORQUE_STRENGTH) * (1.0 - DRAG_COEFF)
    predicted_no_band = 100.0 * (1.0 - swirl_factor ** 2)
    print(f"\n  Closed-form prediction, torque x drag only, no band:")
    print(f"    swirl scaled by ({1-TORQUE_STRENGTH:.2f})x({1-DRAG_COEFF:.2f})"
          f" = {swirl_factor:.3f}  ->  1 - {swirl_factor:.3f}^2 = "
          f"{predicted_no_band:.2f} %")
    print(f"  Measured with the band added: {loss:.2f} %")
    print(f"""
  The measured value sits just above the closed-form one, and the whole
  difference is the altitude band acting on part of the domain. There is no
  synergy here and none is possible: stacking multiplicative velocity
  scalings multiplies the scalings. The suite's ranking of methods was a
  ranking of how hard each one multiplies.
""")

    # --- SCORE B: what it would cost ------------------------------------
    du = u - u0
    dv = v - v0
    dw = w - w0
    p_lin, L_needed, e_floor = momentum_bill(du, dv, dw, X, Y, dx, dy, dz)

    Ldot_needed = L_needed / WINDOW
    power_floor = e_floor / WINDOW

    print("=" * 78)
    print("SCORE B - THE MOMENTUM BILL (what a machine must supply)")
    print("-" * 78)
    print(f"  Linear momentum to supply:   {p_lin:.3e} kg m/s")
    print(f"  Angular momentum to supply:  {L_needed:.3e} kg m^2/s")
    print(f"  Energy floor (perfect delivery, no losses): {e_floor:.3e} J")
    print(f"\n  Delivered over the {WINDOW:.0f} s window:")
    print(f"    required Ldot:  {Ldot_needed:.3e} kg m^2/s^2")
    print(f"    required power: {power_floor:.3e} W  "
          f"({power_floor/1e6:,.1f} MW)")

    print(f"\n  Against the proposed tower:")
    print(f"    vs tower as specified (Ldot {TOWER_LDOT_SPEC:.2e}): "
          f"{Ldot_needed/TOWER_LDOT_SPEC:>12,.0f}x short")
    print(f"    vs tower at 5.2 MW ceiling ({TOWER_LDOT_IDEAL:.2e}): "
          f"{Ldot_needed/TOWER_LDOT_IDEAL:>12,.0f}x short")
    print(f"    power floor vs 5.2 MW installed: "
          f"{power_floor/TOWER_JET_POWER_IDEAL:>12,.0f}x short")

    print(f"\n  Scaled to a real EF4 (x{EF4_SCALE:,.0f} on angular momentum):")
    print(f"    required Ldot:  {Ldot_needed*EF4_SCALE:.3e} kg m^2/s^2")
    print(f"    vs tower ceiling: "
          f"{Ldot_needed*EF4_SCALE/TOWER_LDOT_IDEAL:,.0f}x short")

    # --- Side by side ----------------------------------------------------
    print("\n" + "=" * 78)
    print("THE TWO SCORES, SIDE BY SIDE")
    print("=" * 78)
    print(f"""
  Score A says this combination removes {loss:.1f}% of the vortex's kinetic
  energy and leaves {vort_left:.1f}% of its core spin. On the strength of a
  number like that, the tower got specced, costed at $1.9M, and given a
  36-month build schedule.

  Score B says producing that velocity field requires {Ldot_needed:.2e} kg m^2/s^2
  of angular momentum flux sustained for two minutes -- {Ldot_needed/TOWER_LDOT_IDEAL:,.0f}x
  more than the tower can deliver at its physical power ceiling, in the
  SANDBOX domain. Against a real EF4 it is {Ldot_needed*EF4_SCALE/TOWER_LDOT_IDEAL:,.0f}x short.

  Stacking the winners did not help, because the thing that was missing was
  never a better combination of mechanisms. It was the supply.
""")

    print("=" * 78)
    print("WHAT THIS DOES AND DOESN'T TELL YOU")
    print("=" * 78)
    print("""
  It is a real calculation of a real quantity: given this exact velocity
  field as the target, this is the momentum a machine has to put in. The
  arithmetic is sound.

  What it is NOT is evidence that the target field would disrupt anything.
  The model still has no time integration, so a vortex handed this field
  cannot be observed either recovering or failing to recover. Score A's
  percentage remains a statement about v^2, not about vortex stability.
  Combining the mechanisms did not fix that and could not have.

  The one route that does not appear in this table is the one that does not
  supply momentum at all -- passive inflow roughness (PHASE1_REPORT.md
  sections 4-5). It sidesteps Score B entirely by using the tornado's own
  kinetic energy, which is why it survived when everything here did not. It
  also carries a real risk of making near-surface winds worse, which is what
  the chamber experiment is meant to settle.
""")


if __name__ == "__main__":
    main()
