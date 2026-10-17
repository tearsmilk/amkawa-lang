"""Physics: every group is a pendulum chain (Cubism-style). The inputs (head / body parameters) shake its root
sideways and tilt the gravity; each link is an angular spring towards its parent link and the hanging
direction, so a quick head turn sends a delayed wave down the chain. Outputs read the bend at a link
(«angle») or how far a vertex swung sideways («x») and write it into parameters, −1…1 scaled to their range."""
import math

BEND = math.pi / 6       # 30° of bend = full output
SUBSTEPS = 8


class _Chain:
    def __init__(self, n, anchor):
        self.n = n
        L = 1.0 / n
        self.p = [[anchor, i * L] for i in range(n + 1)]   # vertices (x, y), y down
        self.q = [list(v) for v in self.p]                  # previous positions (Verlet)

    def angles(self):
        out = []
        for i in range(1, self.n + 1):
            dx = self.p[i][0] - self.p[i - 1][0]
            dy = self.p[i][1] - self.p[i - 1][1]
            out.append(math.atan2(dx, dy))
        return out


class PhysicsSim:
    def __init__(self, model):
        self.model = model
        self.state = {}

    def reset(self):
        self.state.clear()

    def target(self, g, values):
        x = 0.0
        tilt = 0.0
        for inp in g.inputs:
            p = self.model.param(inp.get("param"))
            if p is None:
                continue
            v = p.norm(values.get(p.id, p.default)) * inp.get("weight", 1.0)
            if inp.get("kind") == "angle":
                tilt += v
            else:
                x += v
        return x, tilt

    def step(self, dt, values=None):
        """Advance the simulation and write the outputs into model.values (or `values`)."""
        values = self.model.values if values is None else values
        dt = max(1e-3, min(dt, 0.05))
        for g in self.model.physics:
            outs = [o for o in g.out_list() if self.model.param(o.get("param")) is not None]
            if not outs or not g.enabled:
                continue
            x_in, tilt = self.target(g, values)
            n = max(1, int(g.segments))
            L = 1.0 / n
            anchor = x_in * 0.3
            st = self.state.get(g.id)
            if st is None or st.n != n:
                st = self.state[g.id] = _Chain(n, anchor)
            hang = -tilt * 0.6 * g.gravity            # the hair hangs straight down while the head tilts
            k = max(1.0, g.stiffness)
            keep = math.exp(-max(0.1, g.damping) * 1.6 * dt / SUBSTEPS)
            h = dt / SUBSTEPS
            p0x = st.p[0][0]
            for sub in range(SUBSTEPS):
                st.p[0] = [p0x + (anchor - p0x) * (sub + 1) / SUBSTEPS, 0.0]
                parent_ang = 0.0
                for i in range(1, n + 1):
                    P, Q, A = st.p[i], st.q[i], st.p[i - 1]
                    rest = hang if i == 1 else 0.55 * parent_ang + 0.45 * hang
                    rx = A[0] + L * math.sin(rest)
                    ry = A[1] + L * math.cos(rest)
                    vx = (P[0] - Q[0]) * keep
                    vy = (P[1] - Q[1]) * keep
                    st.q[i] = [P[0], P[1]]
                    nx = P[0] + vx + (rx - P[0]) * k * h * h
                    ny = P[1] + vy + (ry - P[1]) * k * h * h
                    # keep the link length
                    dx, dy = nx - A[0], ny - A[1]
                    dl = math.hypot(dx, dy) or 1e-9
                    st.p[i] = [A[0] + dx / dl * L, A[1] + dy / dl * L]
                    parent_ang = math.atan2(st.p[i][0] - A[0], st.p[i][1] - A[1])
            th = st.angles()
            for o in outs:
                p = self.model.param(o["param"])
                v_i = max(1, min(n, int(o.get("vertex", n))))
                if o.get("kind") == "x":
                    val = (st.p[v_i][0] - st.p[0][0]) / (v_i * L) / math.sin(BEND)
                else:
                    bend = th[v_i - 1] - (th[v_i - 2] if v_i > 1 else 0.0)
                    val = bend / BEND
                val *= g.scale * float(o.get("scale", 1.0))
                val = max(-1.0, min(1.0, val))
                span = max(abs(p.max - p.default), abs(p.min - p.default)) or 1.0
                values[p.id] = p.clamp(p.default + val * span)

    def chain_points(self, gid):
        """Current link angles of a group (for drawing the pendulum)."""
        st = self.state.get(gid)
        return st.angles() if st else []

    def settle(self, values=None, seconds=1.5):
        for _ in range(int(seconds / 0.02)):
            self.step(0.02, values)
