"""
Threshold analysis: How much energy must be removed to disrupt the vortex?

Tests a range of uniform energy dissipation levels (25%, 50%, 75%, 90%)
to find where the vortex transitions from "weakened but stable" to "disrupted".
"""

from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "src"))
from tornado_vortex_3d import (
    build_grid_3d, burgers_rott_field, vorticity_3d, kinetic_energy_3d,
    core_vorticity_3d, GAMMA, RC0, ALPHA, CORE_CENTER_XY,
    DOMAIN_HEIGHT, NX, NY, NZ, AIR_DENSITY, BL_PEAK_HEIGHT
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def dissipate_energy_uniformly(u, v, w, retention_fraction):
    """
    Scale all velocity components by retention_fraction.
    retention_fraction=1.0 → no dissipation
    retention_fraction=0.5 → 50% energy loss
    retention_fraction=0.1 → 90% energy loss
    """
    return u * retention_fraction, v * retention_fraction, w * retention_fraction


def assess_vortex_stability(core_vorticity_initial, core_vorticity_final):
    """
    Classify vortex state based on remaining core vorticity.
    """
    fraction_remaining = core_vorticity_final / core_vorticity_initial

    if fraction_remaining > 0.9:
        return "INTACT", "Nearly unaffected; vortex maintained"
    elif fraction_remaining > 0.7:
        return "WEAKENED", "Noticeably weaker; still spinning coherently"
    elif fraction_remaining > 0.5:
        return "UNSTABLE", "Significantly degraded; marginal coherence"
    elif fraction_remaining > 0.2:
        return "SEVERELY DISRUPTED", "Core destroyed; residual circulation"
    else:
        return "COLLAPSED", "Vortex structure completely broken"


def main():
    print("=" * 80)
    print("TORNADO DISRUPTION THRESHOLD ANALYSIS")
    print("=" * 80)

    # Build grid and baseline
    X, Y, Z, dx, dy, dz = build_grid_3d()
    u0, v0, w0 = burgers_rott_field(X, Y, Z, center_xy=CORE_CENTER_XY, gamma=GAMMA, alpha=ALPHA)

    ke_baseline = kinetic_energy_3d(u0, v0, w0, dx, dy, dz)
    ox0, oy0, oz0 = vorticity_3d(u0, v0, w0, dx, dy, dz)
    core_vort_baseline = core_vorticity_3d(ox0, oy0, oz0, X, Y, Z, center_xy=CORE_CENTER_XY)

    print(f"\nBASELINE TORNADO:")
    print(f"  Kinetic energy:  {ke_baseline:,.0f} J")
    print(f"  Core vorticity:  {core_vort_baseline:.4f} 1/s")
    print(f"\n" + "=" * 80)
    print("DISRUPTION THRESHOLD TESTS")
    print("=" * 80)

    # Test different energy removal levels
    test_levels = [
        (0.75, "25% energy loss"),
        (0.50, "50% energy loss"),
        (0.25, "75% energy loss"),
        (0.10, "90% energy loss"),
    ]

    results = []

    for retention, label in test_levels:
        u_dis, v_dis, w_dis = dissipate_energy_uniformly(u0, v0, w0, retention)

        ke_after = kinetic_energy_3d(u_dis, v_dis, w_dis, dx, dy, dz)
        ox, oy, oz = vorticity_3d(u_dis, v_dis, w_dis, dx, dy, dz)
        core_vort_after = core_vorticity_3d(ox, oy, oz, X, Y, Z, center_xy=CORE_CENTER_XY)

        energy_loss_pct = 100.0 * (1.0 - retention)
        vort_retained_pct = 100.0 * core_vort_after / core_vort_baseline

        state, description = assess_vortex_stability(core_vort_baseline, core_vort_after)

        results.append({
            'energy_loss': energy_loss_pct,
            'ke_after': ke_after,
            'vort_retained': vort_retained_pct,
            'state': state,
            'description': description,
        })

        print(f"\n{label}:")
        print(f"  Energy after:        {ke_after:,.0f} J")
        print(f"  Core vorticity:      {core_vort_after:.4f} 1/s ({vort_retained_pct:.1f}% retained)")
        print(f"  Status:              {state}")
        print(f"  → {description}")

    print("\n" + "=" * 80)
    print("DISRUPTION THRESHOLD SUMMARY")
    print("=" * 80)

    # Find the threshold
    critical_threshold = None
    for result in results:
        if result['state'] in ["UNSTABLE", "SEVERELY DISRUPTED", "COLLAPSED"]:
            if critical_threshold is None:
                critical_threshold = result['energy_loss']

    if critical_threshold:
        print(f"\n🔴 CRITICAL THRESHOLD: {critical_threshold:.0f}% energy loss")
        print(f"   → Vortex transitions from 'weakened but stable' to 'disrupted'")
    else:
        print("\n⚠️  No clear threshold reached in test range")

    print(f"\n{'RECOMMENDATION:':20} Remove at least {critical_threshold:.0f}% of tornado's kinetic energy")
    print(f"{'For your method':20} You currently achieve only 15.2% — need {critical_threshold - 15.2:.0f}% more")

    print("\n" + "=" * 80)
    print("ENERGY REQUIREMENTS BY DISRUPTION LEVEL")
    print("=" * 80)
    print(f"\nTo disrupt a {ke_baseline/1e9:.1f} GJ tornado:")
    for energy_pct in [25, 50, 75, 90]:
        energy_joules = (energy_pct / 100.0) * ke_baseline
        print(f"  {energy_pct}% loss = {energy_joules/1e9:.2f} GJ")

    # Save results
    metrics_file = OUTPUT_DIR / "disruption_threshold_analysis.txt"
    with open(metrics_file, "w") as f:
        f.write("TORNADO DISRUPTION THRESHOLD ANALYSIS\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Baseline KE:  {ke_baseline:,.0f} J\n")
        f.write(f"Baseline vorticity: {core_vort_baseline:.4f} 1/s\n\n")
        f.write("RESULTS:\n")
        for result in results:
            f.write(f"\n{result['energy_loss']:.0f}% energy loss:\n")
            f.write(f"  Vorticity retained: {result['vort_retained']:.1f}%\n")
            f.write(f"  State: {result['state']}\n")
        if critical_threshold:
            f.write(f"\nCRITICAL THRESHOLD: {critical_threshold:.0f}% energy loss\n")

    print(f"\nMetrics saved to: {metrics_file}")


if __name__ == "__main__":
    main()
