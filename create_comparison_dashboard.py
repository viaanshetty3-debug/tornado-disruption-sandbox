"""
Create a visual comparison dashboard of all disruption methods.
"""

from pathlib import Path
import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# Load results
with open(OUTPUT_DIR / "comprehensive_analysis_results.json") as f:
    results = json.load(f)

# Extract data
methods = [r['param'] for r in results]
energy_loss = [r['energy_loss'] for r in results]
vort_retained = [r['vort_retained'] for r in results]
disrupted = [r['disrupted'] for r in results]

# Categorize methods
categories = []
for param in methods:
    if "strength=" in param:
        categories.append("Torque Optimization")
    elif "Torque" in param and "+" in param:
        categories.append("Hybrid")
    elif "Core-only" in param or "Altitude" in param:
        categories.append("Targeted")
    else:
        categories.append("Novel")

# Color coding
colors = []
for d in disrupted:
    if d:
        colors.append("#2ecc71")  # Green = works
    else:
        colors.append("#e74c3c")  # Red = doesn't work

# ========== Figure 1: Energy Loss vs Vorticity ==========
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

# Scatter: Energy Loss vs Vort Retention
for i, (method, el, vr, color, cat) in enumerate(zip(methods, energy_loss, vort_retained, colors, categories)):
    ax1.scatter(el, vr, s=200, c=color, alpha=0.7, edgecolors="black", linewidth=1.5)
    ax1.text(el + 1.5, vr + 1, method.replace("strength=", "T="), fontsize=8, ha="left")

# Add threshold line
ax1.axvline(x=50, color="orange", linestyle="--", linewidth=2, label="50% disruption threshold")
ax1.axhline(y=50, color="orange", linestyle="--", linewidth=2)

ax1.set_xlabel("Energy Loss (%)", fontsize=12, fontweight="bold")
ax1.set_ylabel("Core Vorticity Retained (%)", fontsize=12, fontweight="bold")
ax1.set_title("Disruption Effectiveness: Energy vs Vorticity", fontsize=13, fontweight="bold")
ax1.grid(True, alpha=0.3)
ax1.legend(fontsize=10)
ax1.set_xlim(-50, 105)

# Bar chart: Energy Loss by Method
y_pos = np.arange(len(methods))
sorted_idx = np.argsort(energy_loss)[::-1]  # Sort descending

sorted_methods = [methods[i] for i in sorted_idx]
sorted_energy = [energy_loss[i] for i in sorted_idx]
sorted_colors = [colors[i] for i in sorted_idx]

bars = ax2.barh(y_pos, sorted_energy, color=sorted_colors, edgecolor="black", linewidth=1)

# Add value labels
for i, (bar, val) in enumerate(zip(bars, sorted_energy)):
    ax2.text(val + 2, i, f"{val:.1f}%", va="center", fontsize=9, fontweight="bold")

# Add 50% threshold line
ax2.axvline(x=50, color="orange", linestyle="--", linewidth=2, alpha=0.7, label="Disruption threshold")

ax2.set_yticks(y_pos)
ax2.set_yticklabels(sorted_methods, fontsize=9)
ax2.set_xlabel("Energy Loss (%)", fontsize=12, fontweight="bold")
ax2.set_title("Energy Dissipation by Method", fontsize=13, fontweight="bold")
ax2.set_xlim(0, 105)
ax2.grid(True, alpha=0.3, axis="x")
ax2.legend(fontsize=10)

fig.suptitle("TORNADO DISRUPTION METHOD COMPARISON", fontsize=14, fontweight="bold", y=0.98)
fig.tight_layout()
fig.savefig(OUTPUT_DIR / "disruption_comparison_dashboard.png", dpi=150, bbox_inches="tight")
print("Dashboard saved: disruption_comparison_dashboard.png")
plt.close(fig)

# ========== Figure 2: Method Categories ==========
fig, ax = plt.subplots(figsize=(14, 8))

category_colors = {
    "Torque Optimization": "#3498db",   # Blue
    "Hybrid": "#9b59b6",                 # Purple
    "Targeted": "#e67e22",               # Orange
    "Novel": "#95a5a6",                  # Gray
}

y_pos = np.arange(len(methods))
sorted_methods_cat = [methods[i] for i in sorted_idx]
sorted_categories = [categories[i] for i in sorted_idx]
sorted_colors_cat = [category_colors[categories[i]] for i in sorted_idx]
sorted_energy_cat = [energy_loss[i] for i in sorted_idx]
sorted_disrupted_cat = [disrupted[i] for i in sorted_idx]

