"""
Synthetic data for a portfolio dashboard: subscription metrics of a fictional dating app ("Driftly").
All data is SIMULATED. Output: data/dashboard_data.json (compact, columnar) + CSVs for reference.
Shown window: 2024-01-01 .. 2025-12-31. Subscriptions are simulated from 2023-01-01 so the active base is realistic.
Planted events:
  - 2025-07-01: monthly price $12.99 -> $14.99, annual $79.99 -> $89.99 for new subscribers (slightly lower trial->paid)
  - 2025-10-01: new paywall on iOS (more trial starts); 2025-11-15: same paywall on Android
  - TikTok Ads scaled from 2025-03 (more installs, weaker retention)
"""
import json
import numpy as np
import pandas as pd

rng = np.random.default_rng(2025)
SIM0, SHOW0, END = pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31")
days = pd.date_range(SIM0, END, freq="D"); D = len(days)
t = np.arange(D)
PLAT = ["iOS", "Android"]; REG = ["US", "Tier-1 other", "Rest of world"]; CH = ["Organic", "Meta Ads", "Google Ads", "TikTok Ads"]
PLAN = ["Monthly", "Annual"]
combos = [(p, r, c) for p in range(2) for r in range(3) for c in range(4)]
dow = np.array([1.0, 0.96, 0.97, 1.0, 1.06, 1.12, 1.09])[days.dayofweek]
season = 1 + 0.06 * np.sin(2 * np.pi * (days.dayofyear - 20) / 365)          # winter peak
growth = 1 + 0.00035 * t

base_inst = {"Organic": 900, "Meta Ads": 700, "Google Ads": 450, "TikTok Ads": 250}
reg_share = [0.40, 0.30, 0.30]; plat_share = {0: 0.55, 1: 0.45}
price_m = np.where(days < "2025-07-01", 12.99, 14.99); price_a = np.where(days < "2025-07-01", 79.99, 89.99)
reg_price = [1.0, 0.85, 0.45]                                                   # regional price levels
ret_m = {"Organic": 0.83, "Meta Ads": 0.78, "Google Ads": 0.79, "TikTok Ads": 0.66}
ret_reg = [0.02, 0.0, -0.05]

funnel = np.zeros((D, len(combos), 4), dtype=np.int64)                          # installs, paywall, trials, paid
subs = []
for k, (p, r, c) in enumerate(combos):
    ch = CH[c]
    scale = base_inst[ch] * reg_share[r] * plat_share[p]
    if ch == "TikTok Ads":
        scale = scale * np.where(days >= "2025-03-01", 1 + np.minimum((days - pd.Timestamp("2025-03-01")).days, 120) / 60, 1)
    lam = scale * dow * season * growth
    inst = rng.poisson(lam)
    pv = rng.binomial(inst, 0.56)
    tr_rate = np.full(D, 0.24 if p == 0 else 0.20)
    tr_rate = np.where(days >= ("2025-10-01" if p == 0 else "2025-11-15"), tr_rate * 1.17, tr_rate)
    tr = rng.binomial(pv, tr_rate)
    conv = np.full(D, {0: 0.40, 1: 0.34}[p] * {"TikTok Ads": 0.8}.get(ch, 1.0) * [1.05, 1.0, 0.85][r])
    conv = np.where(days >= "2025-07-01", conv * 0.95, conv)
    paid = rng.binomial(tr, conv)
    funnel[:, k] = np.stack([inst, pv, tr, paid], 1)
    # individual subscriptions
    di = np.repeat(t, paid)
    annual = rng.random(di.size) < (0.32 if p == 0 else 0.22)
    s = np.clip(ret_m[ch] + ret_reg[r] + np.where(days[di] >= "2025-07-01", -0.015, 0), 0.3, 0.95)
    first = s - 0.12
    # monthly: number of paid periods (geometric with lower first renewal)
    n_m = 1 + np.where(rng.random(di.size) < first, 1 + rng.geometric(1 - s) - 1, 0)
    # annual: renew each year with prob 0.45 (TikTok 0.3)
    pa = 0.3 if ch == "TikTok Ads" else 0.45
    n_a = 1 + (rng.random(di.size) < pa) + 0
    n_a = n_a + ((n_a == 2) & (rng.random(di.size) < pa))
    length = np.where(annual, n_a * 365, n_m * 30)
    price = np.where(annual, price_a[di], price_m[di]) * reg_price[r]
    subs.append(pd.DataFrame({"combo": k, "plan": annual.astype(int), "start": di, "end": di + length,
                              "n_pay": np.where(annual, n_a, n_m), "period": np.where(annual, 365, 30), "price": price}))
