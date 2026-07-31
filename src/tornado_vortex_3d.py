"""
3D Tornado Vortex Simulation using an approximate Burgers-Rott vortex structure.

Extends the 2D Lamb-Oseen model into a full 3D volume: horizontal rotation
(u, v) that varies with altitude like a boundary-layer wind-speed jet, a
radial inflow that feeds a vertically stretching updraft (w), following the
classic Burgers vortex stretching term combined with a Rott-style near-surface
boundary-layer profile. A 3D counter-force (jet / pressure shock) can be
injected at any (x, y, z) with an arbitrary 3D direction vector.

NOTE: This is a simplified, illustrative implementation of the Burgers-Rott
structure (not an exact solution of Rott's boundary-layer similarity
equations) - it reproduces the qualitative features requested: tangential
wind that scales with altitude, and an updraft that accelerates upward.
"""

from pathlib import Path

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (registers 3D projection)

# Generated figures are written to the repository's output/ folder
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

# ----------------------------------------------------------------------
# Adjustable parameters
# ----------------------------------------------------------------------

GAMMA = 8000.0            # Reference circulation strength (m^2/s)
RC0 = 15.0                # Core radius at the surface (m)
FUNNEL_WIDENING = 0.8     # Fractional core-radius growth from surface to domain top (funnel flare)
BL_PEAK_HEIGHT = 40.0     # Altitude of maximum tangential wind - boundary-layer jet height (m)
ALPHA = 0.03              # Burgers vertical-stretching / radial-convergence rate (1/s)

CORE_CENTER_XY = (0.0, 0.0)   # (x, y) location of the vortex axis

DOMAIN_HALF_WIDTH = 60.0   # Horizontal grid extends from -W to +W in x and y (m)
DOMAIN_HEIGHT = 300.0      # Vertical grid extends from 0 to this altitude (m), up to cloud base
NX, NY, NZ = 36, 36, 24    # Grid resolution per axis

AIR_DENSITY = 1.225        # kg/m^3, standard atmospheric density at sea level

# Default 3D disruption (counter-force) parameters
DISRUPTION_LOCATION = (25.0, 0.0, 80.0)  # (x, y, z) where the counter-force is injected
DISRUPTION_STRENGTH = 45.0               # Peak injected velocity magnitude (m/s) - used only when `direction` is explicit
DISRUPTION_RADIUS = 15.0                 # Gaussian falloff radius of the injected force (m)
DISRUPTION_DIRECTION = None              # (dx, dy, dz) or None to auto-oppose the local flow, per-cell
DISRUPTION_CANCEL_FRACTION = 1.0         # Fraction of the local flow canceled at the injection center
                                          # when direction=None (1.0 = exact cancellation at the marker,
                                          # >1.0 = local flow reversal)


# ----------------------------------------------------------------------
# Grid
# ----------------------------------------------------------------------

def build_grid_3d(half_width=DOMAIN_HALF_WIDTH, height=DOMAIN_HEIGHT, nx=NX, ny=NY, nz=NZ):
    """Create the 3D coordinate grid the vector field is evaluated on."""
    x = np.linspace(-half_width, half_width, nx)
    y = np.linspace(-half_width, half_width, ny)
    z = np.linspace(0.0, height, nz)
    X, Y, Z = np.meshgrid(x, y, z, indexing="ij")
    dx = x[1] - x[0]
    dy = y[1] - y[0]
    dz = z[1] - z[0]
    return X, Y, Z, dx, dy, dz


# ----------------------------------------------------------------------
# Burgers-Rott 3D vortex field
# ----------------------------------------------------------------------

def core_radius_profile(Z, rc0=RC0, height=DOMAIN_HEIGHT, widening=FUNNEL_WIDENING):
    """Core radius grows with altitude, producing a widening funnel shape."""
    return rc0 * (1.0 + widening * (Z / height))


def boundary_layer_profile(Z, peak_height=BL_PEAK_HEIGHT):
    """
    Height-scaling factor for tangential wind: rises from zero at the surface
    to a peak within the boundary layer (z = peak_height), then relaxes above
    it - approximating the Rott near-surface tangential wind jet.
    """
    z_safe = np.maximum(Z, 1e-6)
    return (z_safe / peak_height) * np.exp(1.0 - z_safe / peak_height)


