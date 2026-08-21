"""
Test: Reverse rotation torque + drag force disruption method.

Physics model:
1. Reverse rotation torque: Apply azimuthal velocity opposing the tornado's spin
   → Creates shear layers that disrupt coherence
   → Acts like injecting counter-rotating fluid

2. Drag force: Apply velocity-dependent braking force
   → Models atmospheric resistance, friction, or injected dissipative medium
   → F = -c·v, reducing velocity proportionally
"""

from pathlib import Path
import sys
import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent / "src"))
from tornado_vortex_3d import (
    build_grid_3d, burgers_rott_field, vorticity_3d, kinetic_energy_3d,
    core_vorticity_3d, plot_vortex_3d, GAMMA, RC0, ALPHA, CORE_CENTER_XY,
    DOMAIN_HEIGHT, NX, NY, NZ, AIR_DENSITY, BL_PEAK_HEIGHT
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# ============================================================================
# Method Parameters
# ============================================================================

# 1. REVERSE ROTATION TORQUE: Counter-rotate the entire vortex
REVERSE_TORQUE_STRENGTH = 0.8      # Fraction of local azimuthal velocity to oppose (0-1)
                                    # 0.5 = add 50% opposing rotation
                                    # 1.0 = exact cancellation (zero net rotation)

# 2. DRAG FORCE: Apply velocity-dependent braking throughout the domain
DRAG_COEFFICIENT = 0.15             # Fraction of velocity removed per "time step" (0-1)
                                    # 0.1 = remove 10% of velocity
                                    # 0.5 = remove 50% of velocity


def apply_reverse_rotation_torque(X, Y, Z, u, v, w, center_xy=CORE_CENTER_XY,
                                   strength=REVERSE_TORQUE_STRENGTH):
    """
    Apply a counter-rotating torque that opposes the vortex's azimuthal motion.

    For each point, compute:
    - Local radius vector from vortex axis: (dx, dy)
    - Local azimuthal velocity: v_θ (tangent to circle)
    - Counter-rotation: inject -strength * v_θ in the opposite direction
    """
    cx, cy = center_xy
    dx = X - cx
    dy = Y - cy
    r = np.hypot(dx, dy)
    r_safe = np.where(r < 1e-6, 1e-6, r)

    # Local azimuthal direction (perpendicular to radius, in direction of rotation)
    cos_theta = dx / r_safe
    sin_theta = dy / r_safe

    # Current azimuthal velocity: v_θ = -u·sin(θ) + v·cos(θ)
    v_theta = -u * sin_theta + v * cos_theta

    # Counter-rotation: inject opposite azimuthal velocity
    # v_theta_counter = -strength * v_theta
    u_counter = strength * v_theta * sin_theta
    v_counter = -strength * v_theta * cos_theta

    return u_counter, v_counter


def apply_drag_force(u, v, w, drag_coeff=DRAG_COEFFICIENT):
    """
    Apply velocity-dependent drag force: F = -c·v
    Reduces all velocity components by the drag coefficient.

    This models energy dissipation from friction, viscosity, or injected
    dissipative medium (like aerosol particles).
    """
    u_drag = -drag_coeff * u
    v_drag = -drag_coeff * v
    w_drag = -drag_coeff * w

    return u_drag, v_drag, w_drag


def main():
    print("=" * 70)
    print("DISRUPTION METHOD TEST: REVERSE TORQUE + DRAG FORCE")
    print("=" * 70)

    # Build grid
    X, Y, Z, dx, dy, dz = build_grid_3d()
    z_levels = np.linspace(0.0, DOMAIN_HEIGHT, NZ)

    # ========== BASELINE ==========
    print("\n[1/4] Computing baseline vortex...")
    u0, v0, w0 = burgers_rott_field(X, Y, Z, center_xy=CORE_CENTER_XY, gamma=GAMMA, alpha=ALPHA)

    ke_baseline = kinetic_energy_3d(u0, v0, w0, dx, dy, dz)
    ox0, oy0, oz0 = vorticity_3d(u0, v0, w0, dx, dy, dz)
    core_vort_baseline = core_vorticity_3d(ox0, oy0, oz0, X, Y, Z, center_xy=CORE_CENTER_XY)

    # ========== STEP 1: Apply reverse rotation torque ==========
    print("[2/4] Applying reverse rotation torque...")
    u_torque, v_torque = apply_reverse_rotation_torque(
        X, Y, Z, u0, v0, w0,
        center_xy=CORE_CENTER_XY,
        strength=REVERSE_TORQUE_STRENGTH
    )

    # Apply torque
    u_after_torque = u0 + u_torque
    v_after_torque = v0 + v_torque
    w_after_torque = w0.copy()  # No vertical component in torque

    ke_after_torque = kinetic_energy_3d(u_after_torque, v_after_torque, w_after_torque, dx, dy, dz)

    # ========== STEP 2: Apply drag force ==========
    print("[3/4] Applying drag force to all velocities...")
    u_drag, v_drag, w_drag = apply_drag_force(
        u_after_torque, v_after_torque, w_after_torque,
        drag_coeff=DRAG_COEFFICIENT
    )

    # Apply drag (velocity already reduced by torque, now apply additional drag)
    u_final = u_after_torque + u_drag
    v_final = v_after_torque + v_drag
    w_final = w_after_torque + w_drag

    ke_final = kinetic_energy_3d(u_final, v_final, w_final, dx, dy, dz)
    ox_f, oy_f, oz_f = vorticity_3d(u_final, v_final, w_final, dx, dy, dz)
    core_vort_final = core_vorticity_3d(ox_f, oy_f, oz_f, X, Y, Z, center_xy=CORE_CENTER_XY)

    # ========== RESULTS ==========
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    print(f"\nBASELINE (Undisturbed vortex):")
    print(f"  Kinetic energy:    {ke_baseline:,.2f} J")
    print(f"  Core vorticity:    {core_vort_baseline:.4f} 1/s")

    ke_loss_torque = ke_baseline - ke_after_torque
    pct_loss_torque = 100.0 * ke_loss_torque / ke_baseline
    print(f"\nAFTER REVERSE TORQUE (strength={REVERSE_TORQUE_STRENGTH}):")
    print(f"  Kinetic energy:    {ke_after_torque:,.2f} J")
    print(f"  Energy lost:       {ke_loss_torque:,.2f} J ({pct_loss_torque:.1f}%)")

    ke_loss_total = ke_baseline - ke_final
    pct_loss_total = 100.0 * ke_loss_total / ke_baseline
    pct_vort_remaining = 100.0 * core_vort_final / core_vort_baseline

    print(f"\nFINAL (After drag force, coeff={DRAG_COEFFICIENT}):")
    print(f"  Kinetic energy:    {ke_final:,.2f} J")
    print(f"  Total energy lost: {ke_loss_total:,.2f} J ({pct_loss_total:.1f}%)")
    print(f"  Core vorticity:    {core_vort_final:.4f} 1/s ({pct_vort_remaining:.1f}% of baseline)")

    print("\n" + "=" * 70)
    print("EFFECTIVENESS ASSESSMENT")
    print("=" * 70)

    if pct_loss_total >= 50:
        rating = "✓ DISRUPTS VORTEX (>50% threshold)"
    elif pct_loss_total >= 25:
        rating = "◐ MODERATELY EFFECTIVE (25-50%)"
    else:
        rating = "✗ WEAK EFFECT (<25%)"

    print(f"\nEnergy dissipation: {pct_loss_total:.1f}% → {rating}")
    print(f"Core vorticity retention: {pct_vort_remaining:.1f}%")

    if pct_vort_remaining < 50:
        print("  → VORTEX DISRUPTED ✓")
    elif pct_vort_remaining < 80:
        print("  → Vortex weakened but still coherent")
    else:
        print("  → Vortex largely unaffected")

    print("=" * 70)

    # Save visualization
    plot_vortex_3d(X, Y, Z, u_final, v_final, w_final, CORE_CENTER_XY,
                   (CORE_CENTER_XY[0], CORE_CENTER_XY[1], DOMAIN_HEIGHT/2),  # Plot at vortex center
                   z_levels,
                   save_path=OUTPUT_DIR / "reverse_torque_drag_disruption.png")

    # Save metrics to file
    metrics_file = OUTPUT_DIR / "reverse_torque_drag_metrics.txt"
    with open(metrics_file, "w") as f:
        f.write("REVERSE ROTATION TORQUE + DRAG FORCE DISRUPTION TEST\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Parameters:\n")
        f.write(f"  Reverse torque strength: {REVERSE_TORQUE_STRENGTH}\n")
        f.write(f"  Drag coefficient:        {DRAG_COEFFICIENT}\n\n")
        f.write(f"Baseline KE:       {ke_baseline:,.2f} J\n")
        f.write(f"After torque:      {ke_after_torque:,.2f} J ({pct_loss_torque:.1f}% loss)\n")
        f.write(f"Final (+ drag):    {ke_final:,.2f} J ({pct_loss_total:.1f}% total loss)\n")
        f.write(f"\nBaseline vorticity:  {core_vort_baseline:.4f} 1/s\n")
        f.write(f"Final vorticity:     {core_vort_final:.4f} 1/s ({pct_vort_remaining:.1f}% remaining)\n")
        f.write(f"\nEffectiveness: {rating}\n")
        if pct_loss_total >= 50:
            f.write(f"✓ MEETS 50% THRESHOLD FOR DISRUPTION\n")
        else:
            f.write(f"✗ Below 50% threshold. Need {50 - pct_loss_total:.1f}% more energy dissipation.\n")

    print(f"\nMetrics saved to: {metrics_file}")


if __name__ == "__main__":
    main()
