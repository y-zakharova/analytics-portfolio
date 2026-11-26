"""
Simulator for a portfolio case study: reciprocal ranking of a dating feed.
Fictional dating app "Driftly". Everything here is SIMULATED.

World: women browse a feed of men. A mutual match needs her like AND his like back.
- Her like depends on his attractiveness, shared interests, distance, age gap.
- His like-back depends on her attractiveness and fit, he is pickier if he is very popular,
  and he answers less when his inbox is crowded (capacity effect).
"""
import numpy as np
import pandas as pd

NW, NM, POOL, SLOTS = 2500, 6000, 350, 25
sig = lambda x: 1 / (1 + np.exp(-x))


class World:
    def __init__(self, seed=3):
        rng = np.random.default_rng(seed)
        self.rng = rng
        self.w_attr = rng.normal(0, 1, NW)
        self.m_attr = rng.normal(0, 1, NM)
        self.m_pick = rng.normal(0, 0.6, NM)                       # individual pickiness
        self.w_photo = self.w_attr + rng.normal(0, 0.5, NW)        # observable proxies
        self.m_photo = self.m_attr + rng.normal(0, 0.5, NM)
        self.w_age = rng.integers(21, 40, NW); self.m_age = rng.integers(21, 42, NM)
        self.w_int = rng.random((NW, 12)) < 0.25; self.m_int = rng.random((NM, 12)) < 0.25
        self.pool = np.stack([rng.choice(NM, POOL, replace=False) for _ in range(NW)])   # men near each woman
        self.dist = rng.gamma(2, 7, (NW, POOL))
        w = np.repeat(np.arange(NW), POOL); m = self.pool.ravel()
        self.shared = (self.w_int[w] & self.m_int[m]).sum(1).reshape(NW, POOL)
        self.age_gap = (self.m_age[m] - self.w_age[w]).reshape(NW, POOL)
        u_w = rng.normal(0, 0.5, NW)[:, None]
        self.p_her = sig(-1.9 + 1.1 * self.m_attr[self.pool] + 0.30 * self.shared - 0.035 * self.dist
                         - 0.12 * np.abs(self.age_gap - 2) + u_w)
        self.p_his = sig(-0.2 + 0.9 * self.w_attr[:, None] + 0.35 * self.shared - 0.02 * self.dist
                         - 0.08 * np.abs(self.age_gap - 2) - 0.55 * self.m_attr[self.pool] - self.m_pick[self.pool])
        self.CAP = 12.0                                            # inbox capacity (likes/day he can handle)

    def run_day(self, order_fn, seen, rng, day):
        """show SLOTS unseen candidates per woman ranked by order_fn; return impression log for the day."""
        scores = order_fn(day)                                     # (NW, POOL) higher = shown first
        scores = np.where(seen, -np.inf, scores)
        top = np.argsort(-scores, axis=1)[:, :SLOTS]
        wi = np.repeat(np.arange(NW), SLOTS); pj = top.ravel()
        seen[wi, pj] = True
        her = rng.random(wi.size) < self.p_her[wi, pj]
        men = self.pool[wi, pj]
        received = np.bincount(men[her], minlength=NM)            # likes each man got today
        cap = 1 / (1 + received[men] / self.CAP)
        his = her & (rng.random(wi.size) < self.p_his[wi, pj] * cap)
        return pd.DataFrame({"day": day, "woman_id": wi, "man_id": men, "slot": pj, "position": np.tile(np.arange(SLOTS), NW),
                             "her_like": her.astype(np.int8), "mutual": his.astype(np.int8)})
