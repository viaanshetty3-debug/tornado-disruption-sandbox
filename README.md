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

The sandbox is built up in five stages, each in its own script — a vortex model,
a 3D extension, a thermodynamic intervention framework, an extended strategy
set, and a head-to-head arena:

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

### 4. Extended strategy set — `src/tornado_strategies.py`

The first three methods all act on the *thermodynamics*. This module widens the
search space along three new axes, reusing the same framework so every result
stays comparable:

| Method | Axis | Mechanism |
|---|---|---|
| `run_surface_roughness` | Dynamic | Canopy drag law `V_out/V_in = exp(−C_d·L/h)` removes inflow momentum; mass continuity throttles the stretching updraft |
| `run_kinetic_jet_barrage` | Dynamic | Anchored thrust units apply counter-torque `F·R` against the angular momentum the inflow supplies, `L̇ = ∫ρ(−v_r)·v_θ·r dA` |
| `run_hygroscopic_seeding` | Microphysical | Salt nuclei condense the storm's own vapour early — mass loading down, latent heat up |
| `run_blast_overpressure` | Impulsive | Yield partitioned into a transient blast wave and *persistent* deposited heat |
| `run_aerosol_shading` | Preventive | Blocked insolation upstream cuts boundary-layer heating hours before the storm matures |
| `run_combined_arms` | Stacked | Shading → drag field → polymer, applied in timescale order |

Two structural choices matter for reading the numbers:

- **Surface drag** and **jet barrage** modify velocity, not temperature, so they
  feed back through mass continuity rather than through buoyancy. `TornadoState`
  gained a `w_base` override for exactly this.
- **Aerosol shading** is applied with a horizontally *uniform* mask, because its
  real footprint is tens of kilometres across. Its zero baroclinic side effect
  is therefore a consequence of that modelling choice, not a discovery — the
  contrast with cryogenic cooling's sharp-edged plume is the point.

### 5. Strategy arena — `src/strategy_arena.py`

Runs all nine methods against one shared baseline and answers two questions:
**which lever** (a single comparative table) and **how big** (a dose–response
sweep per method, so you can see whether a method scales into usefulness or
saturates). Emits `output/strategy_arena.png` and
`output/strategy_dose_response.png`.

---

## Benchmark Results

Baseline vortex: peak updraft 26.35 m/s · mean vorticity 0.0351 s⁻¹ · KE 7.18 GJ.
Engagement window: 10 minutes. Domain: 600 × 600 × 1000 m.

All nine strategies, sorted by effect on the rotation
(`python3 src/strategy_arena.py`):

| Strategy | Updraft Red. | Vorticity Red. | Baroclinic Red. | KE Loss (GJ) | Feasibility | Energy Cost | Verdict |
|---|---:|---:|---:|---:|---:|---:|:--|
| Cryogenic Cooling | +84.7 % | **+46.9 %** | **−530.7 %** ⚠ | 5.50 | 5.7 / 10 | 1.0 TJ | mixed |
| Combined Arms | +68.1 % | +38.9 % | −32.8 % | 5.54 | 4.3 / 10 | 4.8 TJ | mixed |
| Aerosol Shading | +34.7 % | +32.6 % | 0.0 % | 5.35 | 3.8 / 10 | 3.9 TJ | **net positive** |
| Kinetic Jet Barrage | 0.0 % | +8.6 % | 0.0 % | 0.69 | 1.6 / 10 | 2.1 TJ | **net positive** |
| Surface Drag Field | +11.9 % | +4.4 % | 0.0 % | 0.19 | 1.5 / 10 | 883.6 GJ | **net positive** |
| Polymer Desiccation | +43.3 % | +1.9 % | −32.8 % | 0.21 | 2.8 / 10 | 11.0 GJ | mixed |
| Microwave Beaming | −8.7 % | −2.0 % | +43.7 % | −0.07 | 0.4 / 10 | 6.0 TJ | ⚠ backfires |
| Hygroscopic Seeding | −60.0 % | −13.9 % | −48.9 % | −0.86 | 2.3 / 10 | 25.0 GJ | ⚠ backfires |
| Blast Overpressure | −348.8 % | −146.7 % | −2259.2 % | −18.29 | 0.5 / 10 | 4.2 TJ | ⚠ backfires |

