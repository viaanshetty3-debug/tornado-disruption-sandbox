"""
2D Tornado Vortex Simulation using the Lamb-Oseen vortex model.

Models a rotating wind field, computes its kinetic energy, allows injection
of a counter-directional disruption (e.g. a jet or pressure shock), and
visualizes the resulting flow.
"""

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

# Generated figures are written to the repository's output/ folder
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

# ----------------------------------------------------------------------
# Adjustable parameters
# ----------------------------------------------------------------------

GAMMA = 8000.0          # Circulation strength (m^2/s) - controls rotational intensity
RC = 15.0               # Core radius (m) - radius of maximum tangential velocity
CORE_CENTER = (0.0, 0.0)  # (x, y) location of the vortex core

DOMAIN_HALF_WIDTH = 60.0  # Grid extends from -W to +W in both x and y (m)
GRID_RESOLUTION = 200     # Number of grid points per axis

AIR_DENSITY = 1.225     # kg/m^3, standard atmospheric density at sea level

# Default disruption (counter-force) parameters
DISRUPTION_LOCATION = (25.0, 0.0)  # (x, y) where the counter-force is injected
DISRUPTION_STRENGTH = 45.0         # Peak injected velocity magnitude (m/s)
DISRUPTION_RADIUS = 10.0           # Gaussian falloff radius of the injected force (m)


# ----------------------------------------------------------------------
# Core vortex field
# ----------------------------------------------------------------------

def build_grid(half_width=DOMAIN_HALF_WIDTH, resolution=GRID_RESOLUTION):
    """Create the 2D coordinate grid the vector field is evaluated on."""
    x = np.linspace(-half_width, half_width, resolution)
    y = np.linspace(-half_width, half_width, resolution)
    X, Y = np.meshgrid(x, y)
    dx = x[1] - x[0]
    dy = y[1] - y[0]
    return X, Y, dx, dy


def lamb_oseen_field(X, Y, center=CORE_CENTER, gamma=GAMMA, rc=RC):
    """
    Compute (u, v) velocity components of a Lamb-Oseen vortex.

    v_theta(r) = (Gamma / (2*pi*r)) * (1 - exp(-r^2 / rc^2))
    """
    x0, y0 = center
    dx = X - x0
    dy = Y - y0
    r = np.hypot(dx, dy)
    r_safe = np.where(r < 1e-6, 1e-6, r)

    v_theta = (gamma / (2.0 * np.pi * r_safe)) * (1.0 - np.exp(-(r_safe ** 2) / rc ** 2))

    theta = np.arctan2(dy, dx)
    u = -v_theta * np.sin(theta)
    v = v_theta * np.cos(theta)

    # Velocity is zero exactly at the core center (removable singularity)
    u = np.where(r < 1e-6, 0.0, u)
    v = np.where(r < 1e-6, 0.0, v)
    return u, v


# ----------------------------------------------------------------------
# Counter-force injection
# ----------------------------------------------------------------------

def inject_counterforce(X, Y, location=DISRUPTION_LOCATION, strength=DISRUPTION_STRENGTH,
                         radius=DISRUPTION_RADIUS, direction=None, core_center=CORE_CENTER):
    """
    Inject a localized, Gaussian-weighted velocity field at (x, y) to model
    an opposing jet force or pressure shock disrupting the vortex.

    If `direction` is None, the injected force automatically opposes the
    local tangential rotation of the vortex at that point. Otherwise
    `direction` is an (du, dv) vector giving the injection direction.
    """
    x0, y0 = location
    dx = X - x0
    dy = Y - y0
    envelope = np.exp(-(dx ** 2 + dy ** 2) / (2.0 * radius ** 2))

    if direction is None:
        cx, cy = core_center
        theta0 = np.arctan2(y0 - cy, x0 - cx)
        # Local counterclockwise tangential unit vector is (-sin, cos);
        # the counter-force points opposite to it.
        dir_u, dir_v = np.sin(theta0), -np.cos(theta0)
    else:
        dir_u, dir_v = direction
        norm = np.hypot(dir_u, dir_v)
        dir_u, dir_v = dir_u / norm, dir_v / norm

    u_inject = strength * dir_u * envelope
    v_inject = strength * dir_v * envelope
    return u_inject, v_inject


# ----------------------------------------------------------------------
# Physical metrics
# ----------------------------------------------------------------------

def kinetic_energy(u, v, dx, dy, rho=AIR_DENSITY):
    """
    Total kinetic energy of the field over the grid (per unit depth):
    KE = 0.5 * rho * integral(|velocity|^2) dA
    """
    speed_sq = u ** 2 + v ** 2
    return 0.5 * rho * np.sum(speed_sq) * dx * dy


def vorticity(u, v, dx, dy):
    """2D vorticity (curl_z) = dv/dx - du/dy."""
    dvdx = np.gradient(v, dx, axis=1)
    dudy = np.gradient(u, dy, axis=0)
    return dvdx - dudy


