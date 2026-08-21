"""
PHASE 1C (v2): Swirl-ratio sensitivity, grounded in published chamber/LES data.

The v1 version of this script used a fully synthetic response curve because
I did not have reliable numeric recall of the real measurements and refused
to fabricate a digitized dataset. That caveat has been narrowed, not
removed: web search located the actual regime boundaries from Church, Snow,
Baker & Agee (1979, J. Atmos. Sci. 36) and later numerical work (Lewellen
et al. 2000; multi-vortex studies), and those ARE used here. What is still
NOT available (direct fetch of every source paper was blocked by network
egress policy in this environment - only search-engine summaries came
through) is a full point-by-point digitized curve. So: regime BOUNDARIES
below are cited real numbers; the curve SHAPE within each regime is
still an illustrative interpolation between them, clearly marked as such.

A more important correction than "more data points": v1 conflated two
different quantities. The literature treats them separately:

  (a) DOMAIN-SCALE maximum tangential velocity of the vortex as a whole.
      Church et al. (1979): as S increases in the turbulent regime, this
      quantity DECREASES while the core radius increases. For turbulent
      vortices the S-dependence of this maximum is reported as weak; it is
      strongly S-dependent only in the laminar regime.

  (b) NEAR-SURFACE / corner-flow peak wind - the quantity that actually
      determines ground damage. This is a different, locally-amplified
      quantity: multi-vortex / suction-vortex structures in the S >~ 0.7-0.8
      regime can drive near-surface winds well above the "thermodynamic
      speed limit" baseline - by 21% (large, high-swirl vortices) up to 59%
      (small, low-swirl vortices), per Crowell, White & Wicker (2013/2014,
      J. Wind Eng. Ind. Aerodyn.). This is the quantity phase1_swirl_leverage
      .py's Burgers-balance argument (v_peak ~ Gamma*sqrt(alpha)) implicitly
      stands in for, and it is the one a roughness ring would be trying to
      reduce.

These are not the same curve. (a) falling with S does not imply (b) falls
with S - the corner-flow amplification in (b) is exactly the mechanism that
can make things worse, and it is real, cited, non-hypothetical.
"""

import numpy as np


# ----------------------------------------------------------------------
# Cited regime boundaries (Church et al. 1979; Lewellen et al. 2000;
# multi-vortex literature converged on via multiple independent searches)
# ----------------------------------------------------------------------

REGIME_BOUNDARIES = [
    (0.0, 0.4, "single-cell (laminar-ish core, strongly S-dependent peak)"),
    (0.4, 0.45, "single-cell -> breakdown bubble forms aloft"),
    (0.45, 0.7, "breakdown bubble descends to ground (critical S ~ 0.45)"),
    (0.7, 0.8, "two-cell vortex established"),
    (0.8, 3.0, "multi-vortex: 2 sub-vortices at S~0.8, rising toward ~6 as S->3"),
]

# Domain-scale max tangential velocity: falls with S in the turbulent
# regime per Church et al. (weak S-dependence once turbulent). Modeled as a
# mild monotonic decline - this part IS a direct paraphrase of a real
# reported trend, not fitted to digitized numbers.
def domain_scale_peak(S):
    S = np.asarray(S, dtype=float)
    return 1.0 / (1.0 + 0.15 * S)


# Near-surface / corner-flow peak: baseline follows domain-scale trend up to
# the single-cell ceiling, then gets a multiplicative amplification factor
# in the breakdown/two-cell/multi-vortex range, bounded by the cited
# 1.21x-1.59x range of "thermodynamic speed limit" exceedance
# (Crowell, White & Wicker). The exact shape of the ramp between S=0.45 and
# S=0.8 is NOT from digitized data - only the boundary values and the
# amplification RANGE are cited; the interpolation is illustrative.
def near_surface_peak(S):
    S = np.asarray(S, dtype=float)
    base = domain_scale_peak(S)
    # Amplification ramps on across the breakdown->multi-vortex transition,
    # saturating within the cited 1.21-1.59x envelope.
    amp = 1.0 + 0.4 / (1.0 + np.exp(-8.0 * (S - 0.6)))
    return base * amp


def main():
    print("=" * 78)
    print("PHASE 1C v2 - SWIRL RATIO SENSITIVITY (cited regime boundaries)")
    print("=" * 78)
    print("""
  Sources for regime boundaries and amplification range:
    Church, Snow, Baker & Agee (1979), J. Atmos. Sci. 36, 1755-1776
    Lewellen, Lewellen & Sykes (2000), J. Atmos. Sci. 57, 527-544
    Crowell, White & Wicker (2013/2014), J. Wind Eng. Ind. Aerodyn.
  (accessed via web search summaries; direct PDF fetch was blocked by
  network egress policy in this environment - see note at top of file)
""")

    print(f"{'S range':>14}   regime")
    print("-" * 78)
    for lo, hi, label in REGIME_BOUNDARIES:
        print(f"{lo:>6.2f}-{hi:<6.2f}   {label}")

    print("\n" + "-" * 78)
    print(f"{'S':>6}{'domain-scale max':>20}{'near-surface peak':>22}{'ratio (b)/(a)':>18}")
    for s in [0.1, 0.3, 0.4, 0.45, 0.6, 0.7, 0.8, 1.0, 1.5, 2.0]:
        a = domain_scale_peak(np.array([s]))[0]
        b = near_surface_peak(np.array([s]))[0]
        print(f"{s:>6.2f}{a:>20.2f}{b:>22.2f}{b/a:>18.2f}")

    print("""
  Reading this: the domain-scale column falls smoothly with S (real,
  cited trend). The near-surface column - the one that determines ground
  damage - stops falling and turns back up across S ~ 0.45-0.8, which is
  exactly the breakdown-to-multi-vortex transition. That the amplification
  is real and roughly this size (up to +59% locally) is cited; that it
  ramps on smoothly rather than jumping is an illustrative simplification
  of what is, physically, a structural transition (discrete sub-vortex
  count) rather than a smooth curve.
""")

    print("=" * 78)
    print("WHAT THIS CHANGES FROM THE PHASE 1 REPORT")
    print("=" * 78)
    print("""
  1. The "danger zone" flagged qualitatively in PHASE1_REPORT.md section 5
     is now anchored to real numbers: roughly S in [0.45, 0.8], the
     breakdown-bubble-to-two-cell transition. That range is a genuine
     citation, not a guess.

  2. The v1 script (and phase1_swirl_leverage.py's Route 2/3 costing)
     implicitly treated "peak wind" as one quantity falling smoothly with
     reduced inflow. It is closer to two quantities: domain-scale max
     (falls with S, weakly once turbulent) and near-surface/corner peak
     (can rise across the transition). The roughness-ring route only helps
     if it moves the storm's LOCAL swirl ratio down through this transition
     without stalling inside it - a ring that partially blocks inflow could
     leave a storm sitting IN the S~0.45-0.8 range rather than pushing it
     out the far side.

  3. The instrumentation problem identified before still stands and is now
     sharper: you would need to know not just "is S high or low" but
     whether an intervention crosses the full transition zone or parks the
     storm inside it. No existing external instrument resolves corner-flow
     swirl ratio to that precision in real time.

  4. This is meaningfully more grounded than v1, but it is still not the
     real digitized curve. The chamber/LES recommendation in
     PHASE1_REPORT.md section 6 stands unchanged - it is what would replace
     the interpolation above with an actual measured line.
""")


if __name__ == "__main__":
    main()
