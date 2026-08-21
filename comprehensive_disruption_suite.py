"""
Comprehensive Tornado Disruption Analysis Suite

Tests multiple disruption methods and combinations to find:
1. Minimum effective parameters
2. Synergies between methods
3. Efficiency frontiers (energy loss vs. practical feasibility)
4. Novel mechanisms
"""

from pathlib import Path
import sys
import numpy as np
import json

sys.path.insert(0, str(Path(__file__).parent / "src"))
from tornado_vortex_3d import (
    build_grid_3d, burgers_rott_field, vorticity_3d, kinetic_energy_3d,
    core_vorticity_3d, GAMMA, RC0, ALPHA, CORE_CENTER_XY,
    DOMAIN_HEIGHT, NX, NY, NZ, AIR_DENSITY, BL_PEAK_HEIGHT
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


# ============================================================================
# DISRUPTION MECHANISMS
# ============================================================================

def apply_reverse_rotation_torque(X, Y, Z, u, v, w, center_xy=CORE_CENTER_XY, strength=1.0):
    """Apply counter-rotating azimuthal velocity."""
    cx, cy = center_xy
    dx = X - cx
    dy = Y - cy
    r = np.hypot(dx, dy)
    r_safe = np.where(r < 1e-6, 1e-6, r)

    cos_theta = dx / r_safe
    sin_theta = dy / r_safe
    v_theta = -u * sin_theta + v * cos_theta

    u_counter = strength * v_theta * sin_theta
    v_counter = -strength * v_theta * cos_theta
    return u_counter, v_counter


def apply_drag_force(u, v, w, drag_coeff=0.15):
    """Apply velocity-dependent drag."""
    return -drag_coeff * u, -drag_coeff * v, -drag_coeff * w


def apply_core_targeting(u, v, w, X, Y, Z, center_xy=CORE_CENTER_XY, core_radius=20.0, strength=1.0):
    """Apply disruption only within the vortex core (r <= core_radius)."""
    cx, cy = center_xy
    r = np.hypot(X - cx, Y - cy)
    mask = r <= core_radius

    u_dis = u.copy()
    v_dis = v.copy()
    u_dis[mask] *= (1.0 - strength)
    v_dis[mask] *= (1.0 - strength)
    return u_dis, v_dis, w


def apply_altitude_targeting(u, v, w, Z, z_min=50.0, z_max=150.0, strength=1.0):
    """Apply disruption only within altitude band."""
    mask = (Z >= z_min) & (Z <= z_max)
    u_dis = u.copy()
    v_dis = v.copy()
    u_dis[mask] *= (1.0 - strength)
    v_dis[mask] *= (1.0 - strength)
    return u_dis, v_dis, w


def apply_pressure_pulse(X, Y, Z, u, v, w, center=(0, 0, 100), strength=50.0, radius=25.0):
    """
    Apply radial outward velocity (simulating pressure pulse).
    Models explosive expansion from the core.
    """
    cx, cy, cz = center
    dx = X - cx
    dy = Y - cy
    dz = Z - cz
    dist_sq = dx**2 + dy**2 + dz**2
    dist = np.sqrt(dist_sq + 1e-6)

    envelope = np.exp(-dist_sq / (2.0 * radius**2))

    u_pulse = strength * (dx / dist) * envelope
    v_pulse = strength * (dy / dist) * envelope
    w_pulse = strength * (dz / dist) * envelope

    return u_pulse, v_pulse, w_pulse


def apply_vertical_shear(u, v, w, Z, height=DOMAIN_HEIGHT, strength=1.0):
    """
    Apply opposing vertical shear: lower levels spin one way, upper levels opposite.
    Models differential heating or wind shear.
    """
    # Normalize z to 0-1
    z_norm = Z / height

    # Shear magnitude increases with height
    shear_factor = 2.0 * (z_norm - 0.5) * strength

    # Apply differential rotation
    u_shear = shear_factor * v
    v_shear = -shear_factor * u

    return u_shear, v_shear, np.zeros_like(w)


# ============================================================================
# TEST SUITE
# ============================================================================

class DisruptionTest:
    """Single disruption test with metrics."""

    def __init__(self, name, u0, v0, w0, X, Y, Z, dx, dy, dz, center_xy=CORE_CENTER_XY):
        self.name = name
        self.u0 = u0
        self.v0 = v0
        self.w0 = w0
        self.X = X
        self.Y = Y
        self.Z = Z
        self.dx = dx
        self.dy = dy
        self.dz = dz
        self.center_xy = center_xy

        self.ke_baseline = kinetic_energy_3d(u0, v0, w0, dx, dy, dz)
        ox0, oy0, oz0 = vorticity_3d(u0, v0, w0, dx, dy, dz)
        self.vort_baseline = core_vorticity_3d(ox0, oy0, oz0, X, Y, Z, center_xy)

    def run(self, u_final, v_final, w_final):
        """Compute metrics for disrupted field."""
        ke_final = kinetic_energy_3d(u_final, v_final, w_final, self.dx, self.dy, self.dz)
        ox_f, oy_f, oz_f = vorticity_3d(u_final, v_final, w_final, self.dx, self.dy, self.dz)
        vort_final = core_vorticity_3d(ox_f, oy_f, oz_f, self.X, self.Y, self.Z, self.center_xy)

        energy_loss_pct = 100.0 * (1.0 - ke_final / self.ke_baseline)
        vort_retained_pct = 100.0 * vort_final / self.vort_baseline

        return {
            'name': self.name,
            'ke_final': ke_final,
            'vort_retained': vort_retained_pct,
            'energy_loss': energy_loss_pct,
            'disrupted': energy_loss_pct >= 50.0
        }


def main():
    print("=" * 80)
    print("COMPREHENSIVE TORNADO DISRUPTION ANALYSIS SUITE")
    print("=" * 80)

    # Setup
    X, Y, Z, dx, dy, dz = build_grid_3d()
    u0, v0, w0 = burgers_rott_field(X, Y, Z, center_xy=CORE_CENTER_XY, gamma=GAMMA, alpha=ALPHA)

    ke_baseline = kinetic_energy_3d(u0, v0, w0, dx, dy, dz)
    print(f"\nBaseline kinetic energy: {ke_baseline:,.0f} J")

    results = []

    # ========== 1. REVERSE TORQUE OPTIMIZATION ==========
    print("\n" + "=" * 80)
    print("1. REVERSE TORQUE STRENGTH OPTIMIZATION")
    print("=" * 80)

    test = DisruptionTest("Reverse Torque Optimization", u0, v0, w0, X, Y, Z, dx, dy, dz)

    for strength in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        u_torque, v_torque = apply_reverse_rotation_torque(X, Y, Z, u0, v0, w0, strength=strength)
        u_dis = u0 + u_torque
        v_dis = v0 + v_torque
        result = test.run(u_dis, v_dis, w0)
        result['param'] = f"strength={strength}"
        results.append(result)

        status = "✓ DISRUPTS" if result['disrupted'] else "✗ Weak"
        print(f"  Strength {strength:.1f}: {result['energy_loss']:.1f}% loss, {result['vort_retained']:.1f}% vort → {status}")

    # ========== 2. HYBRID METHODS ==========
    print("\n" + "=" * 80)
    print("2. HYBRID METHOD COMBINATIONS")
    print("=" * 80)

    test = DisruptionTest("Hybrid Methods", u0, v0, w0, X, Y, Z, dx, dy, dz)

    # Torque + Drag
    u_torque, v_torque = apply_reverse_rotation_torque(X, Y, Z, u0, v0, w0, strength=0.5)
    u_hybrid = u0 + u_torque
    v_hybrid = v0 + v_torque
    u_drag, v_drag, w_drag = apply_drag_force(u_hybrid, v_hybrid, w0, drag_coeff=0.1)
    u_hybrid += u_drag
    v_hybrid += v_drag
    result = test.run(u_hybrid, v_hybrid, w0 + w_drag)
    result['param'] = "Torque(0.5) + Drag(0.1)"
    results.append(result)
    print(f"  Torque(0.5) + Drag(0.1): {result['energy_loss']:.1f}% loss → {'✓' if result['disrupted'] else '✗'}")

    # Torque + Pressure Pulse
    u_torque, v_torque = apply_reverse_rotation_torque(X, Y, Z, u0, v0, w0, strength=0.4)
    u_pulse, v_pulse, w_pulse = apply_pressure_pulse(X, Y, Z, u0, v0, w0, strength=30.0)
    u_hybrid = u0 + u_torque + u_pulse
    v_hybrid = v0 + v_torque + v_pulse
    result = test.run(u_hybrid, v_hybrid, w0 + w_pulse)
    result['param'] = "Torque(0.4) + Pressure(30)"
    results.append(result)
    print(f"  Torque(0.4) + Pressure(30): {result['energy_loss']:.1f}% loss → {'✓' if result['disrupted'] else '✗'}")

    # ========== 3. TARGETED DISRUPTION ==========
    print("\n" + "=" * 80)
    print("3. TARGETED DISRUPTION (Core-Only vs Altitude Band)")
    print("=" * 80)

    test = DisruptionTest("Targeted Disruption", u0, v0, w0, X, Y, Z, dx, dy, dz)

    # Core-only torque
    u_dis, v_dis, w_dis = apply_core_targeting(u0, v0, w0, X, Y, Z, core_radius=20.0, strength=0.8)
    result = test.run(u_dis, v_dis, w_dis)
    result['param'] = "Core-only torque (r<20m, 80%)"
    results.append(result)
    print(f"  Core-only (r<20m, 80%): {result['energy_loss']:.1f}% loss → {'✓' if result['disrupted'] else '✗'}")

    # Altitude band torque
    u_dis, v_dis, w_dis = apply_altitude_targeting(u0, v0, w0, Z, z_min=50, z_max=150, strength=0.7)
    result = test.run(u_dis, v_dis, w_dis)
    result['param'] = "Altitude band (50-150m, 70%)"
    results.append(result)
    print(f"  Altitude band (50-150m, 70%): {result['energy_loss']:.1f}% loss → {'✓' if result['disrupted'] else '✗'}")

    # ========== 4. NOVEL MECHANISMS ==========
    print("\n" + "=" * 80)
    print("4. NOVEL MECHANISMS")
    print("=" * 80)

    test = DisruptionTest("Novel Mechanisms", u0, v0, w0, X, Y, Z, dx, dy, dz)

    # Pressure pulse alone
    u_pulse, v_pulse, w_pulse = apply_pressure_pulse(X, Y, Z, u0, v0, w0, strength=50.0, radius=30.0)
    result = test.run(u0 + u_pulse, v0 + v_pulse, w0 + w_pulse)
    result['param'] = "Pressure pulse (strength=50)"
    results.append(result)
    print(f"  Pressure pulse (50): {result['energy_loss']:.1f}% loss → {'✓' if result['disrupted'] else '✗'}")

    # Vertical shear
    u_shear, v_shear, w_shear = apply_vertical_shear(u0, v0, w0, Z, strength=0.8)
    result = test.run(u0 + u_shear, v0 + v_shear, w0 + w_shear)
    result['param'] = "Vertical shear (0.8)"
    results.append(result)
    print(f"  Vertical shear (0.8): {result['energy_loss']:.1f}% loss → {'✓' if result['disrupted'] else '✗'}")

    # ========== SUMMARY ==========
    print("\n" + "=" * 80)
    print("SUMMARY TABLE")
    print("=" * 80)

    results_sorted = sorted(results, key=lambda x: x['energy_loss'], reverse=True)

    print(f"\n{'Method':<35} {'Energy Loss':<15} {'Vort Retained':<15} {'Status':<10}")
    print("-" * 75)

    for r in results_sorted:
        status = "✓ WORKS" if r['disrupted'] else "Too weak"
        print(f"{r['param']:<35} {r['energy_loss']:>6.1f}%{'':<8} {r['vort_retained']:>6.1f}%{'':<8} {status:<10}")

    # Save results
    output_file = OUTPUT_DIR / "comprehensive_analysis_results.json"
    with open(output_file, "w") as f:
        json.dump(results_sorted, f, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")

    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    effective = [r for r in results if r['disrupted']]
    if effective:
        most_efficient = min(effective, key=lambda x: x['energy_loss'])
        print(f"\n✓ Most efficient method (meets 50% threshold):")
        print(f"  {most_efficient['param']}: {most_efficient['energy_loss']:.1f}% energy loss")

    print("\n✓ Most practical (lowest energy, core-targeted):")
    print("  Core-only targeting can reduce energy input needed")

    print("\n✓ Most robust (hybrid methods):")
    print("  Combining mechanisms provides redundancy and margin")


if __name__ == "__main__":
    main()
