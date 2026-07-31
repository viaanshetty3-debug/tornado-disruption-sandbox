# 3D Tornado Hydrodynamic & Thermodynamic Disruption Sandbox

A modular Python sandbox for modeling tornado vortex structure and comparing
speculative disruption methods under a common, internally consistent physics
framework. Built with NumPy and Matplotlib only — no external CFD dependencies.

> **Scope disclaimer:** these are steady-state *diagnostic* models, not
> forecast-grade CFD. There is no time integration, moist thermodynamics,
> pressure solver, or turbulence closure. All benchmark numbers are
> apples-to-apples comparisons *within* the sandbox, not predictions of
> real-world efficacy. The honest headline result is that every intervention
> studied is orders of magnitude away from practical.

---

## Overview

The sandbox is built up in three stages, each in its own script:

### 1. Lamb–Oseen vortex (2D) — `src/tornado_vortex.py`

The classic desingularized line vortex. Tangential wind speed:

```
v_θ(r) = Γ / (2πr) · (1 − exp(−r² / r_c²))
```

- `Γ` — circulation strength (m²/s), `r_c` — core radius (m)
- Solid-body rotation inside the core, potential-vortex decay outside
- Supports injection of a Gaussian-localized counter-directional velocity
  field (an opposing jet / pressure shock) at any (x, y) coordinate
- Reports kinetic energy (`½ρ∫|V|² dA`, ρ = 1.225 kg/m³) and core vorticity
  retention after disruption

### 2. Burgers–Rott vortex (3D) — `src/tornado_vortex_3d.py`

Extends the model into a 3D volume with the qualitative structure of the
Burgers–Rott stretched vortex:

- **Tangential swirl** — Lamb–Oseen radial profile, scaled by a Rott-style
  boundary-layer jet in altitude: `f(z) = (z/z_p)·exp(1 − z/z_p)`
- **Radial convergence** — `v_r = −(αr/2)·exp(−z/2z_p)` feeding the core
- **Vertical stretching updraft** — `w = αz·exp(−r²/r_c(z)²)`, accelerating
  with height
- **Funnel flare** — core radius `r_c(z)` widens with altitude
- 3D counter-force injection at any (x, y, z): either a fixed (dx, dy, dz)
  direction, or per-cell dynamic opposition `−f·envelope·(u, v, w)_local`
  that guarantees peak cancellation exactly at the injection point
  (`f > 1` produces local flow reversal and a counter-rotating shear eddy)
- Volumetric KE and full 3D vorticity (curl) diagnostics

### 3. Thermodynamic intervention sandbox — `src/tornado_intervention_sandbox.py`

Adds temperature `T(x, y, z)` and density `ρ(x, y, z)` fields on top of the
Burgers–Rott dynamics, coupled through buoyancy:

```
w_accel = g · (T_local − T_ambient) / T_ambient          (thermal buoyancy)
w_accel −= g · (ρ_load / ρ_air)                          (mass/water loading)
w(z)² / 2 = ∫ B dz                                       (parcel energetics)
```

Baroclinic vorticity generation is measured as the curl of the buoyancy field
(`∂B/∂y, −∂B/∂x`) — the term that builds horizontal vorticity along the gust
front, later tilted upright into the tornado.

The baseline scenario includes a warm moist **inflow layer** (+4 K, shallow,
+x side), a cold **rear-flank downdraft (RFD) pool** (−6 K, −x side), and the
baroclinic zone between them. Three modular interventions perturb it:

| Method | Target zone | Mechanism |
|---|---|---|
| `run_microwave_beaming` | RFD | Beamed heating (E = m·c_p·ΔT) erases the cold pool's thermal contrast |
| `run_polymer_desiccation` | Updraft | Suspended gel mass adds gravitational loading (F = −m·g) with centrifugal ejection losses |
| `run_cryogenic_cooling` | Inflow | −50 K chilling strips the inflow's positive buoyancy |

---

## Benchmark Results

Baseline vortex: peak updraft 26.35 m/s · mean vorticity 0.0351 s⁻¹ · KE 7.18 GJ.
Engagement window: 10 minutes. Domain: 600 × 600 × 1000 m.

| Method | Updraft Reduction | Vorticity Reduction | Baroclinic Reduction | KE Loss (GJ) | Feasibility | Energy Cost |
|---|---:|---:|---:|---:|---:|---:|
| Microwave Beaming | **−8.72 %** ⚠ | −2.02 % | **+43.72 %** | −0.07 | 0.4 / 10 | 6.0 TJ |
| Polymer Desiccation | +43.35 % | +1.86 % | −32.80 % | 0.21 | 2.8 / 10 | 11.0 GJ |
| Cryogenic Cooling | **+84.70 %** | **+46.94 %** | **−530.70 %** ⚠ | 5.50 | 5.7 / 10 | 1.0 TJ |

