# Phase 1 Report — Go/No-Go on the Tornado Disruptor Tower

**Status: NO-GO as specified.** The tower cannot work. A different concept
survives, and the phase 1 experiment should change accordingly.

Phase 1 was defined as an aerosol wind-tunnel test to check whether injected
particles create counter-rotation. Before spending $50K on a rig, the
momentum budget had to be checked — the sandbox never charged us for the
momentum it was subtracting. That check is decisive, so it is reported first.

Scripts: `phase1_energy_budget.py`, `phase1_swirl_leverage.py`

---

## 1. The sandbox results were arithmetic, not physics

Every "successful" disruption in this repo applied a velocity change and then
measured the energy drop. Reverse torque at strength *s* multiplies the
tangential wind by (1−*s*). Energy goes as v², so the measured loss is
1−(1−s)² — by construction:

| torque strength | 1−(1−s)² | measured in `comprehensive_disruption_suite.py` |
|---|---|---|
| 0.3 | 51.0% | 50.6% |
| 0.5 | 75.0% | 74.4% |
| 0.8 | 96.0% | 95.2% |

The "optimization" that found strength 0.3 as the minimum effective setting
rediscovered the square root of 0.49. It contained no information about
whether a machine could produce that velocity change. The 96.5% headline
result means only "if the wind were 80% slower, the wind would be 80% slower."

The threshold analysis has the same defect: uniformly scaling velocity by *k*
and reporting 1−k² energy loss is a restatement of the definition of kinetic
energy, not a stability criterion. **There is no evidence in this repo that
50% energy loss disrupts a vortex.** The model has no time integration, so it
cannot show a vortex failing to recover.

---

## 2. What the tower can actually deliver

Two corrections to `tower_design_overview.txt`:

**Unit error.** The spec claims 800 kg/s of air injection and, three lines
later, 800 m³/min = 13.3 kg/s. Compressor ratings are free-air delivery in
m³/min, so the real figure is 800 m³/min × 1.225 kg/m³ ≈ **16 kg/s**. The
headline number was too large by ~50×.

**Power ceiling.** If all 5.2 MW of shaft power became jet kinetic energy at
100 m/s (P = ½ṁV²), the absolute ceiling is 1,040 kg/s. Real compressed-air
jets reach maybe 10–20% of that. 1,040 kg/s is used below as a hard upper
bound the machine cannot exceed, not as a design point.

| | mass flux | thrust | angular momentum flux | jet power |
|---|---|---|---|---|
| as specified | 16 kg/s | 1.6 kN | 8.2×10⁴ | 82 kW |
| ideal 5.2 MW ceiling | 1,040 kg/s | 104 kN | 5.2×10⁶ | 5.2 MW |

---

## 3. The gap

Angular momentum is the quantity that matters. Outside the core, r·v_θ = Γ/2π
is constant with radius, so L = ρ(Γ/2π)V — it scales with the whole vortex
volume and cannot be made small by choosing a convenient boundary.

Time to cancel it, assuming *every* injected unit lands on the vortex with the
right sign and nothing is lost to entrainment, mixing, or the ground:

| vortex | peak wind | angular momentum | tower as spec'd | at 5.2 MW ceiling |
|---|---|---|---|---|
| sandbox model | 54 m/s | 5.3×10⁹ | 18 hours | 17 min |
| real EF2 | 51 m/s | 2.8×10¹¹ | 39 days | 15 hours |
| real EF4 | 81 m/s | 1.2×10¹³ | 1,670 days | 26 days |

The intervention window is about 120 seconds. Against a real EF4 the tower is
short by **1.2 million×** as specified, or **19,000×** at its physical power
ceiling.

And the tornado is not a closed system. A supercell's updraft carries ~1.6×10⁹
kg/s; condensing ~1% of that releases ~41 TW, of which a few tenths of a
percent becomes organized kinetic energy — order 100 GW. **The storm
regenerates kinetic energy roughly 24,000× faster than the tower injects it.**
Even a successful cancellation refills in well under a second.

No refinement of nozzles, aerosols, or targeting closes a six-order-of-
magnitude gap. The aerosol wind tunnel test would have been answering the
wrong question at the wrong scale.

---

## 4. The one thing that survives

Peak wind is not set by circulation alone; it is set by how tightly the
circulation is concentrated. In a Burgers vortex, stretching (α) fights
turbulent diffusion (ν_t) and the core radius sits where they balance:

    r_c = √(4ν_t/α)     →     v_peak ∝ Γ/r_c ∝ Γ√α

Weaken the stretching and the core *must* widen. The vortex keeps every unit
of angular momentum it had, spread thinner:

| α/α₀ | core radius | peak wind |
|---|---|---|
| 1.00 | 100 m | 81 m/s |
| 0.50 | 141 m | 57 m/s |
| 0.25 | 200 m | 41 m/s |
| 0.10 | 316 m | 26 m/s |

*(The earlier "microwave heating" test scored 0.7% because the 3D model
prescribes core radius independently of α — it cut the updraft while leaving
the core width, and therefore the winds, untouched. That decoupling is
unphysical and understated the thermal route.)*

Halving peak wind needs α cut 4×, i.e. blocking 75% of the convergent inflow —
9.2×10⁵ kg/s instead of the 4.9×10⁶ kg/s equivalent for the circulation route.
**5.3× cheaper, and still 888× beyond the tower's ceiling.** Any machine that
has to *supply* the momentum loses.

### Route 3: don't supply momentum

A drag element supplies none. It removes inflow momentum using the tornado's
own kinetic energy, at zero power budget — so the six orders of magnitude
simply do not apply to it. Inflow crossing a field of bluff bodies decays as
exp(−C_d·a·R/2). Cutting it to 25% over a ring of width R requires:

| ring width | projected obstacle area per m² of ground |
|---|---|
| 200 m | 1.16 (impossible) |
| 500 m | 0.46 (≈ mature forest) |
| 1000 m | 0.23 (≈ open woodland / dense pole grid) |
| 2000 m | 0.12 (sparse but very wide) |

These are civil-engineering numbers, not machine numbers: a 0.5–2 km
roughness ring around whatever you want to protect. It is also the only route
with observational support — tornado damage intensity is known to vary with
surface roughness and terrain, and the corner-flow inflow layer is exactly
where that sensitivity lives.

It is not a machine, and it protects a fixed place rather than chasing storms.

---

## 5. The caveat that could invert all of it

Changing the swirl-to-inflow balance does not slide a tornado down a smooth
ramp. It moves it across a **bifurcation**. As the corner-flow swirl ratio S
rises, laboratory vortex chambers show the flow jump from single-cell, to a
breakdown bubble, to two-cell, to multiple suction vortices — and two-cell
and multi-vortex states can carry *higher* peak near-surface winds than the
single-cell state they replaced.

When this report was first written that paragraph was a qualitative claim
from general familiarity with the literature, without checked citations.
Web search (`phase1_swirl_ratio_sensitivity.py` v2) subsequently located the
actual regime boundaries and confirmed the claim is real, not a hedge:

| S range | regime | source |
|---|---|---|
| 0 – 0.4 | single-cell | Church, Snow, Baker & Agee (1979), *J. Atmos. Sci.* 36 |
| 0.4 – 0.45 | breakdown bubble forms aloft | Church et al. (1979) |
| 0.45 – 0.7 | breakdown bubble descends to ground (critical S ≈ 0.45) | Lewellen, Lewellen & Sykes (2000), *J. Atmos. Sci.* 57 |
| 0.7 – 0.8 | two-cell vortex established | Church et al. (1979) |
| 0.8 – 3+ | multi-vortex, 2 sub-vortices at S≈0.8 rising toward ~6 near S≈3 | multi-vortex literature (Fiedler/Rotunno-line studies) |

Church et al. also report a distinction the earlier draft of this report
did not make: the vortex's **domain-scale** maximum tangential velocity
*decreases* with S once the flow is turbulent (S-dependence is weak in that
regime). The quantity that goes up across the S≈0.45–0.8 transition is
different — **near-surface / corner-flow peak wind**, the one that actually
sets damage. Crowell, White & Wicker (2013/2014, *J. Wind Eng. Ind. Aerodyn.*)
quantify that corner-flow amplification: near-surface winds exceeding the
"thermodynamic speed limit" baseline by 21% (large, high-swirl vortices) up
to 59% (small, low-swirl vortices).

So Route 2/3's Burgers-balance argument (peak wind ∝ Γ√α, section 3) is a
decent model of the domain-scale quantity, which is the one that falls
smoothly as inflow is blocked — but it is silent on the corner-flow quantity,
which is the one that can rise. **A roughness ring that only partially blocks
inflow risks parking the storm's local S inside the 0.45–0.8 transition band
rather than pushing it out the other side**, which is a real way for this
intervention to make things worse, not just fail to help.

Nothing in this repo's sandbox model can place a real tornado on this curve:
there is no time integration, no boundary layer, no pressure solver. Nor can
any existing external instrument read a real storm's corner-flow swirl ratio
in real time with the precision this requires — that instrumentation gap,
not the civil engineering, is the actual blocker for the roughness-ring
route (`phase1_swirl_ratio_sensitivity.py`, section "what this changes").

*Caveat on the caveat:* direct fetch of the source papers (arXiv, AMS
Journals, Springer, NOAA repository) was blocked by this environment's
network egress policy; the numbers above come from search-engine summaries
of those papers, not the primary text. They converged consistently across
several independent searches, which is reasonable grounds for confidence in
the regime boundaries — but they are secondhand, and the exact shape of the
near-surface peak-wind curve *within* each regime is still not digitized
data. That is what the chamber experiment below is for.

---

## 6. Revised Phase 1 experiment

**Not** an aerosol counter-rotation test. That tests a mechanism now known to
be ~10⁶ short, and a wind tunnel cannot scale away that gap.

**Instead: a swirl-ratio perturbation study in a Ward-type vortex chamber.**

- Chamber with independently controlled circulation and updraft flow rate, so
  swirl ratio S can be set and swept through the breakdown transitions.
- Instrument near-surface peak velocity with PIV — the quantity that
  determines damage, not volume-integrated energy.
- Introduce a scaled roughness ring in the inflow layer; measure how the
  achieved ΔS maps to near-surface peak wind.
- **The result that matters is the sign.** Does added inflow roughness reduce
  near-surface peak wind, or push the vortex into a multi-vortex state that
  raises it? Map this across the S range, not at a single setting.

Cost is comparable to the original proposal (chamber time at an existing
facility rather than a new rig — NSSL, Iowa State, Western Ontario and others
operate them). The output is a go/no-go on whether inflow modification helps
or hurts, which is the only question worth answering before anything is built.

**If the sign is favourable**, the follow-on is a roughness-ring siting study
for a fixed high-value target, not a tower. **If the sign is unfavourable or
S-dependent**, the concept is dead and that is worth knowing for $50K.

---

## 7. What this does not say

The physics that a *sufficiently large* momentum injection would disrupt a
vortex is not in dispute. What Phase 1 establishes is that the required
magnitude is six orders beyond a tower-scale machine, that the storm refills
faster than any such machine drains, and that the repo's earlier percentages
were definitional rather than empirical. The passive-roughness route is not
refuted here — it is the only one whose cost model was not ruled out, which is
a much weaker claim than saying it works.
