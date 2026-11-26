"""Logged data from the production feed: popularity ranking with 20% random exploration, 14 days."""
import numpy as np
import pandas as pd
from sim import World, NW, NM, POOL

W = World()
rng = np.random.default_rng(99)
seen = np.zeros((NW, POOL), bool)
# production ranker: man's popularity proxy (photo score) + noise; 20% of slots explore at random
EXPL = {}
def prod_order(day):
    s = W.m_photo[W.pool] + rng.normal(0, 0.3, (NW, POOL))
    r = rng.random((NW, POOL)); r[seen] = -1                  # 5 of 25 slots: random unseen candidates
    idx = np.argsort(-r, axis=1)[:, :5]
    explore = np.zeros((NW, POOL), bool); explore[np.arange(NW)[:, None], idx] = True
    EXPL[day] = explore
    return np.where(explore, 100.0, s)
parts = []
for d in range(14):
    x = W.run_day(prod_order, seen, rng, d)
    x["is_exploration"] = EXPL[d][x.woman_id, x.slot].astype(np.int8)   # random slot: unbiased for offline evaluation
    parts.append(x)
logs = pd.concat(parts, ignore_index=True)

w = pd.DataFrame({"woman_id": np.arange(NW), "age": W.w_age, "photo_score": W.w_photo.round(3)})
m = pd.DataFrame({"man_id": np.arange(NM), "age": W.m_age, "photo_score": W.m_photo.round(3)})
pairs = logs[["woman_id", "slot"]].drop_duplicates()
logs["shared_interests"] = W.shared[logs.woman_id, logs.slot]
logs["distance_km"] = W.dist[logs.woman_id, logs.slot].round(1)
logs = logs.drop(columns="slot")
w.to_csv("data/women.csv", index=False); m.to_csv("data/men.csv", index=False)
logs.to_csv("data/impressions.csv.gz", index=False)
print(logs.shape, logs.her_like.mean(), logs.mutual.mean(), logs.mutual.sum() / logs.her_like.sum())
