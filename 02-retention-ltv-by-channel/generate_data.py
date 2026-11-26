"""
Synthetic data for a portfolio case study: retention and LTV by acquisition channel.
Fictional subscription dating app "Driftly". All data is SIMULATED.
Installs: Jan-Dec 2025 (12 monthly cohorts). Data snapshot: 2026-03-31.
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
SNAP = pd.Timestamp("2026-03-31")
PRICE = 29.99                                  # monthly subscription, gross

# channel parameters (constant over the year -> within-channel quality is stable)
CH = pd.DataFrame({
    #               never-return share, mean lifetime (days), 30d payer conv, 1st renewal, later renewals, base CPI
    "channel":  ["Apple Search Ads", "Meta Ads", "Google App Campaigns", "Influencers", "TikTok Ads", "Organic"],
    "z":        [0.52, 0.48, 0.50, 0.42, 0.38, 0.45],
    "mu":       [150, 90, 80, 55, 35, 160],
    "conv":     [0.075, 0.050, 0.045, 0.035, 0.020, 0.065],
    "s1":       [0.70, 0.62, 0.60, 0.55, 0.45, 0.70],
    "s":        [0.82, 0.75, 0.74, 0.68, 0.60, 0.82],
    "cpi":      [4.50, 3.20, 2.40, 2.80, 1.45, 0.0],
}).set_index("channel")

# install mix shifts toward TikTok over the year (it looked cheap)
months = pd.date_range("2025-01-01", periods=12, freq="MS")
t = np.linspace(0, 1, 12)
share = pd.DataFrame({
    "Apple Search Ads":     0.14 - 0.04 * t,
    "Meta Ads":             0.30 - 0.08 * t,
    "Google App Campaigns": 0.16 - 0.04 * t,
    "Influencers":          0.07 + 0.00 * t,
    "TikTok Ads":           0.08 + 0.28 * t,
    "Organic":              0.25 - 0.12 * t,
}, index=months)
share = share.div(share.sum(axis=1), axis=0)
total_installs = (11000 + 7000 * t) * rng.normal(1, 0.03, 12)

users, txns, spend = [], [], []
uid = 1_000_000
for mi, m in enumerate(months):
    days_in = m.days_in_month
    for ch, row in CH.iterrows():
        n = int(total_installs[mi] * share.loc[m, ch])
        inst = m + pd.to_timedelta(rng.integers(0, days_in, n), unit="D")
        ids = np.arange(uid, uid + n); uid += n
        platform = np.where(ch == "Apple Search Ads", "ios", rng.choice(["ios", "android"], n, p=[0.5, 0.5]))
        # activity lifetime: never return (0) or exponential lifetime, small month noise
        mu = row.mu * rng.normal(1, 0.04)
        never = rng.random(n) < row.z * rng.normal(1, 0.02)
        life = np.where(never, 0, np.ceil(rng.exponential(mu, n))).astype(int)
        obs = (SNAP - inst).days.values
        last_active = np.minimum(life, obs)                  # censored at snapshot
        users.append(pd.DataFrame({"user_id": ids, "install_date": inst.date, "channel": ch, "platform": platform,
                                   "last_active_day": last_active, "is_censored": (life > obs).astype(int)}))
        # subscriptions
        payer = rng.random(n) < row.conv * rng.normal(1, 0.05)
        for i in np.where(payer)[0]:
            d = int(min(rng.exponential(4), 29))
            if d > obs[i]:
                continue
            k, date = 0, inst[i] + pd.Timedelta(days=d)
            while date <= SNAP:
                txns.append((ids[i], date.date(), k, PRICE))
                p = row.s1 if k == 0 else row.s
                if rng.random() > p:
                    break
                k += 1; date = date + pd.Timedelta(days=30)
        if row.cpi > 0:
            cpi = row.cpi * (1 + (0.35 * t[mi] if ch == "TikTok Ads" else 0)) * rng.normal(1, 0.04)
            spend.append((m.date(), ch, n, round(n * cpi, 2)))

users = pd.concat(users, ignore_index=True)
txns = pd.DataFrame(txns, columns=["user_id", "charge_date", "renewal_number", "gross_amount_usd"])
spend = pd.DataFrame(spend, columns=["month", "channel", "installs", "spend_usd"])
users.to_csv("data/users.csv.gz", index=False)
txns.to_csv("data/transactions.csv", index=False)
spend.to_csv("data/marketing_spend.csv", index=False)
print(users.shape, txns.shape, spend.shape)
print(users.groupby("channel").size())
