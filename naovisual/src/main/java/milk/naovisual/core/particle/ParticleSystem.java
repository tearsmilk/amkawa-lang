package milk.naovisual.core.particle;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import milk.naovisual.core.render.Render3D;
import milk.naovisual.core.util.ColorUtil;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderContext;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Random;

/** Собственные частицы в мире: билборды с гравитацией, затуханием и формами. */
public final class ParticleSystem {
    public enum Shape { SQUARE, DIAMOND, HEART, BUBBLE, STAR }

    public static final class Particle {
        public double x, y, z, px, py, pz, vx, vy, vz;
        public float size, gravity, drag, spin;
        public int color, life, maxLife;
        public Shape shape;
        public boolean collide;
    }

    private static final List<Particle> PARTICLES = new ArrayList<>();
    private static final Random RNG = new Random();
    private static final int MAX = 2000;

    private ParticleSystem() {}

    public static Random random() { return RNG; }

    public static Particle spawn(double x, double y, double z, double vx, double vy, double vz, float size, int color, int life, Shape shape) {
        Particle p = new Particle();
        p.x = p.px = x; p.y = p.py = y; p.z = p.pz = z;
        p.vx = vx; p.vy = vy; p.vz = vz;
        p.size = size; p.color = color; p.life = 0; p.maxLife = Math.max(1, life);
        p.shape = shape; p.gravity = 0.02f; p.drag = 0.98f;
        synchronized (PARTICLES) {
            if (PARTICLES.size() >= MAX) PARTICLES.remove(0);
            PARTICLES.add(p);
        }
        return p;
    }

    public static void tick() {
        synchronized (PARTICLES) {
            Iterator<Particle> it = PARTICLES.iterator();
            var mc = net.minecraft.client.Minecraft.getInstance();
            while (it.hasNext()) {
                Particle p = it.next();
                p.px = p.x; p.py = p.y; p.pz = p.z;
                p.vy -= p.gravity;
                p.vx *= p.drag; p.vy *= p.drag; p.vz *= p.drag;
                double nx = p.x + p.vx, ny = p.y + p.vy, nz = p.z + p.vz;
                if (p.collide && mc.level != null) {
                    var pos = net.minecraft.core.BlockPos.containing(nx, ny, nz);
                    if (!mc.level.getBlockState(pos).getCollisionShape(mc.level, pos).isEmpty()) {
                        p.vx *= 0.5; p.vz *= 0.5; p.vy = Math.abs(p.vy) * 0.4;
                        ny = p.y;
                    }
                }
                p.x = nx; p.y = ny; p.z = nz;
                if (++p.life >= p.maxLife) it.remove();
            }
        }
    }

    public static int count() { synchronized (PARTICLES) { return PARTICLES.size(); } }
    public static void clear() { synchronized (PARTICLES) { PARTICLES.clear(); } }

    public static void render(WorldRenderContext ctx) {
        List<Particle> copy;
        synchronized (PARTICLES) { if (PARTICLES.isEmpty()) return; copy = new ArrayList<>(PARTICLES); }
        float partial = Render3D.partial();
        PoseStack ps = ctx.matrices();
        Render3D.begin(ctx);
        VertexConsumer vc = Render3D.quads(ctx);
        for (Particle p : copy) {
            float t = (p.life + partial) / p.maxLife;
            float alpha = t < 0.15f ? t / 0.15f : t > 0.6f ? 1f - (t - 0.6f) / 0.4f : 1f;
            int c = ColorUtil.withAlpha(p.color, Math.round(ColorUtil.alpha(p.color) * Math.max(0, Math.min(1, alpha))));
            double x = p.px + (p.x - p.px) * partial, y = p.py + (p.y - p.py) * partial, z = p.pz + (p.z - p.pz) * partial;
            float size = p.size * (p.shape == Shape.BUBBLE ? 1f + t * 0.4f : 1f);
            drawShape(ps, vc, ctx, p.shape, x, y, z, size, c, t);
        }
        Render3D.end(ctx);
    }

    private static void drawShape(PoseStack ps, VertexConsumer vc, WorldRenderContext ctx, Shape shape, double x, double y, double z, float size, int color, float t) {
        switch (shape) {
            case SQUARE -> Render3D.billboard(ps, vc, ctx, x, y, z, size, color);
            case DIAMOND -> {
                Render3D.billboard(ps, vc, ctx, x, y, z, size * 0.7f, color);
                Render3D.billboard(ps, vc, ctx, x, y + size * 0.35, z, size * 0.3f, color);
                Render3D.billboard(ps, vc, ctx, x, y - size * 0.35, z, size * 0.3f, color);
            }
            case HEART -> {
                org.joml.Vector3fc left = Render3D.left(ctx);
                double ox = left.x() * size * 0.25, oy = left.y() * size * 0.25, oz = left.z() * size * 0.25;
                Render3D.billboard(ps, vc, ctx, x - ox, y + size * 0.15, z - oz, size * 0.5f, color);
                Render3D.billboard(ps, vc, ctx, x + ox, y + size * 0.15, z + oz, size * 0.5f, color);
                Render3D.billboard(ps, vc, ctx, x, y - size * 0.15, z, size * 0.55f, color);
            }
            case BUBBLE -> {
                Render3D.billboard(ps, vc, ctx, x, y, z, size, ColorUtil.withAlpha(color, ColorUtil.alpha(color) / 3));
                Render3D.billboard(ps, vc, ctx, x, y, z, size * 0.6f, color);
            }
            case STAR -> {
                Render3D.billboard(ps, vc, ctx, x, y, z, size * 0.4f, color);
                Render3D.billboard(ps, vc, ctx, x, y + size * 0.5, z, size * 0.25f, color);
                Render3D.billboard(ps, vc, ctx, x, y - size * 0.5, z, size * 0.25f, color);
                org.joml.Vector3fc left = Render3D.left(ctx);
                Render3D.billboard(ps, vc, ctx, x + left.x() * size * 0.5, y + left.y() * size * 0.5, z + left.z() * size * 0.5, size * 0.25f, color);
                Render3D.billboard(ps, vc, ctx, x - left.x() * size * 0.5, y - left.y() * size * 0.5, z - left.z() * size * 0.5, size * 0.25f, color);
            }
        }
    }
}