subs = pd.concat(subs, ignore_index=True)
print("subscriptions simulated:", len(subs))

# ---------- daily subscription aggregates per combo x plan ----------
S0 = (SHOW0 - SIM0).days; W = D - S0
nC, nP = len(combos), 2
active = np.zeros((D + 4000, nC, nP)); mrr = np.zeros((D + 4000, nC, nP))
newp = np.zeros((D, nC, nP)); churn = np.zeros((D + 4000, nC, nP)); rev = np.zeros((D + 4000, nC, nP))
ci, pl, st, en = subs.combo.values, subs.plan.values, subs.start.values, subs.end.values
mval = np.where(pl == 1, subs.price.values / 12, subs.price.values)
np.add.at(active, (st, ci, pl), 1); np.add.at(active, (en, ci, pl), -1)
np.add.at(mrr, (st, ci, pl), mval); np.add.at(mrr, (en, ci, pl), -mval)
np.add.at(newp, (st, ci, pl), 1)
np.add.at(churn, (en, ci, pl), 1)
pay_rep = np.repeat(np.arange(len(subs)), subs.n_pay.values)
pay_k = np.concatenate([np.arange(n) for n in subs.n_pay.values])
pay_day = st[pay_rep] + pay_k * subs.period.values[pay_rep]
np.add.at(rev, (pay_day, ci[pay_rep], pl[pay_rep]), subs.price.values[pay_rep])
active = np.cumsum(active, 0)[:D]; mrr = np.cumsum(mrr, 0)[:D]
churn = churn[:D]; rev = rev[:D]

# ---------- monthly cohorts (shown window) ----------
months = pd.period_range("2024-01", "2025-12", freq="M"); M = len(months)
sd = days[st]; smonth = sd.to_period("M")
coh = np.zeros((M, M, nC, nP), dtype=np.int64)                                  # cohort, age, combo, plan
for mi, mth in enumerate(months):
    sel = smonth == mth
    for age in range(M - mi):
        ref = (mth + age).to_timestamp() + pd.offsets.MonthBegin(0)
        # active at the same day-of-month offset: use cohort month start + age months (+ day)
        alive = sel & (en > st + age * 30.4)
        if age == 0:
            alive = sel
        np.add.at(coh[mi, age], (ci[alive], pl[alive]), 1)

out = {
    "meta": {"start": str(SHOW0.date()), "days": int(W), "platforms": PLAT, "regions": REG, "channels": CH, "plans": PLAN,
             "combos": [[p, r, c] for p, r, c in combos], "months": [str(m) for m in months],
             "events": [{"date": "2025-07-01", "label": "Price +15% (new subs)"},
                        {"date": "2025-10-01", "label": "New paywall · iOS"},
                        {"date": "2025-11-15", "label": "New paywall · Android"}]},
    # funnel: [day][combo] -> [installs, paywall, trials, paid]
    "funnel": funnel[S0:].tolist(),
    # subs: [day][combo][plan] -> [active, mrr*100, new, churned, revenue*100]
    "subs": np.stack([active[S0:], np.round(mrr[S0:] * 100), newp[S0:], churn[S0:], np.round(rev[S0:] * 100)], -1).astype(np.int64).tolist(),
    "cohorts": coh.tolist(),
}
s = json.dumps(out, separators=(",", ":"))
open("data/dashboard_data.json", "w").write(s)
print("json size MB:", round(len(s) / 1e6, 2))

# reference totals for verification
tot = pd.DataFrame({"date": days[S0:], "active": active[S0:].sum((1, 2)), "mrr": mrr[S0:].sum((1, 2)),
                    "new": newp[S0:].sum((1, 2)), "churned": churn[S0:].sum((1, 2)), "revenue": rev[S0:].sum((1, 2)),
                    "installs": funnel[S0:, :, 0].sum(1), "trials": funnel[S0:, :, 2].sum(1), "paid": funnel[S0:, :, 3].sum(1)})
tot.to_csv("data/daily_totals.csv", index=False)
print(tot.iloc[[0, 180, 364, 455, 547]].round(0).to_string())
