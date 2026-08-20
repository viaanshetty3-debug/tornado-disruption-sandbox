"""
Test: Microwave heating + polyacrylate gel disruption method.

Physics model:
1. Microwave satellites heat the upper side of the tornado
   → kills the warm-air buoyancy that drives updraft
   → reduces vertical velocity (w) at high altitudes

2. Polyacrylate gel absorbs water vapor
   → removes latent heat release (energy source of convection)
   → modeled as energy dissipation in the gel-filled region

Result: Combined thermal + energy-dissipation effect.
"""

from pathlib import Path
import sys
import numpy as np
import matplotlib.pyplot as plt

# Import the 3D model
sys.path.insert(0, str(Path(__file__).parent / "src"))
from tornado_vortex_3d import (
    build_grid_3d, burgers_rott_field, vorticity_3d, kinetic_energy_3d,
    core_vorticity_3d, plot_vortex_3d, GAMMA, RC0, ALPHA, CORE_CENTER_XY,
    DOMAIN_HALF_WIDTH, DOMAIN_HEIGHT, NX, NY, NZ, AIR_DENSITY, BL_PEAK_HEIGHT
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# ============================================================================
# Method Parameters
# ============================================================================

# 1. MICROWAVE HEATING: throttle vertical velocity above this altitude
MICROWAVE_HEATING_THRESHOLD = 100.0  # Start heating above 100 m
MICROWAVE_THROTTLE_FRACTION = 0.4    # Kill 60% of updraft in heated region (40% remains)

# 2. POLYACRYLATE GEL: deploy in a 30 m radius sphere at the disruption center
GEL_INJECTION_LOCATION = (15.0, 0.0, 60.0)  # (x, y, z) - center of gel blob
GEL_RADIUS = 30.0                            # Sphere of influence (m)
GEL_ENERGY_RETENTION = 0.1                   # Gel absorbs water vapor → kill 90% of energy (10% remains)


def apply_microwave_heating(w, Z, threshold=MICROWAVE_HEATING_THRESHOLD, throttle=MICROWAVE_THROTTLE_FRACTION):
    """
    Reduce vertical velocity above the heating threshold altitude.
    Simulates microwave satellites weakening the buoyant updraft.
    """
    w_heated = w.copy()
    mask = Z >= threshold
    w_heated[mask] *= throttle
    return w_heated


def apply_polyacrylate_gel_dissipation(u, v, w, X, Y, Z,
                                        center=GEL_INJECTION_LOCATION,
                                        radius=GEL_RADIUS,
                                        energy_retention=GEL_ENERGY_RETENTION):
    """
    Deploy polyacrylate gel in a spherical region.
    The gel absorbs water vapor, which dissipates kinetic energy.
    Modeled as: velocity components inside the gel sphere are scaled
    by energy_retention (e.g., 0.1 = keep 10%, lose 90%).
    """
    cx, cy, cz = center
    dist_sq = (X - cx) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2
    mask = dist_sq <= radius ** 2

    u_gel = u.copy()
    v_gel = v.copy()
    w_gel = w.copy()

    u_gel[mask] *= energy_retention
    v_gel[mask] *= energy_retention
    w_gel[mask] *= energy_retention

    return u_gel, v_gel, w_gel


def main():
    print("=" * 70)
    print("DISRUPTION METHOD TEST: MICROWAVE HEATING + POLYACRYLATE GEL")
    print("=" * 70)

    # Build grid
    X, Y, Z, dx, dy, dz = build_grid_3d()
    z_levels = np.linspace(0.0, DOMAIN_HEIGHT, NZ)

    # ========== BASELINE: Undisturbed vortex ==========
    print("\n[1/3] Computing baseline vortex...")
    u0, v0, w0 = burgers_rott_field(X, Y, Z, center_xy=CORE_CENTER_XY, gamma=GAMMA, alpha=ALPHA)

    ke_baseline = kinetic_energy_3d(u0, v0, w0, dx, dy, dz)
    ox0, oy0, oz0 = vorticity_3d(u0, v0, w0, dx, dy, dz)
    core_vort_baseline = core_vorticity_3d(ox0, oy0, oz0, X, Y, Z, center_xy=CORE_CENTER_XY)

    # ========== STEP 1: Apply microwave heating ==========
    print("[2/3] Applying microwave heating (reduce upper updraft)...")
    w_heated = apply_microwave_heating(w0, Z,
                                       threshold=MICROWAVE_HEATING_THRESHOLD,
                                       throttle=MICROWAVE_THROTTLE_FRACTION)

    # After heating, horizontal components unchanged, only w is reduced
    u_after_heat = u0.copy()
    v_after_heat = v0.copy()

    ke_after_heating = kinetic_energy_3d(u_after_heat, v_after_heat, w_heated, dx, dy, dz)

    # ========== STEP 2: Apply polyacrylate gel dissipation ==========
    print("[3/3] Deploying polyacrylate gel (absorb vapor → dissipate energy)...")
    u_final, v_final, w_final = apply_polyacrylate_gel_dissipation(
        u_after_heat, v_after_heat, w_heated,
        X, Y, Z,
        center=GEL_INJECTION_LOCATION,
        radius=GEL_RADIUS,
        energy_retention=GEL_ENERGY_RETENTION
    )

    ke_final = kinetic_energy_3d(u_final, v_final, w_final, dx, dy, dz)
    ox_f, oy_f, oz_f = vorticity_3d(u_final, v_final, w_final, dx, dy, dz)
    core_vort_final = core_vorticity_3d(ox_f, oy_f, oz_f, X, Y, Z, center_xy=CORE_CENTER_XY)

    # ========== RESULTS ==========
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    # Baseline
    print(f"\nBASELINE (Undisturbed vortex):")
    print(f"  Kinetic energy:    {ke_baseline:,.2f} J")
    print(f"  Core vorticity:    {core_vort_baseline:.4f} 1/s")

    # After heating
    ke_loss_heating = ke_baseline - ke_after_heating
    pct_loss_heating = 100.0 * ke_loss_heating / ke_baseline
    print(f"\nAFTER MICROWAVE HEATING (z >= {MICROWAVE_HEATING_THRESHOLD} m):")
    print(f"  Kinetic energy:    {ke_after_heating:,.2f} J")
    print(f"  Energy lost:       {ke_loss_heating:,.2f} J ({pct_loss_heating:.1f}%)")

    # Final (heating + gel)
    ke_loss_total = ke_baseline - ke_final
    pct_loss_total = 100.0 * ke_loss_total / ke_baseline
    pct_vort_remaining = 100.0 * core_vort_final / core_vort_baseline

    print(f"\nFINAL (After gel deployment within {GEL_RADIUS} m sphere):")
    print(f"  Kinetic energy:    {ke_final:,.2f} J")
    print(f"  Total energy lost: {ke_loss_total:,.2f} J ({pct_loss_total:.1f}%)")
    print(f"  Core vorticity:    {core_vort_final:.4f} 1/s ({pct_vort_remaining:.1f}% of baseline)")

    print("\n" + "=" * 70)
    print("EFFECTIVENESS ASSESSMENT")
    print("=" * 70)

    if pct_loss_total >= 50:
        rating = "✓ HIGHLY EFFECTIVE"
    elif pct_loss_total >= 20:
        rating = "◐ MODERATELY EFFECTIVE"
    else:
        rating = "✗ WEAK EFFECT"

    print(f"\nEnergy dissipation: {pct_loss_total:.1f}% → {rating}")
    print(f"Core vorticity retention: {pct_vort_remaining:.1f}%")

    if pct_vort_remaining < 50:
        print("  → Vortex core significantly destabilized")
    elif pct_vort_remaining < 80:
        print("  → Vortex core weakened but still spinning")
    else:
        print("  → Vortex core largely unaffected")

    print("=" * 70)

    # Save visualization
    plot_vortex_3d(X, Y, Z, u_final, v_final, w_final, CORE_CENTER_XY,
                   GEL_INJECTION_LOCATION, z_levels,
                   save_path=OUTPUT_DIR / "microwave_gel_disruption.png")

    # Save metrics to file
    metrics_file = OUTPUT_DIR / "microwave_gel_metrics.txt"
    with open(metrics_file, "w") as f:
        f.write("MICROWAVE HEATING + POLYACRYLATE GEL DISRUPTION TEST\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Baseline KE:       {ke_baseline:,.2f} J\n")
        f.write(f"After heating:     {ke_after_heating:,.2f} J ({pct_loss_heating:.1f}% loss)\n")
        f.write(f"Final (+ gel):     {ke_final:,.2f} J ({pct_loss_total:.1f}% total loss)\n")
        f.write(f"\nBaseline vorticity:  {core_vort_baseline:.4f} 1/s\n")
        f.write(f"Final vorticity:     {core_vort_final:.4f} 1/s ({pct_vort_remaining:.1f}% remaining)\n")
        f.write(f"\nEffectiveness: {rating}\n")

    print(f"\nMetrics saved to: {metrics_file}")


if __name__ == "__main__":
    main()