def core_vorticity(vort_field, X, Y, center=CORE_CENTER, radius=RC):
    """Mean vorticity within the vortex core radius - a proxy for core spin strength."""
    dx = X - center[0]
    dy = Y - center[1]
    mask = (dx ** 2 + dy ** 2) <= radius ** 2
    return np.mean(vort_field[mask])


# ----------------------------------------------------------------------
# Visualization
# ----------------------------------------------------------------------

def plot_vortex(X, Y, u, v, u0, v0, core_center, disruption_location):
    """Side-by-side streamplot of the disrupted flow and heatmap of wind speed."""
    speed = np.hypot(u, v)

    fig, (ax_stream, ax_heat) = plt.subplots(1, 2, figsize=(14, 6))

    # --- Left: streamplot of the (possibly disrupted) vector field ---
    strm = ax_stream.streamplot(
        X, Y, u, v,
        color=speed, cmap="viridis", density=1.6, linewidth=1.2, arrowsize=1
    )
    ax_stream.plot(*core_center, marker="o", color="white", markeredgecolor="black",
                    markersize=9, label="Vortex core")
    ax_stream.plot(*disruption_location, marker="X", color="red", markeredgecolor="black",
                    markersize=10, label="Injected counter-force")
    ax_stream.set_title("Wind Vector Field (streamlines)")
    ax_stream.set_xlabel("x (m)")
    ax_stream.set_ylabel("y (m)")
    ax_stream.set_aspect("equal")
    ax_stream.legend(loc="upper right", framealpha=0.9)
    fig.colorbar(strm.lines, ax=ax_stream, label="Wind speed (m/s)")

    # --- Right: heatmap of wind speed magnitude ---
    heat = ax_heat.pcolormesh(X, Y, speed, cmap="viridis", shading="auto")
    ax_heat.plot(*core_center, marker="o", color="white", markeredgecolor="black", markersize=9)
    ax_heat.plot(*disruption_location, marker="X", color="red", markeredgecolor="black", markersize=10)
    ax_heat.set_title("Wind Speed Magnitude")
    ax_heat.set_xlabel("x (m)")
    ax_heat.set_ylabel("y (m)")
    ax_heat.set_aspect("equal")
    fig.colorbar(heat, ax=ax_heat, label="Speed (m/s)")

    fig.suptitle("2D Tornado Vortex: Lamb-Oseen Model with Disruption Event", fontsize=14)
    fig.tight_layout()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_path = OUTPUT_DIR / "tornado_vortex_2d.png"
    fig.savefig(save_path, dpi=150)
    print(f"\nFigure saved to: {save_path}")
    plt.show()


# ----------------------------------------------------------------------
# Main simulation
# ----------------------------------------------------------------------

def main():
    X, Y, dx, dy = build_grid()

    # Baseline vortex
    u0, v0 = lamb_oseen_field(X, Y, center=CORE_CENTER, gamma=GAMMA, rc=RC)
    ke_initial = kinetic_energy(u0, v0, dx, dy)
    vort0 = vorticity(u0, v0, dx, dy)
    core_vort_initial = core_vorticity(vort0, X, Y, center=CORE_CENTER, radius=RC)

    # Counter-force injection
    u_inject, v_inject = inject_counterforce(
        X, Y,
        location=DISRUPTION_LOCATION,
        strength=DISRUPTION_STRENGTH,
        radius=DISRUPTION_RADIUS,
        core_center=CORE_CENTER,
    )
    ke_injected = kinetic_energy(u_inject, v_inject, dx, dy)

    # Combined (disrupted) field
    u = u0 + u_inject
    v = v0 + v_inject
    vort_after = vorticity(u, v, dx, dy)
    core_vort_after = core_vorticity(vort_after, X, Y, center=CORE_CENTER, radius=RC)

    remaining_pct = 100.0 * core_vort_after / core_vort_initial

    # --- Console metrics ---
    print("=" * 50)
    print("TORNADO VORTEX SIMULATION METRICS")
    print("=" * 50)
    print(f"Circulation strength (Gamma): {GAMMA:.1f} m^2/s")
    print(f"Core radius (rc):             {RC:.1f} m")
    print(f"Air density:                  {AIR_DENSITY:.3f} kg/m^3")
    print("-" * 50)
    print(f"Initial vortex kinetic energy:   {ke_initial:,.2f} J/m")
    print(f"Injected counter-force energy:   {ke_injected:,.2f} J/m")
    print(f"Energy ratio (injection/vortex): {100 * ke_injected / ke_initial:.2f} %")
    print("-" * 50)
    print(f"Core vorticity before disruption: {core_vort_initial:.4f} 1/s")
    print(f"Core vorticity after disruption:  {core_vort_after:.4f} 1/s")
    print(f"Remaining core vorticity:          {remaining_pct:.2f} %")
    print("=" * 50)

    plot_vortex(X, Y, u, v, u0, v0, CORE_CENTER, DISRUPTION_LOCATION)


if __name__ == "__main__":
    main()
