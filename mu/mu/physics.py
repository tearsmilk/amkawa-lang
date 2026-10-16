"""Hair / skirt physics: each group is a damped spring that lags behind its inputs (head and body movement)
and hangs with gravity when the head tilts. The output parameter swings −1…1 (scaled to its range)."""
import math


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
            x += v
        return x, tilt

    def step(self, dt, values=None):
        """Advance the simulation and write the outputs into model.values (or `values`)."""
        values = self.model.values if values is None else values
        dt = max(1e-3, min(dt, 0.05))
        for g in self.model.physics:
            out = self.model.param(g.output)
            if out is None or not g.enabled:
                continue
            anchor, tilt = self.target(g, values)
            st = self.state.setdefault(g.id, [anchor, 0.0])
            # a few sub-steps keep stiff springs stable
            for _ in range(4):
                h = dt / 4
                acc = (anchor - st[0]) * g.stiffness - st[1] * g.damping
                st[1] += acc * h
                st[0] += st[1] * h
            swing = (st[0] - anchor) * g.scale + math.sin(tilt * 0.5) * g.gravity * 0.6
            swing = max(-1.0, min(1.0, swing))
            span = max(abs(out.max - out.default), abs(out.min - out.default)) or 1.0
            values[g.output] = out.clamp(out.default + swing * span)

    def settle(self, values=None, seconds=1.5):
        for _ in range(int(seconds / 0.02)):
            self.step(0.02, values)
