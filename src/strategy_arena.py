"""
Strategy Arena
==============

Runs every disruption strategy in the sandbox - the three thermodynamic methods
from `tornado_intervention_sandbox` and the six extended methods from
`tornado_strategies` - against one shared baseline vortex, then answers the two
questions that matter if you are trying to decide what to build:

  1. WHICH LEVER?  A single comparative table, all nine methods, identical
     baseline, identical diagnostics. Effectiveness, side effects, energy cost,
     feasibility.

  2. HOW BIG?      A dose-response sweep per method: vorticity reduction as a
     function of the resource you pour in. This is the part that tells you
     whether a method scales into usefulness or saturates - and three of them
     have negative slopes, meaning more effort makes things worse.

Run:
    python3 src/strategy_arena.py

Everything here is diagnostic and steady-state. See the module docstrings in
`tornado_intervention_sandbox` and `tornado_strategies` for the full list of
what this model does not include; the short version is that the rankings are
meaningful and the absolute numbers are not.
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from tornado_intervention_sandbox import (
    OUTPUT_DIR, DOMAIN_HALF_WIDTH, DOMAIN_HEIGHT, INTERVENTION_DURATION_S,
    build_grid, build_temperature_field, TornadoState,
    run_microwave_beaming, run_polymer_desiccation, run_cryogenic_cooling,
    feasibility_score, resource_scale, fmt_energy,
)
from tornado_strategies import STRATEGY_REGISTRY, build_all_strategies

TABLE_WIDTH = 118


# ======================================================================
# Diagnostics
# ======================================================================

def score_state(base, state):
    """Reduce one intervention to the comparable scalar metrics."""
    updraft_red = 100.0 * (base.peak_updraft - state.peak_updraft) / base.peak_updraft
    vort_red = 100.0 * (base.total_vorticity - state.total_vorticity) / base.total_vorticity
    baro_red = 100.0 * (base.mean_baroclinic - state.mean_baroclinic) / base.mean_baroclinic
    ke_loss_gj = (base.kinetic_energy - state.kinetic_energy) / 1e9
    score, cost_j = feasibility_score(state.label, state, vort_red)
    return {
        "state": state,
        "label": state.label,
        "updraft_red": updraft_red,
        "vorticity_red": vort_red,
        "baroclinic_red": baro_red,
        "ke_loss_gj": ke_loss_gj,
        "feasibility": score,
        "cost_j": cost_j,
    }


def net_verdict(row):
    """
    One-word judgement combining the two things a real operator cares about:
    does it weaken the rotation, and does it avoid making the storm worse
    somewhere else?

    A method that cuts vorticity but spikes baroclinic generation has not
    solved the problem, it has moved it downstream - so both terms gate the
    verdict.
    """
    helps = row["vorticity_red"] > 1.0
    updraft_ok = row["updraft_red"] > -1.0
    baro_ok = row["baroclinic_red"] > -25.0

    if not helps and row["vorticity_red"] < -1.0:
        return "BACKFIRES"
    if not helps:
        return "no effect"
    if helps and updraft_ok and baro_ok:
        return "net positive"
    return "mixed"


# ======================================================================
# 1. Head-to-head table
# ======================================================================

def print_arena_table(base, rows):
    print("=" * TABLE_WIDTH)
    print("TORNADO DISRUPTION STRATEGY ARENA".center(TABLE_WIDTH))
    print("=" * TABLE_WIDTH)
    print(f"Baseline vortex: peak updraft {base.peak_updraft:.2f} m/s | "
          f"mean vorticity {base.total_vorticity:.4f} 1/s | "
          f"mean baroclinic {base.mean_baroclinic:.2e} 1/s^2 | "
          f"KE {base.kinetic_energy/1e9:.2f} GJ")
    print(f"Engagement window: {INTERVENTION_DURATION_S/60:.0f} min | "
          f"Domain: {2*DOMAIN_HALF_WIDTH:.0f} x {2*DOMAIN_HALF_WIDTH:.0f} x "
          f"{DOMAIN_HEIGHT:.0f} m | {len(rows)} strategies")
    print("-" * TABLE_WIDTH)

    print(f"{'Strategy':<22} {'Updraft':>9} {'Vorticity':>10} {'Baroclinic':>11} "
          f"{'KE Loss':>9} {'Feasib.':>8} {'Energy':>10} {'Verdict':>14}")
    print(f"{'':22} {'reduc.':>9} {'reduc.':>10} {'reduc.':>11} "
          f"{'(GJ)':>9} {'/10':>8} {'cost':>10} {'':>14}")
    print("-" * TABLE_WIDTH)

    # Best vorticity reduction first; that is the headline metric
    for row in sorted(rows, key=lambda r: -r["vorticity_red"]):
        print(f"{row['label']:<22} {row['updraft_red']:>8.1f}% "
              f"{row['vorticity_red']:>9.1f}% {row['baroclinic_red']:>10.1f}% "
              f"{row['ke_loss_gj']:>9.2f} {row['feasibility']:>8.1f} "
              f"{fmt_energy(row['cost_j']):>10} {net_verdict(row):>14}")

    print("-" * TABLE_WIDTH)
    print("Positive = the quantity improved. Negative = the intervention made it worse.")
    print("Baroclinic reduction tracks the side effect: a large negative number means the")
    print("method manufactured the horizontal buoyancy gradient that feeds tornadogenesis.")


def print_resources_and_notes(rows):
    print("\n" + "=" * TABLE_WIDTH)
    print("RESOURCE SCALE".center(TABLE_WIDTH))
    print("=" * TABLE_WIDTH)
    for row in sorted(rows, key=lambda r: r["cost_j"]):
        print(f"  {row['label']:<22} {fmt_energy(row['cost_j']):>10}   "
              f"{resource_scale(row['label'], row['state'])}")

    print("\n" + "=" * TABLE_WIDTH)
    print("METHOD NOTES".center(TABLE_WIDTH))
    print("=" * TABLE_WIDTH)
    for row in rows:
        print(f"\n  {row['label']}")
        print(f"    {row['state'].notes}")


# ======================================================================
# 2. Dose-response sweep
# ======================================================================

def sweep_strategy(base, func, dose_kwarg, dose_values):
    """Run one strategy across a range of resource levels."""
    out = []
    for dose in dose_values:
        state = func(base, **{dose_kwarg: dose})
        row = score_state(base, state)
        row["dose"] = dose
        out.append(row)
    return out


def run_sweeps(base):
    """Dose-response for every strategy that has a meaningful dial."""
    sweeps = {}
    for label, func, dose_kwarg, dose_values, unit in STRATEGY_REGISTRY:
        sweeps[label] = {
            "unit": unit,
            "dose_kwarg": dose_kwarg,
            "rows": sweep_strategy(base, func, dose_kwarg, dose_values),
        }
    return sweeps


def print_sweeps(sweeps):
    print("\n" + "=" * TABLE_WIDTH)
    print("DOSE-RESPONSE: DOES MORE EFFORT HELP?".center(TABLE_WIDTH))
    print("=" * TABLE_WIDTH)

    for label, sweep in sweeps.items():
        print(f"\n  {label}  (dial: {sweep['dose_kwarg']}, in {sweep['unit']})")
        print(f"    {'dose':>12} {'vorticity red.':>16} {'updraft red.':>14} "
              f"{'baroclinic red.':>17} {'cost':>10}")
        for row in sweep["rows"]:
            dose = row["dose"]
            dose_str = f"{dose:.3g}"
            print(f"    {dose_str:>12} {row['vorticity_red']:>15.2f}% "
                  f"{row['updraft_red']:>13.2f}% {row['baroclinic_red']:>16.2f}% "
                  f"{fmt_energy(row['cost_j']):>10}")

        print(f"    -> {sweep_trend(sweep['rows'])[1]}")


def sweep_trend(rows):
    """
    Classify the shape of a dose-response curve: does pouring in more resource
    keep buying effect, stop buying effect, or actively hurt?

    Returns (category, description) so the sweep listing and the readout stay
    in agreement instead of each deciding for themselves.
    """
    first, last = rows[0], rows[-1]
    delta = last["vorticity_red"] - first["vorticity_red"]
    tail = last["vorticity_red"] - rows[-2]["vorticity_red"]
    dose_span = last["dose"] / max(first["dose"], 1e-12)
    cost_span = last["cost_j"] / max(first["cost_j"], 1e-9)

    effort = (f"{dose_span:.0f}x the dose at flat cost" if cost_span < 1.01
              else f"{cost_span:.0f}x the spend")

    if delta < -1.0:
        return "inverts", f"INVERTS - {effort} makes it {abs(delta):.1f} points WORSE"
    if delta > 1.0 and abs(tail) < 0.05 * abs(delta):
        return "saturates", (f"saturates - {effort} buys {delta:+.1f} points, but "
                             f"the last step adds only {tail:+.2f}: the lever runs out")
    if delta > 1.0:
        return "scales", (f"scales - {effort} buys {delta:+.1f} points of "
                          f"vorticity reduction")
    return "flat", f"flat - {effort} changes almost nothing"


# ======================================================================
# 3. Visualization
# ======================================================================

def plot_arena(base, rows, save_path=None):
    """
    Three-panel summary: effectiveness ranking, the effectiveness-vs-cost
    landscape, and the side-effect axis that the headline metric hides.
    """
    ordered = sorted(rows, key=lambda r: r["vorticity_red"])
    labels = [r["label"] for r in ordered]
    vort = [r["vorticity_red"] for r in ordered]
    baro = [r["baroclinic_red"] for r in ordered]

    fig, axes = plt.subplots(1, 3, figsize=(20, 7.5))

    # A single backfiring method can be two orders of magnitude worse than the
    # best method is good, so linear axes would flatten everything else to a
    # sliver. Symlog keeps the small differences readable without hiding the
    # outlier that makes the point.
    def annotate_values(ax, values, fmt="{:+.1f}%"):
        """
        Label each bar. Short bars get the label just past their end; long ones
        get it inside, in white, since on a symlog axis the longest bar runs
        close enough to the frame that an outside label would land on the
        opposite panel's tick labels.
        """
        max_abs = max(abs(min(values)), abs(max(values)))
        for i, value in enumerate(values):
            inside = abs(value) >= 0.3 * max_abs
            if inside:
                pad, ha, color = (-6 if value >= 0 else 6), \
                    ("right" if value >= 0 else "left"), "white"
            else:
                pad, ha, color = (6 if value >= 0 else -6), \
                    ("left" if value >= 0 else "right"), "black"
            ax.annotate(fmt.format(value), (value, i),
                        textcoords="offset points", xytext=(pad, 0),
                        va="center", ha=ha, fontsize=8, color=color)
        # Symlog is symmetric, so widen both sides to keep labels off the ticks
        ax.set_xlim(-max_abs * 4.0, max_abs * 4.0)

    # --- Panel 1: effectiveness ranking
    ax = axes[0]
    ax.barh(labels, vort, color=["#c0392b" if v < 0 else "#2980b9" for v in vort])
    ax.axvline(0, color="black", linewidth=1)
    ax.set_xscale("symlog", linthresh=10)
    annotate_values(ax, vort)
    ax.set_xlabel("Vorticity reduction (%), symlog  -  positive is better")
    ax.set_title("Effectiveness against the rotation", fontsize=12)
    ax.grid(axis="x", alpha=0.3)

    # --- Panel 2: effectiveness vs cost
    ax = axes[1]
    for i, row in enumerate(ordered):
        cost = max(row["cost_j"], 1e6)
        color = "#c0392b" if row["vorticity_red"] < 0 else "#2980b9"
        ax.scatter(cost, row["vorticity_red"], s=140, color=color,
                   edgecolor="black", zorder=3)
        # Alternate the label side so neighbouring points do not collide
        dx, ha = ((9, "left") if i % 2 == 0 else (-9, "right"))
        ax.annotate(row["label"], (cost, row["vorticity_red"]),
                    textcoords="offset points", xytext=(dx, 7),
                    ha=ha, fontsize=8.5)
    ax.set_xscale("log")
    ax.set_yscale("symlog", linthresh=10)
    ax.axhline(0, color="black", linewidth=1)
    ax.set_xlabel("Energy cost per engagement (J, log scale)")
    ax.set_ylabel("Vorticity reduction (%), symlog")
    ax.set_title("What you get for what you spend", fontsize=12)
    ax.grid(alpha=0.3)

    # --- Panel 3: the side effect
    ax = axes[2]
    ax.barh(labels, baro, color=["#c0392b" if b < 0 else "#27ae60" for b in baro])
    ax.axvline(0, color="black", linewidth=1)
    ax.set_xscale("symlog", linthresh=10)
    annotate_values(ax, baro)
    ax.set_xlabel("Baroclinic reduction (%), symlog  -  negative seeded new vorticity")
    ax.set_title("Side effect: the vorticity source term", fontsize=12)
    ax.grid(axis="x", alpha=0.3)

    fig.suptitle(
        "Tornado Disruption Strategy Arena - nine methods, one baseline vortex\n"
        f"baseline: {base.peak_updraft:.1f} m/s updraft, "
        f"{base.total_vorticity:.4f} 1/s mean vorticity, "
        f"{base.kinetic_energy/1e9:.1f} GJ",
        fontsize=14)
    fig.tight_layout()

    if save_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        save_path = OUTPUT_DIR / "strategy_arena.png"
    fig.savefig(save_path, dpi=140)
    plt.close(fig)
    print(f"\nArena chart saved to: {save_path}")


def plot_dose_response(sweeps, save_path=None):
    """Vorticity reduction vs normalized dose, one line per strategy."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

    for label, sweep in sweeps.items():
        rows = sweep["rows"]
        doses = np.array([r["dose"] for r in rows], dtype=float)
        vort = [r["vorticity_red"] for r in rows]
        costs = [max(r["cost_j"], 1e6) for r in rows]

        # Normalize dose to its own minimum so strategies with wildly different
        # units share an x axis; the shape of the curve is what we are comparing.
        ax1.plot(doses / doses[0], vort, marker="o", label=f"{label} ({sweep['unit']})")
        ax2.plot(costs, vort, marker="o", label=label)

    for ax, xlabel, title in (
        (ax1, "Dose, relative to the smallest tested", "Response to dosage"),
        (ax2, "Energy cost per engagement (J)", "Response to spending"),
    ):
        ax.set_xscale("log")
        # Blast overpressure runs to -1750%; on a linear axis it flattens every
        # other curve to the zero line. Symlog keeps both readable.
        ax.set_yscale("symlog", linthresh=10)
        ax.axhline(0, color="black", linewidth=1)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Vorticity reduction (%), symlog")
        ax.set_title(title, fontsize=12)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8.5, loc="lower left")

    fig.suptitle("Dose-Response: which strategies scale into usefulness\n"
                 "lines below zero are strategies that get worse the harder you push",
                 fontsize=14)
    fig.tight_layout()

    if save_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        save_path = OUTPUT_DIR / "strategy_dose_response.png"
    fig.savefig(save_path, dpi=140)
    plt.close(fig)
    print(f"Dose-response chart saved to: {save_path}")