*(Negative values mean the quantity got worse — see below.)*

**Resource scale required:**

- **Microwave Beaming** — 10 GW beam (≈10× a large nuclear reactor's output)
- **Polymer Desiccation** — 100 t of gel, ~1–2 C-17 sorties, delivered airborne into the core
- **Cryogenic Cooling** — ≈2 GW refrigeration plant (COP 3), 3.1 TJ heat extraction

---

## Emerging Physics Observations

The interesting results are the *side effects*, which emerge from the coupled
physics rather than being scripted:

1. **Microwave heating buoys the updraft it's meant to weaken.** Warming the
   cold RFD does cut baroclinic generation by ~44 % as intended — but removing
   *negative* buoyancy is indistinguishable from adding positive buoyancy, so
   the peak updraft *strengthens* by ~9 %. The cure for the vorticity source
   feeds the storm's engine.

2. **Cryogenic cooling seeds the next baroclinic zone.** Chilling the inflow
   is decisively effective against the current updraft (−85 %) and rotation
   (−47 %) — but the −50 K pool it creates has far sharper edges than the
   storm's own gradients, spiking baroclinic vorticity generation by over 5×
   (−530 %). The intervention manufactures exactly the ingredient
   (a strong cold-pool boundary) that tornadogenesis feeds on.

3. **The vortex defends itself centrifugally against mass loading.** Polymer
   payload retention depends on the ratio of centrifugal acceleration
   (v_θ²/r) to gravity — the stronger the vortex, the faster it flings the
   payload out of the core. At this vortex intensity retention is ~95 %, but
   it degrades precisely where suppression is needed most.

4. **Overcancellation is wasted energy** (from the 3D counter-force study):
   pushing the cancellation fraction beyond 1.0 reverses local flow and more
   than doubles local shear vorticity (241 % of baseline at 3×), while core
   vorticity barely improves (93.9 % → 91.2 % remaining). Nearly all extra
   injected energy becomes local turbulence, not vortex suppression.

---

## Repository Structure

```
tornado-disruption-sandbox/
├── src/
│   ├── tornado_vortex.py                  # 2D Lamb–Oseen vortex + disruption
│   ├── tornado_vortex_3d.py               # 3D Burgers–Rott vortex + 3D counter-force
│   └── tornado_intervention_sandbox.py    # Thermodynamic intervention comparison
├── output/
│   ├── tornado_vortex_2d.png              # Streamplot + speed heatmap
│   ├── tornado_vortex_3d.png              # 3D quiver + cross-section heatmap
│   └── tornado_interventions_comparison.png  # 2×2 X-Z temperature/flow comparison
├── README.md
└── requirements.txt
```

## Usage

### Install

Requires Python ≥ 3.10.

```bash
git clone <your-repo-url>
cd tornado-disruption-sandbox
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
```

### Run

Each script is standalone; figures are written to `output/` automatically.

```bash
# 2D Lamb–Oseen vortex with counter-force injection
python3 src/tornado_vortex.py

# 3D Burgers–Rott vortex with 3D counter-force injection
python3 src/tornado_vortex_3d.py

# Three-way intervention benchmark (prints comparison table)
python3 src/tornado_intervention_sandbox.py
```

On a headless machine, prefix with `MPLBACKEND=Agg` (the intervention sandbox
already forces Agg internally).

### Tune

All physical parameters sit at the top of each script as documented constants:

- **Vortex:** `GAMMA` (circulation, m²/s), `RC` / `RC0` (core radius, m),
  `ALPHA` (stretching rate, 1/s), `BL_PEAK_HEIGHT` (jet altitude, m)
- **Disruption (2D/3D):** `DISRUPTION_LOCATION`, `DISRUPTION_STRENGTH`,
  `DISRUPTION_RADIUS`, `DISRUPTION_CANCEL_FRACTION` (>1 ⇒ flow reversal)
- **Interventions:** `MICROWAVE_GIGAWATTS`, `POLYMER_MASS_KG`, `CRYO_DELTA_K`,
  `INTERVENTION_DURATION_S`, plus the thermodynamic scene
  (`INFLOW_EXCESS_K`, `RFD_DEFICIT_K`, zone geometry)

The intervention functions are also directly importable:

```python
from tornado_intervention_sandbox import (
    TornadoState, build_grid, build_temperature_field,
    run_microwave_beaming, run_polymer_desiccation, run_cryogenic_cooling,
)

X, Y, Z, dx, dy, dz = build_grid()
base = TornadoState(X, Y, Z, dx, dy, dz, build_temperature_field(X, Y, Z))
result = run_cryogenic_cooling(base, cooling_capacity_kelvin=-30)
print(result.peak_updraft, result.total_vorticity)
```

## License & Citation

Educational / research sandbox. The vortex models follow standard references:
Lamb (1932), Oseen (1912), Burgers (1948), Rott (1958).