def burgers_rott_field(X, Y, Z, center_xy=CORE_CENTER_XY, gamma=GAMMA, alpha=ALPHA):
    """
    Compute (u, v, w) velocity components of the 3D vortex.

    - Tangential speed follows a Lamb-Oseen radial profile, scaled by
      `boundary_layer_profile(Z)` so rotation varies with altitude.
    - Radial inflow (Burgers convergence) feeds the core and decays with
      height as it is consumed by the updraft.
    - Vertical velocity w = alpha * z (Burgers vertical-stretching term),
      concentrated near the vortex core and accelerating upward.
    """
    x0, y0 = center_xy
    dx = X - x0
    dy = Y - y0
    r = np.hypot(dx, dy)
    r_safe = np.where(r < 1e-6, 1e-6, r)
    theta = np.arctan2(dy, dx)

    rc_z = core_radius_profile(Z)
    height_scale = boundary_layer_profile(Z)

    v_theta = (gamma / (2.0 * np.pi * r_safe)) * (1.0 - np.exp(-(r_safe ** 2) / rc_z ** 2)) * height_scale
    v_r = -(alpha * r_safe / 2.0) * np.exp(-Z / (2.0 * BL_PEAK_HEIGHT))

    u = v_r * np.cos(theta) - v_theta * np.sin(theta)
    v = v_r * np.sin(theta) + v_theta * np.cos(theta)
    w = alpha * Z * np.exp(-(r_safe ** 2) / rc_z ** 2)

    # Horizontal velocity is zero exactly on the vortex axis (removable singularity)
    u = np.where(r < 1e-6, 0.0, u)
    v = np.where(r < 1e-6, 0.0, v)
    return u, v, w


# ----------------------------------------------------------------------
# 3D counter-force injection
# ----------------------------------------------------------------------

def inject_counterforce_3d(X, Y, Z, location=DISRUPTION_LOCATION, radius=DISRUPTION_RADIUS,
                            strength=DISRUPTION_STRENGTH, cancel_fraction=DISRUPTION_CANCEL_FRACTION,
                            direction=DISRUPTION_DIRECTION, base_field=None):
    """
    Inject a localized, Gaussian-weighted velocity field at 3D point (x, y, z)
    to model an opposing jet force or pressure shock disrupting the vortex.

    If `direction` is None (the default), the injected vector is computed
    PER GRID CELL as `-cancel_fraction * envelope * (u_local, v_local, w_local)`,
    i.e. it dynamically opposes the actual background velocity at every point
    inside the Gaussian influence radius, not just a single direction sampled
    at the injection center. Because the Gaussian envelope peaks exactly at
    (x0, y0, z0), the cancellation is deepest there by construction - with
    cancel_fraction=1.0 the combined velocity at that cell is exactly zero -
    so the resulting low-speed notch is guaranteed to be centered on the
    injection coordinates rather than drifting off due to the background
    flow's direction varying across the blob.

    If `direction` is an explicit (dx, dy, dz) vector, the injected field
    instead uses that single fixed direction scaled by `strength` (m/s) and
    the Gaussian envelope, as before.
    """
    x0, y0, z0 = location
    dx = X - x0
    dy = Y - y0
    dz = Z - z0
    dist_sq = dx ** 2 + dy ** 2 + dz ** 2
    envelope = np.exp(-dist_sq / (2.0 * radius ** 2))

    if direction is None:
        if base_field is None:
            raise ValueError("base_field=(u0, v0, w0) is required when direction is None")
        u0, v0, w0 = base_field
        u_inject = -cancel_fraction * envelope * u0
        v_inject = -cancel_fraction * envelope * v0
        w_inject = -cancel_fraction * envelope * w0
    else:
        dir_vec = np.asarray(direction, dtype=float)
        dir_vec = dir_vec / np.linalg.norm(dir_vec)
        u_inject = strength * dir_vec[0] * envelope
        v_inject = strength * dir_vec[1] * envelope
        w_inject = strength * dir_vec[2] * envelope

    return u_inject, v_inject, w_inject


# ----------------------------------------------------------------------
# Physical metrics (integrated over the full 3D volume)
# ----------------------------------------------------------------------

def kinetic_energy_3d(u, v, w, dx, dy, dz, rho=AIR_DENSITY):
    """Total kinetic energy of the field over the volume: KE = 0.5 * rho * integral(|velocity|^2) dV"""
    speed_sq = u ** 2 + v ** 2 + w ** 2
    return 0.5 * rho * np.sum(speed_sq) * dx * dy * dz


def vorticity_3d(u, v, w, dx, dy, dz):
    """Full 3D vorticity vector (curl of the velocity field)."""
    dudy = np.gradient(u, dy, axis=1)
    dudz = np.gradient(u, dz, axis=2)
    dvdx = np.gradient(v, dx, axis=0)
    dvdz = np.gradient(v, dz, axis=2)
    dwdx = np.gradient(w, dx, axis=0)
    dwdy = np.gradient(w, dy, axis=1)

    omega_x = dwdy - dvdz
    omega_y = dudz - dwdx
    omega_z = dvdx - dudy
    return omega_x, omega_y, omega_z