*(Positive = the quantity improved. Negative = the intervention made it worse.
"Verdict" gates on the side effect as well as the headline metric, because a
method that cuts vorticity while spiking baroclinic generation has moved the
problem rather than solved it. The feasibility score is inherited from the
original sandbox and weighs cost against effectiveness only — it is blind to
side effects, which is why Cryogenic Cooling tops it while reading "mixed".)*

**Resource scale required:**

- **Polymer Desiccation** — 100 t of gel, ~1–2 C-17 sorties, delivered airborne into the core
- **Hygroscopic Seeding** — 5 t of salt flares, 2–3 aircraft sorties
- **Surface Drag Field** — 2.95 kt of structure over 20 ha, permanent (88 TJ embodied, amortized over 100 events)
- **Cryogenic Cooling** — ≈2 GW refrigeration plant (COP 3), 3.1 TJ heat extraction
- **Kinetic Jet Barrage** — 20 anchored 400 kN units, 48 t of fuel
- **Aerosol Shading** — 150 t of aerosol over 2500 km², 3 h of lead time
- **Blast Overpressure** — 1 kt TNT-equivalent detonated in the core
- **Microwave Beaming** — 10 GW beam (≈10× a large nuclear reactor's output)

### Dose–response: does more effort help?

The sweep is the part that matters if you are sizing hardware. Three shapes appear:

| Strategy | Shape | Detail |
|---|---|---|
| Surface Drag Field | **scales** | 50× the spend buys +11.5 points of vorticity reduction, still climbing |
| Aerosol Shading | **saturates** | 31× the spend buys +40.7 points, but the last step adds only +1.3 |
| Kinetic Jet Barrage | **saturates hard** | plateaus at +8.6 % by ~10 units; beyond that, extra thrust buys literally nothing |
| Hygroscopic Seeding | **inverts** | 40× the dose makes it 34.5 points *worse* |
| Blast Overpressure | **inverts** | 10⁵× the yield makes it 1752 points *worse* |

Only Surface Drag Field is still buying effect at the top of its range. Every
other lever either runs out or points the wrong way.

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

5. **Seeding fails for a reason no amount of payload can fix.** Condensing
   water releases latent heat *and* adds mass loading, and both terms are
   proportional to the condensed mass — so their ratio is a pure material
   constant, `L_v / (c_p · T_ambient) ≈ 8.5`. Heating beats loading by that
   factor at every dosage. This is the only method in the sandbox whose failure
   is provably independent of scale: the dose–response line is straight and
   points down. Seeding harder cannot work, and the model did not have to be
   told that.

6. **Detonation is the worst option available, and for the unintuitive
   reason.** The blast wave is not the problem — it is an acoustic transient
   that crosses the core in seconds, so over a ten-minute engagement its
   time-averaged contribution is a 0.5 % duty cycle. The *heat* is the problem.
   A 1 kt yield deposits 1.5 TJ into ~12 kt of core air, raising it 125 K, and
   that buoyancy does not leave. The result is a 349 % *stronger* updraft and a
   23× spike in baroclinic generation. Scaling to 100 kt makes it monotonically
   worse. You do not disperse a tornado this way; you feed it.

7. **Removing momentum beats adding energy.** The two dynamic methods are the
   only ones that reduce rotation with no measured side effect at all. The
   reason is structural: they take angular momentum *out* of the system, while
   every thermodynamic method works by adding or removing heat somewhere, and
   heat gradients are exactly what generate new vorticity. The drag field is
   also the only strategy still gaining effectiveness at the top of its
   dose–response range.

8. **The jet barrage saturates because the lever, not the power, runs out.**
   Counter-torque only removes swirl inside its envelope; once that region is
   spun down, more thrust does nothing — the plateau at +8.6 % is reached by
   ~10 units and 50 units score identically. And the in-domain figure flatters
   the method badly: `L̇` is measured at a 150 m control cylinder, while a real
   tornado draws from a mesocyclone kilometres wide. For roughly constant
   circulation, `L̇` grows linearly with reservoir radius, so matching this
   result against a 3 km reservoir would take ~20× the hardware — 400 anchored
   turbofans. The code reports both numbers rather than only the flattering one.

9. **Stacking barely helps, and the reason is a diagnostic in itself.** Combined
   Arms was built expecting synergy: weaken the vortex with drag first, and
   centrifugal ejection should fling less of the polymer payload out of the
   core. The effect is real but negligible — retention moves 95.5 % → 95.6 % —
   because at this vortex intensity centrifugal acceleration is not yet what
   limits the payload. The synergy the design was reaching for only exists at
   intensities where retention is already the binding constraint.

---

## Repository Structure

```
tornado-disruption-sandbox/
├── src/
│   ├── tornado_vortex.py                  # 2D Lamb–Oseen vortex + disruption
│   ├── tornado_vortex_3d.py               # 3D Burgers–Rott vortex + 3D counter-force
│   ├── tornado_intervention_sandbox.py    # Physics framework + 3 thermodynamic methods
│   ├── tornado_strategies.py              # 6 extended strategies (dynamic / microphysical / preventive)
│   └── strategy_arena.py                  # All 9 head-to-head + dose–response sweeps
├── output/
│   ├── tornado_vortex_2d.png              # Streamplot + speed heatmap
│   ├── tornado_vortex_3d.png              # 3D quiver + cross-section heatmap
│   ├── tornado_interventions_comparison.png  # 2×2 X-Z temperature/flow comparison
│   ├── strategy_arena.png                 # Effectiveness, cost, and side-effect panels
│   └── strategy_dose_response.png         # Vorticity reduction vs dose and vs spend
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

# Three-way thermodynamic intervention benchmark (prints comparison table)
python3 src/tornado_intervention_sandbox.py

# All nine strategies head-to-head, plus dose–response sweeps
python3 src/strategy_arena.py
```

`strategy_arena.py` imports its siblings by module name, so run it from `src/`
or with `src/` on the path — invoking it as `python3 src/strategy_arena.py`
from the repository root does both automatically.

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
- **Extended strategies** (`tornado_strategies.py`): `ROUGHNESS_CD` /
  `ROUGHNESS_FETCH_M`, `JET_UNIT_THRUST_N` / `JET_UNIT_COUNT` /
  `MESOCYCLONE_RADIUS_M`, `SEED_CONVERSION_EFFICIENCY`,
  `BLAST_YIELD_TONNES_TNT`, `SHADE_FRACTION` / `SHADE_LEAD_TIME_S`, and the
  `CONTROL_RADIUS_M` / `CONTROL_TOP_M` continuity accounting surface

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

### Adding your own strategy

A strategy is any function that takes a `TornadoState` and returns a new one via
`state.derive(...)`. Override `T` and/or `mass_loading` for a thermodynamic
method, or `u` / `v` / `w_base` for a dynamic one. Report cost by setting two
attributes on the returned state — the benchmark and feasibility scorer pick
them up automatically, with no edits to the framework:

```python
from tornado_intervention_sandbox import zone_mask

def run_my_idea(state, knob=1.0):
    mask = zone_mask(state.X, state.Y, state.Z, "updraft")
    new = state.derive(T=state.T - 10.0 * knob * mask,
                       label="My Idea", notes="what it did and what it cost")
    new.energy_cost_j = 1e12 * knob      # overrides the built-in cost dispatch
    new.resource_note = "what you'd have to build"
    return new
```

To include it in the sweeps, append a
`(label, func, dose_kwarg, dose_values, unit)` tuple to `STRATEGY_REGISTRY` in
`tornado_strategies.py`. If your method changes the radial inflow, run the
result through `continuity_updraft_scale` so the stretching updraft responds
consistently rather than staying pinned at its baseline value.

## License & Citation

Educational / research sandbox. The vortex models follow standard references:
Lamb (1932), Oseen (1912), Burgers (1948), Rott (1958).
