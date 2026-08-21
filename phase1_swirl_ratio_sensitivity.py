"""
PHASE 1C: Swirl-ratio sensitivity - which side of the bifurcation are we on?

phase1_swirl_leverage.py showed that blocking inflow is the only route whose
cost model survives (passive drag, zero power budget). But it assumed
reducing inflow always reduces peak wind. Vortex-chamber literature
(Ward 1972; Church, Snow, Baker & Agee 1979; Lewellen 1993) says that's only
true on one side of a bifurcation in swirl ratio S: past the single-cell
regime the vortex can go through breakdown to two-cell to multi-vortex, and
near-surface peak winds are NOT monotonic in S across that range.

IMPORTANT CAVEAT: the response curve below is a SYNTHETIC function chosen to
have the qualitative shape reported in that literature (rise through
single-cell, peak near the single/two-cell transition, elevated and noisy
through multi-vortex). It is NOT digitized from a real dataset - I do not
have reliable numeric recall of the actual measured curve to reproduce it
faithfully, and fabricating specific values would be worse than admitting
that. Treat every number this script prints as illustrative of the ANALYSIS
STRUCTURE, not as a physical prediction. The real curve is exactly what the
recommended chamber experiment (Phase 1 report, section 6) is for.

What this script IS useful for: showing that "block more inflow" is not
safe to assume monotonic, and giving the shape of the question a chamber
run needs to answer before any roughness ring gets built.
"""

import numpy as np


def schematic_peak_wind_ratio(S):
    """
    Synthetic V_peak(S) / V_peak(S_ref), shaped like the qualitative
    single-cell -> breakdown -> two-cell -> multi-vortex progression.
    NOT real data. See module docstring.
    """
    S = np.asarray(S, dtype=float)

    # Single-cell rise: peak wind increases with S up to the transition
    rise = 1.0 - np.exp(-3.0 * S)

    # Bump centered near the single/two-cell transition (S ~ 0.55): this is
    # where chamber studies report the historic maximum swirl velocity
    bump = 0.35 * np.exp(-((S - 0.55) ** 2) / (2 * 0.12 ** 2))

    # Beyond the transition: elevated, structurally noisy multi-vortex
    # plateau rather than a clean falloff (suction vortices keep local
    # peaks high even as the mean swirl declines)
    plateau = 0.15 * (1.0 / (1.0 + np.exp(-8.0 * (S - 0.9))))

    return rise + bump + plateau


def find_critical_regions(S_range, ratio, threshold=0.0):
    """Return indices where dratio/dS < threshold (wind rising as S falls,
    i.e. reducing inflow would be actively counterproductive there)."""
    dratio_dS = np.gradient(ratio, S_range)
    return dratio_dS < threshold


def main():
    print("=" * 78)
    print("PHASE 1C - SWIRL RATIO SENSITIVITY (SCHEMATIC, NOT MEASURED DATA)")
    print("=" * 78)
    print("""
  Read this as: "if the real curve looks qualitatively like this, here is
  how to use it" - not as a prediction of what a real tornado will do.
""")

    S = np.linspace(0.05, 1.5, 400)
    ratio = schematic_peak_wind_ratio(S)
    ratio /= ratio.max()  # normalize to peak = 1.0

    print(f"{'S (swirl ratio)':>18}{'peak wind (norm.)':>20}{'regime (schematic)':>24}")
    for s in [0.1, 0.3, 0.5, 0.55, 0.7, 0.9, 1.1, 1.4]:
        r_display = schematic_peak_wind_ratio(np.array([s]))[0]
        r_norm = r_display / schematic_peak_wind_ratio(S).max()
        if s < 0.4:
            regime = "single-cell, sub-critical"
        elif s < 0.65:
            regime = "single/two-cell transition"
        elif s < 0.9:
            regime = "two-cell / breakdown bubble"
        else:
            regime = "multi-vortex"
        print(f"{s:>18.2f}{r_norm:>20.2f}   {regime}")

    # Where does reducing S (via inflow blocking) make things WORSE?
    danger = find_critical_regions(S, ratio)
    danger_ranges = S[danger]

    print("\n" + "-" * 78)
    if len(danger_ranges) > 0:
        print(f"  Schematic 'danger zones' (reducing S here INCREASES peak wind):")
        print(f"  S in [{danger_ranges.min():.2f}, {danger_ranges.max():.2f}] "
              f"(approx, non-contiguous in general)")
    print("""
  The actionable point, independent of the exact curve: a roughness ring
  that reduces inflow changes S. If the pre-intervention tornado sits BELOW
  the transition, that's the direction you want. If it sits AT or ABOVE it
  (already two-cell / multi-vortex), further reducing S can walk it further
  along a region where near-surface peak wind does not simply fall.

  You cannot read S off a tornado from outside in real time with any
  existing instrument at the precision this requires. That is the actual
  blocker for the roughness-ring route - not the civil engineering, which
  is straightforward, but not knowing which side of the curve you're
  pushing a given storm from.
""")

    print("=" * 78)
    print("WHAT WOULD MAKE THIS A REAL ANSWER INSTEAD OF A SCHEMATIC")
    print("=" * 78)
    print("""
  1. Chamber run (Phase 1 report, section 6): measure actual V_peak(S) with
     PIV in a Ward-type chamber, across S = 0.1 to 1.5, with and without a
     scaled inflow-roughness ring. This replaces the synthetic curve above
     with real numbers and answers the sign question directly.

  2. If a chamber shows the danger zone is narrow and known, the siting
     study could target rings sized to guarantee S stays clear of it - but
     that requires an independent read on a real storm's swirl ratio before
     committing, which is itself an open instrumentation problem (mobile
     radar-derived low-level divergence/inflow estimates are the closest
     existing proxy, and their precision has not been checked against this
     requirement).

  3. Until (1) exists, the honest status of the roughness-ring route is:
     cost model survives, sign unknown, and this script cannot fix that -
     only the chamber experiment can.
""")


if __name__ == "__main__":
    main()