def core_vorticity_3d(omega_x, omega_y, omega_z, X, Y, Z, center_xy=CORE_CENTER_XY):
    """Mean vorticity magnitude within the core funnel (r <= rc(z)), averaged over all altitudes."""
    cx, cy = center_xy
    r = np.hypot(X - cx, Y - cy)
    rc_z = core_radius_profile(Z)
    mask = r <= rc_z
    magnitude = np.sqrt(omega_x ** 2 + omega_y ** 2 + omega_z ** 2)
    return np.mean(magnitude[mask])


def local_shear_vorticity(omega_x, omega_y, omega_z, X, Y, Z, center, radius):
    """
    Mean vorticity magnitude within a sphere of `radius` around `center` (x, y, z).

    Unlike `core_vorticity_3d` (which measures spin about the vortex axis),
    this measures the shear/turbulence generated locally by a disruption -
    useful for detecting the shear layer that forms when an overcancelling
    counter-force (cancel_fraction > 1) reverses the flow inside its footprint,
    creating a small counter-rotating eddy at the boundary of the injection.
    """
    cx, cy, cz = center
    dist_sq = (X - cx) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2
    mask = dist_sq <= radius ** 2
    magnitude = np.sqrt(omega_x ** 2 + omega_y ** 2 + omega_z ** 2)
    return np.mean(magnitude[mask])


# ----------------------------------------------------------------------
# Visualization
# ----------------------------------------------------------------------

