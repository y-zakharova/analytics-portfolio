"""
Synthetic data for a portfolio case study: behavioral user segmentation.
Fictional subscription dating app "Driftly". All data is SIMULATED.
users.csv: 30-day behavior features (1-30 Sep 2025) + outcomes in the following 30 days.
The latent segment is NOT included in the output.
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(11)
N = 60_000
# latent segments: (share, params)
SEG = {
    "power":      0.08, "selective": 0.17, "swiper": 0.27,
    "lurker":     0.20, "fading":    0.16, "newbie":   0.12,
}
seg = rng.choice(list(SEG), N, p=list(SEG.values()))
P = {  # active_days, swipes/active day, right-swipe rate, msgs per match, reply rate, photos, premium p, male p, tenure days
    "power":     (24, 120, 0.35, 1.6, 0.55, 5.0, 0.55, 0.70, 400),
    "selective": (17, 35, 0.12, 1.9, 0.62, 4.5, 0.10, 0.35, 300),
    "swiper":    (14, 160, 0.62, 0.35, 0.28, 3.0, 0.06, 0.88, 220),
    "lurker":    (12, 18, 0.22, 0.30, 0.40, 2.0, 0.02, 0.45, 260),
    "fading":    (4, 40, 0.35, 0.50, 0.35, 3.2, 0.04, 0.60, 330),
    "newbie":    (8, 70, 0.40, 0.60, 0.40, 1.6, 0.03, 0.60, 8),
}
rows = {k: np.zeros(N) for k in ["active_days", "swipes", "right_swipe_rate", "matches", "messages_sent",
                                  "reply_rate", "photos", "bio_filled", "premium", "male", "tenure_days",
                                  "push_enabled", "sessions"]}
for s, (ad, spd, rsr, mpm, rr, ph, prem, male, ten) in P.items():
    i = seg == s; n = i.sum()
    a = np.clip(rng.normal(ad, ad * 0.28, n), 1, 30).round()
    sw = rng.gamma(3, spd * a / 3)
    r = np.clip(rng.beta(rsr * 12, (1 - rsr) * 12, n), 0.01, 0.99)
    m = rng.binomial(sw.astype(int), np.where(rng.random(n) < male, 1, 3.2) * 0.012 * (0.5 + (1 - r)))  # selective -> better match odds
    rows["active_days"][i] = a; rows["swipes"][i] = sw.round()
    rows["right_swipe_rate"][i] = r
    rows["male"][i] = rng.random(n) < male
    rows["matches"][i] = m
    rows["messages_sent"][i] = rng.poisson(m * mpm)
    rows["reply_rate"][i] = np.clip(rng.beta(rr * 10, (1 - rr) * 10, n), 0, 1)
    rows["photos"][i] = np.clip(rng.poisson(ph, n), 0, 9)
    rows["bio_filled"][i] = rng.random(n) < np.clip(ph / 5.5, 0, 0.95)
    rows["premium"][i] = rng.random(n) < prem
    rows["tenure_days"][i] = np.maximum(1, rng.gamma(2, ten / 2, n)).round() if s != "newbie" else rng.integers(1, 30, n)
    rows["push_enabled"][i] = rng.random(n) < {"fading": 0.35, "lurker": 0.55}.get(s, 0.75)
    rows["sessions"][i] = rng.poisson(a * {"power": 4.5, "swiper": 3.8, "lurker": 2.5}.get(s, 2.2))
df = pd.DataFrame(rows)
df.loc[df.matches == 0, "reply_rate"] = np.nan        # no conversations -> undefined
for c in ["active_days", "swipes", "matches", "messages_sent", "photos", "tenure_days", "sessions"]:
    df[c] = df[c].astype(int)
for c in ["male", "premium", "bio_filled", "push_enabled"]:
    df[c] = df[c].astype(int)
df.insert(0, "user_id", np.arange(500001, 500001 + N))
df.insert(1, "gender", np.where(df.pop("male") == 1, "male", "female"))

# outcomes in the NEXT 30 days (Oct 2025): retention and net revenue
base = {"power": 0.86, "selective": 0.74, "swiper": 0.52, "lurker": 0.45, "fading": 0.18, "newbie": 0.40}
p_ret = np.array([base[s] for s in seg]) + 0.01 * np.clip(df.photos - 3, -3, 3)
df["retained_next_30d"] = (rng.random(N) < np.clip(p_ret, 0.02, 0.98)).astype(int)
arpu = {"power": 14.0, "selective": 2.6, "swiper": 1.4, "lurker": 0.35, "fading": 0.25, "newbie": 0.9}
df["net_revenue_next_30d"] = np.round(rng.gamma(0.25, np.array([arpu[s] for s in seg]) / 0.25), 2)
df.to_csv("data/users.csv.gz", index=False)
pd.Series(seg).to_csv("data/_latent_segment_for_validation_only.csv", index=False, header=["segment"])
print(df.describe().T.round(2))