# ======================================================================
# 4. Readout
# ======================================================================

def print_conclusions(rows, sweeps):
    print("\n" + "=" * TABLE_WIDTH)
    print("READOUT".center(TABLE_WIDTH))
    print("=" * TABLE_WIDTH)

    best = max(rows, key=lambda r: r["vorticity_red"])
    cheapest = min(rows, key=lambda r: r["cost_j"])
    most_feasible = max(rows, key=lambda r: r["feasibility"])
    worst_side_effect = min(rows, key=lambda r: r["baroclinic_red"])
    backfires = [r for r in rows if net_verdict(r) == "BACKFIRES"]

    # The feasibility score weighs cost against effectiveness only - it is blind
    # to side effects, so every superlative below carries its verdict with it.
    print(f"  Strongest effect      {best['label']} "
          f"({best['vorticity_red']:+.1f}% vorticity) [{net_verdict(best)}]")
    print(f"  Cheapest              {cheapest['label']} "
          f"({fmt_energy(cheapest['cost_j'])}) [{net_verdict(cheapest)}]")
    print(f"  Most feasible         {most_feasible['label']} "
          f"({most_feasible['feasibility']:.1f}/10) [{net_verdict(most_feasible)}]")
    print(f"  Worst side effect     {worst_side_effect['label']} "
          f"({worst_side_effect['baroclinic_red']:+.1f}% baroclinic)")

    if backfires:
        print(f"  Actively harmful      "
              f"{', '.join(r['label'] for r in backfires)}")

    clean = [r for r in rows if net_verdict(r) == "net positive"]
    if clean:
        pick = max(clean, key=lambda r: r["vorticity_red"])
        print(f"\n  Best method with no measured side effect: {pick['label']} "
              f"({pick['vorticity_red']:+.1f}% vorticity, "
              f"{fmt_energy(pick['cost_j'])})")

    shapes = {label: sweep_trend(s["rows"])[0] for label, s in sweeps.items()}

    def named(category):
        hits = [label for label, shape in shapes.items() if shape == category]
        return ", ".join(hits) if hits else "none"

    print(f"\n  Keeps scaling with investment  {named('scales')}")
    print(f"  Saturates - more buys nothing  {named('saturates')}")
    print(f"  Gets worse with investment     {named('inverts')}")

    print("\n" + "-" * TABLE_WIDTH)
    print("REALITY CHECK")
    print("-" * TABLE_WIDTH)
    print("  A supercell continuously processes energy at a rate no engineered system")
    print("  in this table approaches, and it does so over a volume thousands of times")
    print("  larger than this domain. Nothing here disrupts a real tornado.")
    print()
    print("  What the sandbox is actually good for is the shape of the problem, and")
    print("  that part is robust: the methods that fight the storm's energy budget")
    print("  head-on lose, the methods that remove momentum cheaply do relatively")
    print("  better than the methods that add energy, and several interventions have")
    print("  the wrong sign - they feed the mechanism they were built to stop.")
    print("=" * TABLE_WIDTH)


# ======================================================================
# Main
# ======================================================================

def main():
    X, Y, Z, dx, dy, dz = build_grid()
    T = build_temperature_field(X, Y, Z)
    base = TornadoState(X, Y, Z, dx, dy, dz, T, label="Base Tornado",
                        notes="Undisturbed Burgers-Rott vortex with warm inflow "
                              "and cold RFD pool")

    # Original three thermodynamic methods
    classic = [
        run_microwave_beaming(base),
        run_polymer_desiccation(base),
        run_cryogenic_cooling(base),
    ]
    # Extended strategies
    extended = build_all_strategies(base)

    rows = [score_state(base, s) for s in classic + extended]

    print_arena_table(base, rows)
    print_resources_and_notes(rows)

    sweeps = run_sweeps(base)
    print_sweeps(sweeps)

    print_conclusions(rows, sweeps)

    plot_arena(base, rows)
    plot_dose_response(sweeps)


if __name__ == "__main__":
    main()
