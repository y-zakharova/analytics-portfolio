import json
import numpy as np
import matplotlib.pyplot as plt

r = json.load(open("results.json"))
W, M = "#2b5c94", "#c8693a"          # women / men (validated pair)
INK, INK2, RULE, GRID = "#1d1d1b", "#6b6760", "#bdb8ae", "#ebe7df"
plt.rcParams.update({
    "font.family": "Inter", "font.size": 10, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.edgecolor": RULE, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK,
    "xtick.major.size": 0, "ytick.major.size": 0, "savefig.transparent": True,
})
O = {o["metric"]: o for o in r["overall"]}
F = {(o["gender"], o["metric"]): o for o in r["funnel"]}
P, FMR, RR = ("Primary: replied conversations / user", "First-message rate (per match)",
              "Reply rate (per first message)")

# Exhibit: overall effect by metric
rows = [(P, "Replied conversations / user", W), (FMR, "First-message rate", INK), (RR, "Reply rate", INK),
        ("Guardrail: D7 retention", "D7 retention", INK2),
        ("Guardrail: reports / 1k first messages", "Reports per 1k first messages", INK2),
        ("Guardrail: premium purchase 7d", "Premium purchase, 7 days", INK2)]
fig, ax = plt.subplots(figsize=(8, 3.3))
ys = np.arange(len(rows))[::-1]
for y, (k, lab, c) in zip(ys, rows):
    o = O[k]
    ax.plot([o["rel_lo"] * 100, o["rel_hi"] * 100], [y, y], color=c, lw=2, solid_capstyle="round", alpha=.55)
    ax.plot(o["rel_lift"] * 100, y, "o", color=c, ms=8, mec="white", mew=2, zorder=3)
    ax.text(max(o["rel_hi"] * 100, 0) + 1.3, y, f"{o['rel_lift']*100:+.1f}%", va="center", fontsize=9.5,
            color=INK, fontweight="bold" if k == P else "normal")
ax.axvline(0, color=RULE, lw=1)
ax.set_yticks(ys, [x[1] for x in rows])
ax.set_xlabel("Relative change vs control, % (dot = estimate, line = 95% CI)")
ax.grid(axis="x", color=GRID, lw=.8); ax.set_axisbelow(True)
ax.axhline(2.5, color=GRID, lw=.8, ls=(0, (2, 2)))
fig.tight_layout(); fig.savefig("charts/ed_overall.png", dpi=240)

# Exhibit: funnel by gender (small multiples)
fig, axes = plt.subplots(1, 3, figsize=(9, 3.0), sharey=True)
for ax, (k, title) in zip(axes, [(FMR, "First-message rate"), (RR, "Reply rate"), (P, "Replied conversations / user")]):
    for i, g in enumerate(["female", "male"]):
        o = F[(g, k)]; c = W if g == "female" else M; v = o["rel_lift"] * 100
        ax.bar(i, v, color=c, width=.56)
        ax.plot([i, i], [o["rel_lo"] * 100, o["rel_hi"] * 100], color=INK, lw=1)
        ax.text(i, (o["rel_hi"] * 100 + 2) if v >= 0 else (o["rel_lo"] * 100 - 2), f"{v:+.0f}%",
                ha="center", va="bottom" if v >= 0 else "top", fontsize=10, fontweight="bold", color=INK)
    ax.axhline(0, color=INK2, lw=.8)
    ax.set_xticks([0, 1], ["Women", "Men"]); ax.set_ylim(-17, 36)
    ax.set_title(title, fontsize=10, color=INK, loc="left", pad=8)
    ax.grid(axis="y", color=GRID, lw=.8); ax.set_axisbelow(True)
for t, c in zip(axes[0].get_xticklabels() + axes[1].get_xticklabels() + axes[2].get_xticklabels(), [W, M] * 3):
    t.set_color(c); t.set_fontweight("bold")
axes[0].set_ylabel("Relative change vs control, %")
axes[1].annotate("", xy=(2.55, 0), xytext=(2.55, 0))
fig.tight_layout(w_pad=2.5); fig.savefig("charts/ed_funnel.png", dpi=240)

# Exhibit: novelty
nov = r["novelty"]
fig, ax = plt.subplots(figsize=(8, 3.2))
for g, c, lab in [("female", W, "Women"), ("male", M, "Men")]:
    s = sorted([o for o in nov if o["gender"] == g], key=lambda o: o["day"])
    x = [o["day"] for o in s]; y = [o["rel_lift"] * 100 for o in s]
    ax.fill_between(x, [o["rel_lo"] * 100 for o in s], [o["rel_hi"] * 100 for o in s], color=c, alpha=.10, lw=0)
    ax.plot(x, y, color=c, lw=2, marker="o", ms=6, mec="white", mew=1.5)
    ax.text(6.2, y[-1], lab, color=c, va="center", fontsize=10, fontweight="bold")
    ax.text(-0.15, y[0], f"{y[0]:+.0f}%", ha="right", va="center", fontsize=9, color=INK)
ax.axhline(0, color=INK2, lw=.8)
ax.set_xticks(range(7), [f"Day {i}" for i in range(7)]); ax.set_xlim(-0.75, 6.8)
ax.set_ylabel("First-message rate, change vs control, %")
ax.grid(axis="y", color=GRID, lw=.8); ax.set_axisbelow(True)
fig.tight_layout(); fig.savefig("charts/ed_novelty.png", dpi=240)
print("ok")
