"""
Synthetic data for a portfolio case study: diagnosing a revenue drop.
Fictional subscription dating app "Driftly". All data is SIMULATED.
Daily warehouse-style aggregates, 2025-07-01 .. 2025-09-30.
Planted events:
  - Android app 5.12 staged rollout from 2025-09-15; purchases fail more often on Android 14+ (billing bug)
  - iOS app 5.12 released 2025-09-10 with no issue (red herring)
  - Meta Ads paused from 2025-09-20 (fewer installs, a separate and known cause)
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
dates = pd.date_range("2025-07-01", "2025-09-30", freq="D")
dow = np.array([1.00, 0.97, 0.98, 1.02, 1.10, 1.16, 1.08])        # Mon..Sun activity multiplier

# ---------- installs by channel ----------
CHN = {"Meta Ads": 1500, "Google App Campaigns": 900, "TikTok Ads": 700, "Apple Search Ads": 500, "Organic": 1600}
inst = []
for d in dates:
    for ch, base in CHN.items():
        m = base * dow[d.dayofweek] * rng.normal(1, 0.05)
        if ch == "Meta Ads" and d >= pd.Timestamp("2025-09-20"):
            m *= 0.12                                                  # campaign paused, residual traffic
        for pf, share in [("android", 0.52), ("ios", 0.48)]:
            if ch == "Apple Search Ads":
                share = 1.0 if pf == "ios" else 0.0
            inst.append((d.date(), ch, pf, int(m * share)))
installs = pd.DataFrame(inst, columns=["date", "channel", "platform", "installs"])
daily_inst = installs.groupby(["date", "platform"]).installs.sum().unstack()
daily_inst.index = pd.to_datetime(daily_inst.index)

# ---------- segments ----------
SEG = []
for pf in ["android", "ios"]:
    for osb, osh in ([("Android 13 and older", 0.45), ("Android 14+", 0.55)] if pf == "android"
                     else [("iOS 17 and older", 0.30), ("iOS 18+", 0.70)]):
        for ct, cth, price in [("US", 0.45, 31.0), ("Tier-1 other", 0.30, 24.0), ("Rest of world", 0.25, 11.0)]:
            SEG.append((pf, osb, osh, ct, cth, price))

EXIST_DAU = {"android": 118_000, "ios": 96_000}
REL = {"ios": pd.Timestamp("2025-09-10"), "android": pd.Timestamp("2025-09-15")}

def adoption(pf, d):
    """share of the platform's active users on app 5.12 on date d."""
    k = (d - REL[pf]).days
    if k < 0:
        return 0.0
    if pf == "android":                                   # staged rollout: 10% -> 50% -> 100% availability
        avail = 0.10 if k < 3 else (0.50 if k < 7 else 1.0)
        return avail * (1 - np.exp(-(k + 1) / 2.5))
    return 1 - np.exp(-(k + 1) / 3.0)

rows = []
for d in dates:
    trend = 1 + 0.0004 * (d - dates[0]).days
    for pf, osb, osh, ct, cth, price in SEG:
        for ut in ["new", "existing"]:
            if ut == "existing":
                dau = EXIST_DAU[pf] * trend * dow[d.dayofweek] * osh * cth * rng.normal(1, 0.015)
            else:
                last7 = daily_inst[pf].loc[:d].tail(7).mean() * 7
                dau = last7 * 0.42 * osh * cth * rng.normal(1, 0.02)
            a = adoption(pf, d)
            for ver, vs in [("5.11", 1 - a), ("5.12", a)]:
                n = int(dau * vs)
                if n == 0:
                    continue
                pv_rate = 0.30 if ut == "new" else 0.085
                pv = rng.binomial(n, pv_rate)
                sel = rng.binomial(pv, 0.34 if ut == "new" else 0.27)
                att = rng.binomial(sel, 0.62)
                succ_p = 0.93 if pf == "android" else 0.95
                bug = pf == "android" and ver == "5.12" and osb == "Android 14+"
                if bug:
                    succ_p = 0.52
                    att = att + rng.binomial(att, 0.18)           # users retry after a failed payment
                pur = rng.binomial(att, succ_p) if not bug else rng.binomial(int(att / 1.18), succ_p)
                rev = pur * price * rng.normal(1, 0.03)
                rows.append((d.date(), pf, ver, osb, ut, ct, n, pv, sel, att, pur, round(rev, 2)))

df = pd.DataFrame(rows, columns=["date", "platform", "app_version", "os_version", "user_type", "country_group",
                                 "dau", "paywall_views", "plan_selected", "purchase_attempts", "purchases",
                                 "revenue_usd"])
df.to_csv("data/daily_segments.csv", index=False)
installs.to_csv("data/installs_by_channel.csv", index=False)
d = df.groupby("date")[["dau", "purchases", "revenue_usd"]].sum()
print(df.shape, installs.shape)
print(d.iloc[[0, 30, 60, 70, 75, 80, 85, 91]])
