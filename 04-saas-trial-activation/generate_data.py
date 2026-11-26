"""
Synthetic data for a portfolio case study: B2B SaaS trial activation ("aha moment").
Fictional team task-management tool "Northdesk". All data is SIMULATED.
trials.csv: one row per 14-day trial workspace (Apr-Sep 2025): firmographics, actions in the first 3 days and
over the whole trial, conversion and starting MRR.
Planted truth: inviting teammates is causal; creating many projects and using the mobile app mostly reflect intent.
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(21)
N = 12_000
sig = lambda x: 1 / (1 + np.exp(-x))
size = rng.choice(["1", "2-5", "6-20", "21-100", "100+"], N, p=[0.22, 0.30, 0.26, 0.15, 0.07])
size_n = pd.Series(size).map({"1": 1, "2-5": 4, "6-20": 12, "21-100": 45, "100+": 150}).values
channel = rng.choice(["Organic search", "Paid search", "Referral", "Content", "Partner"], N, p=[.32, .28, .14, .16, .10])
industry = rng.choice(["Agency", "Software", "Consulting", "E-commerce", "Other"], N, p=[.24, .26, .18, .14, .18])
intent = rng.normal(0, 1, N) + np.select([channel == "Referral", channel == "Partner", channel == "Paid search"], [0.4, 0.3, -0.2], 0)

# observable signals of intent collected at signup (imperfect)
sv = intent + rng.normal(0, 0.45, N)
signup_stage = np.select([sv < -0.5, sv < 0.7], ["Just exploring", "Evaluating tools"], "Ready to switch")
pricing_visit = rng.random(N) < sig(-0.6 + 1.0 * intent)
can_invite = size_n > 1
lam_inv = np.where(can_invite, np.minimum(np.log2(size_n) * 0.55, 3.0) * np.exp(0.55 * intent), 0)
inv3 = rng.poisson(lam_inv)
inv_total = inv3 + rng.poisson(lam_inv * 0.6)
proj3 = rng.poisson(1.3 * np.exp(0.6 * intent))
proj_total = proj3 + rng.poisson(1.0 * np.exp(0.6 * intent))
tasks3 = rng.poisson(6 * np.exp(0.5 * intent) * (1 + 0.4 * np.minimum(inv3, 4)))
integ3 = rng.random(N) < sig(-1.6 + 0.8 * intent + 0.3 * (size_n > 5))
mobile3 = rng.random(N) < sig(-1.0 + 0.9 * intent)
active_days = np.clip(rng.poisson(4 * np.exp(0.35 * intent) * (1 + 0.15 * np.minimum(inv3, 4))), 1, 14)
first_inv_day = np.where(inv_total > 0, np.where(inv3 > 0, rng.integers(0, 3, N), rng.integers(3, 14, N)), -1)

logit = (-2.6 + 0.85 * intent
         + np.select([inv3 >= 2, inv3 == 1], [0.95, 0.35], 0)
         + 0.08 * np.minimum(proj3, 5)
         + 0.45 * integ3 + 0.0 * mobile3
         + pd.Series(size).map({"1": -0.2, "2-5": 0.1, "6-20": 0.25, "21-100": 0.2, "100+": -0.1}).values)
converted = rng.random(N) < sig(logit)
seats = np.where(converted, np.maximum(1, np.minimum(size_n, 1 + inv_total + rng.poisson(1, N))), 0)
mrr = np.where(converted, seats * 12.0, 0)

start = pd.Timestamp("2025-04-01") + pd.to_timedelta(rng.integers(0, 183, N), unit="D")
df = pd.DataFrame({
    "workspace_id": np.arange(70001, 70001 + N), "trial_start": start.date, "company_size": size, "channel": channel,
    "industry": industry, "signup_stage": signup_stage, "visited_pricing_before_signup": pricing_visit.astype(int),
    "invites_d0_2": inv3, "projects_d0_2": proj3, "tasks_d0_2": tasks3,
    "integration_d0_2": integ3.astype(int), "mobile_app_d0_2": mobile3.astype(int),
    "invites_total": inv_total, "projects_total": proj_total, "active_days": active_days,
    "first_invite_day": first_inv_day, "converted": converted.astype(int), "seats": seats, "starting_mrr_usd": mrr,
})
df.to_csv("data/trials.csv", index=False)
print(df.converted.mean(), df.groupby(np.minimum(df.invites_d0_2, 4)).converted.agg(["mean", "size"]))

# ground truth for the final sanity check (only knowable because the data is simulated)
import json
base = logit - np.select([inv3 >= 2, inv3 == 1], [0.95, 0.35], 0)
elig = can_invite
true_inv = (sig(base + 0.95) - sig(base))[elig].mean()                       # >=2 invites vs none
b2 = logit - 0.08 * np.minimum(proj3, 5)
true_proj = (sig(b2 + 0.08 * 3) - sig(b2 + 0.08 * np.minimum(proj3, 2).clip(max=2)))[proj3 < 3].mean()
true_mob = 0.0
true_int = (sig(logit - 0.45 * integ3 + 0.45) - sig(logit - 0.45 * integ3)).mean()
json.dump(dict(invites2_vs_0=true_inv, projects3=true_proj, mobile=true_mob, integration=true_int),
          open("data/_true_effects_for_validation_only.json", "w"), indent=1)