def plot_vortex_3d(X, Y, Z, u, v, w, core_center_xy, disruption_location,
                    z_levels, save_path=None):
    """
    Side-by-side figure:
      (a) 3D quiver plot of the spiraling vortex, colored by wind speed.
      (b) 2D horizontal cross-section heatmap at the injection altitude.
    """
    speed = np.sqrt(u ** 2 + v ** 2 + w ** 2)
    norm = mcolors.Normalize(vmin=speed.min(), vmax=speed.max())
    cmap = matplotlib.colormaps["viridis"]

    fig = plt.figure(figsize=(15, 7))

    # --- Left: 3D quiver plot (subsampled for readability) ---
    ax3d = fig.add_subplot(1, 2, 1, projection="3d")
    step_xy = max(1, X.shape[0] // 10)
    step_z = max(1, X.shape[2] // 8)
    sl = (slice(None, None, step_xy), slice(None, None, step_xy), slice(None, None, step_z))

    Xs, Ys, Zs = X[sl], Y[sl], Z[sl]
    Us, Vs, Ws = u[sl], v[sl], w[sl]
    Ss = speed[sl]

    arrow_colors = cmap(norm(Ss.flatten()))
    # matplotlib draws each 3D arrow as 3 line segments (shaft + 2 head lines);
    # Line3DCollection needs one color per segment.
    quiver_colors = np.concatenate([arrow_colors, np.repeat(arrow_colors, 2, axis=0)], axis=0)

    q = ax3d.quiver(Xs, Ys, Zs, Us, Vs, Ws, length=6.0, normalize=True)
    q.set_color(quiver_colors)

    x0, y0, z0 = disruption_location
    ax3d.scatter(*core_center_xy, 0, color="white", edgecolor="black", s=60, label="Vortex axis (surface)")
    ax3d.scatter(x0, y0, z0, color="red", marker="X", s=80, label="Injected counter-force")
    ax3d.set_title("3D Vortex Structure (quiver, colored by speed)")
    ax3d.set_xlabel("x (m)")
    ax3d.set_ylabel("y (m)")
    ax3d.set_zlabel("z (m, altitude)")
    ax3d.legend(loc="upper left")

    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    fig.colorbar(sm, ax=ax3d, shrink=0.7, pad=0.1, label="Wind speed (m/s)")

    # --- Right: 2D horizontal cross-section at the injection altitude ---
    iz = int(np.argmin(np.abs(z_levels - z0)))
    Xh, Yh = X[:, :, iz], Y[:, :, iz]
    speed_h = speed[:, :, iz]

    # Locate the peak attenuation point (minimum speed) directly from the data,
    # so the marker is guaranteed to sit exactly on the low-speed notch instead
    # of just trusting the nominal injection coordinates.
    min_idx = np.unravel_index(np.argmin(speed_h), speed_h.shape)
    x_notch, y_notch = Xh[min_idx], Yh[min_idx]

    ax2d = fig.add_subplot(1, 2, 2)
    heat = ax2d.pcolormesh(Xh, Yh, speed_h, cmap="viridis", shading="auto")
    ax2d.plot(*core_center_xy, marker="o", color="white", markeredgecolor="black", markersize=9,
              label="Vortex axis")
    ax2d.plot(x_notch, y_notch, marker="X", color="red", markeredgecolor="black", markersize=10,
              label="Peak attenuation (disruption core)")
    ax2d.legend(loc="upper right", framealpha=0.9, fontsize=8)
    ax2d.set_title(f"Horizontal Cross-Section at z = {z_levels[iz]:.0f} m")
    ax2d.set_xlabel("x (m)")
    ax2d.set_ylabel("y (m)")
    ax2d.set_aspect("equal")
    fig.colorbar(heat, ax=ax2d, label="Speed (m/s)")

    fig.suptitle("3D Tornado Vortex: Burgers-Rott Model with Disruption Event", fontsize=14)
    fig.tight_layout()

    if save_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        save_path = OUTPUT_DIR / "tornado_vortex_3d.png"
    fig.savefig(save_path, dpi=150)
    print(f"\nFigure saved to: {save_path}")
    plt.close(fig)


# ----------------------------------------------------------------------
# Main simulation
# ----------------------------------------------------------------------

def main():
    X, Y, Z, dx, dy, dz = build_grid_3d()
    z_levels = np.linspace(0.0, DOMAIN_HEIGHT, NZ)

    # Baseline 3D vortex
    u0, v0, w0 = burgers_rott_field(X, Y, Z, center_xy=CORE_CENTER_XY, gamma=GAMMA, alpha=ALPHA)
    ke_initial = kinetic_energy_3d(u0, v0, w0, dx, dy, dz)
    ox0, oy0, oz0 = vorticity_3d(u0, v0, w0, dx, dy, dz)
    core_vort_initial = core_vorticity_3d(ox0, oy0, oz0, X, Y, Z, center_xy=CORE_CENTER_XY)

    # 3D counter-force injection
    u_inject, v_inject, w_inject = inject_counterforce_3d(
        X, Y, Z,
        location=DISRUPTION_LOCATION,
        radius=DISRUPTION_RADIUS,
        strength=DISRUPTION_STRENGTH,
        cancel_fraction=DISRUPTION_CANCEL_FRACTION,
        direction=DISRUPTION_DIRECTION,
        base_field=(u0, v0, w0),
    )
    ke_injected = kinetic_energy_3d(u_inject, v_inject, w_inject, dx, dy, dz)

    # Combined (disrupted) field
    u = u0 + u_inject
    v = v0 + v_inject
    w = w0 + w_inject
    ox, oy, oz = vorticity_3d(u, v, w, dx, dy, dz)
    core_vort_after = core_vorticity_3d(ox, oy, oz, X, Y, Z, center_xy=CORE_CENTER_XY)

    remaining_pct = 100.0 * core_vort_after / core_vort_initial

    # --- Console metrics ---
    print("=" * 55)
    print("3D TORNADO VORTEX SIMULATION METRICS (Burgers-Rott)")
    print("=" * 55)
    print(f"Circulation strength (Gamma): {GAMMA:.1f} m^2/s")
    print(f"Surface core radius (rc0):    {RC0:.1f} m")
    print(f"Domain: +/-{DOMAIN_HALF_WIDTH:.0f} m horizontal, 0-{DOMAIN_HEIGHT:.0f} m altitude")
    print(f"Air density:                  {AIR_DENSITY:.3f} kg/m^3")
    print(f"Disruption cancel fraction:   {DISRUPTION_CANCEL_FRACTION:.2f} (per-cell, centered on marker)")
    print("-" * 55)
    print(f"Initial volumetric kinetic energy: {ke_initial:,.2f} J")
    print(f"Injected counter-force energy:     {ke_injected:,.2f} J")
    print(f"Energy ratio (injection/vortex):   {100 * ke_injected / ke_initial:.2f} %")
    print("-" * 55)
    print(f"Core vorticity before disruption: {core_vort_initial:.4f} 1/s")
    print(f"Core vorticity after disruption:  {core_vort_after:.4f} 1/s")
    print(f"Remaining core vorticity:          {remaining_pct:.2f} %")
    print("=" * 55)

    plot_vortex_3d(X, Y, Z, u, v, w, CORE_CENTER_XY, DISRUPTION_LOCATION, z_levels)


if __name__ == "__main__":
    main()
