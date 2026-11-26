"""
Synthetic dataset for a portfolio A/B-test case study.
Fictional dating app "Driftly", test: "Conversation Starters"
(3 suggested opening lines on the match screen).
All data is SIMULATED. No real company data is used.
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(20261126)
N = 80_000
DAYS = 7  # observation window per user (D0..D6)
START = pd.Timestamp("2026-09-01")

# ---------- users ----------
uid = np.arange(100001, 100001 + N)
group = rng.choice(["control", "treatment"], size=N, p=[0.5, 0.5])
gender = rng.choice(["male", "female"], size=N, p=[0.62, 0.38])
platform = rng.choice(["ios", "android"], size=N, p=[0.55, 0.45])
is_new = rng.random(N) < 0.35
enroll_day = rng.integers(0, 14, size=N)          # enrollment over 14 days
enroll_date = START + pd.to_timedelta(enroll_day, unit="D")
male = gender == "male"
treat = group == "treatment"

# latent engagement (drives everything; also drives pre-period -> CUPED works)
eng = rng.lognormal(mean=0.0, sigma=0.55, size=N)

# ---------- pre-period (existing users only): replied convs in 28 days before ----------
pre_mu = np.where(male, 2.2, 3.4) * eng * 3.2
pre = np.where(is_new, np.nan, rng.poisson(pre_mu))

# ---------- daily activity ----------
base_matches = np.where(male, 0.55, 1.35) * eng            # matches/day
p_first = np.clip(np.where(male, 0.33, 0.18) * eng ** 0.25, 0.02, 0.9)
p_reply = np.clip(np.where(male, 0.38, 0.47) * eng ** 0.15, 0.02, 0.95)

# treatment effects (relative), novelty decays over days since exposure
lift_first_steady = np.where(male, 0.04, 0.18)
lift_first_novelty = np.where(male, 0.11, 0.16)
reply_lift = np.where(male, -0.07, -0.005)                 # templated openers from men get fewer replies

rows = []
tot = {k: np.zeros(N, dtype=int) for k in ["matches", "first_msgs", "replied"]}
activity_decay = np.array([1.0, 0.85, 0.75, 0.68, 0.63, 0.60, 0.58])
for d in range(DAYS):
    lam = base_matches * activity_decay[d] * rng.gamma(12, 1 / 12, size=N)
    m = rng.poisson(lam)
    novelty = lift_first_novelty * np.exp(-d / 1.3)
    pf = np.clip(p_first * (1 + treat * (lift_first_steady + novelty)), 0, 0.97)
    f = rng.binomial(m, pf)
    pr = np.clip(p_reply * (1 + treat * reply_lift), 0, 0.97)
    r = rng.binomial(f, pr)
    tot["matches"] += m
    tot["first_msgs"] += f
    tot["replied"] += r
    rows.append(pd.DataFrame({"user_id": uid, "day_since_enroll": d,
                              "matches": m, "first_messages_sent": f,
                              "conversations_with_reply": r}))

daily = pd.concat(rows, ignore_index=True)
daily = daily[daily.matches > 0].reset_index(drop=True)

# ---------- outcomes ----------
# D7 retention: depends on engagement + replied conversations (weak)
logit = -0.9 + 0.55 * np.log(eng) + 0.06 * np.minimum(tot["replied"], 15) + np.where(is_new, -0.35, 0.25)
retained_d7 = rng.random(N) < 1 / (1 + np.exp(-logit))

# premium purchase in 7 days (men mostly), no real treatment effect
p_prem = np.where(male, 0.042, 0.011) * np.clip(eng, 0.3, 3)
premium_7d = rng.random(N) < p_prem

# reports received on first messages (guardrail): tiny base rate, no real change
reports = rng.binomial(tot["first_msgs"], np.where(male, 0.0042, 0.0012))

users = pd.DataFrame({
    "user_id": uid, "group": group, "gender": gender, "platform": platform,
    "user_type": np.where(is_new, "new", "existing"),
    "enroll_date": enroll_date.date,
    "pre_replied_convs_28d": pre,
    "matches_7d": tot["matches"], "first_messages_7d": tot["first_msgs"],
    "conversations_with_reply_7d": tot["replied"],
    "reports_received_7d": reports,
    "retained_d7": retained_d7.astype(int), "premium_purchase_7d": premium_7d.astype(int),
})

users.to_csv("data/users.csv.gz", index=False)
daily.to_csv("data/daily_activity.csv.gz", index=False)
print(users.shape, daily.shape)
print(users.groupby(["group", "gender"])[["matches_7d", "first_messages_7d", "conversations_with_reply_7d", "retained_d7", "premium_purchase_7d"]].mean().round(3))