# Bars with category colors
bars = ax.barh(y_pos, sorted_energy_cat, color=sorted_colors_cat, edgecolor="black", linewidth=1.5, alpha=0.8)

# Overlay: Disruption status (checkmark or X)
for i, (bar, is_disrupted, val) in enumerate(zip(bars, sorted_disrupted_cat, sorted_energy_cat)):
    if is_disrupted:
        ax.text(val - 5, i, "✓", fontsize=16, fontweight="bold", color="white", ha="right", va="center")
    else:
        ax.text(val - 5, i, "✗", fontsize=16, fontweight="bold", color="white", ha="right", va="center")
    ax.text(val + 2, i, f"{val:.1f}%", va="center", fontsize=9, fontweight="bold")

ax.axvline(x=50, color="red", linestyle="--", linewidth=2.5, alpha=0.7, label="50% Disruption Threshold")

ax.set_yticks(y_pos)
ax.set_yticklabels(sorted_methods_cat, fontsize=10)
ax.set_xlabel("Energy Loss (%)", fontsize=12, fontweight="bold")
ax.set_title("Disruption Methods by Category (✓ = Effective)", fontsize=13, fontweight="bold")
ax.set_xlim(0, 105)
ax.grid(True, alpha=0.3, axis="x")

# Legend
handles = [mpatches.Patch(color=color, label=cat, edgecolor="black", linewidth=1)
           for cat, color in category_colors.items()]
ax.legend(handles=handles, loc="lower right", fontsize=10)

fig.tight_layout()
fig.savefig(OUTPUT_DIR / "disruption_by_category.png", dpi=150, bbox_inches="tight")
print("Category chart saved: disruption_by_category.png")
plt.close(fig)

# ========== Figure 3: Key Findings Summary ==========
fig, ax = plt.subplots(figsize=(12, 8))
ax.axis("off")

findings = [
    ("KEY FINDINGS", 18, "bold"),
    ("", 10, "normal"),
    ("1. MINIMUM EFFECTIVE STRENGTH: 0.3 (50.6% energy loss)", 11, "normal"),
    ("   • Torque strength of 0.3 is sufficient to disrupt the vortex", 9, "normal"),
    ("   • Reduces required energy input by 3× vs. 0.8 strength", 9, "normal"),
    ("", 10, "normal"),
    ("2. HYBRID METHODS PROVIDE MARGIN", 11, "normal"),
    ("   • Torque(0.5) + Drag(0.1) achieves 79.2% loss", 9, "normal"),
    ("   • Redundancy: if one mechanism fails, second still works", 9, "normal"),
    ("", 10, "normal"),
    ("3. ALTITUDE TARGETING IS PRACTICAL", 11, "normal"),
    ("   • Altitude band (50-150m, 70%) achieves 50.8% loss", 9, "normal"),
    ("   • More realistic than domain-wide application", 9, "normal"),
    ("", 10, "normal"),
    ("4. NOVEL MECHANISMS DON'T WORK ALONE", 11, "normal"),
    ("   • Pressure pulse: -37.3% (energy added, not removed)", 9, "normal"),
    ("   • Vertical shear: -27.0% (increases coherence)", 9, "normal"),
    ("   • Requires direct opposition (reverse torque) to be effective", 9, "normal"),
    ("", 10, "normal"),
    ("RECOMMENDATION: Reverse Torque at Strength 0.3-0.5", 12, "bold"),
    ("   • Meets 50% threshold with minimum energy input", 9, "normal"),
    ("   • Complement with altitude targeting for practical deployment", 9, "normal"),
]

y = 0.95
for text, size, weight in findings:
    ax.text(0.05, y, text, fontsize=size, fontweight=weight, family="monospace",
            verticalalignment="top", transform=ax.transAxes)
    y -= 0.035

fig.tight_layout()
fig.savefig(OUTPUT_DIR / "key_findings.png", dpi=150, bbox_inches="tight")
print("Summary saved: key_findings.png")
plt.close(fig)

print("\n" + "="*60)
print("DASHBOARDS CREATED")
print("="*60)
print("  1. disruption_comparison_dashboard.png - Scatter + bar chart")
print("  2. disruption_by_category.png - Methods by category")
print("  3. key_findings.png - Summary of recommendations")
