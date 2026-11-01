package milk.naovisual.modules.visual;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.particle.ParticleSystem;
import milk.naovisual.core.render.Render3D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.util.Anim;
import milk.naovisual.core.util.ColorUtil;
import milk.naovisual.core.util.Crits;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderContext;
import net.minecraft.world.entity.Entity;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Random;

/** Эффект критического удара: вспышка частиц и красный импульс-кольцо вокруг цели. */
public class CritEffectModule extends Module {
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xFFFF5A4F));
    private final NumberSetting intensity = add(new NumberSetting("Интенсивность", "Количество частиц", 1.0, 0.3, 3.0, 0.1));
    private final BooleanSetting ring = add(new BooleanSetting("Импульс", "Расходящееся кольцо вокруг цели", true));
    private final List<double[]> pulses = new ArrayList<>(); // x, y, z, radius, start

    public CritEffectModule() {
        super("CritEffect", "Эффект крита", "Вспышка и импульс при критическом ударе — отличается от обычного", ModuleCategory.VISUALS);
    }

    @Override
    public void onAttack(Entity e) {
        if (!Crits.recent(e.getId())) return;
        Random rnd = ParticleSystem.random();
        int c = color.color();
        double cx = e.getX(), cy = e.getY() + e.getBbHeight() * 0.6, cz = e.getZ();
        int count = (int) Math.round(18 * intensity.get());
        for (int i = 0; i < count; i++) {
            double a = rnd.nextDouble() * Math.PI * 2, up = rnd.nextDouble() * 0.25 + 0.05, sp = 0.15 + rnd.nextDouble() * 0.2;
            int pc = i % 3 == 0 ? 0xFFFFE3B0 : c;
            var p = ParticleSystem.spawn(cx, cy, cz, Math.cos(a) * sp, up, Math.sin(a) * sp, 0.12f + rnd.nextFloat() * 0.08f, pc, 14 + rnd.nextInt(10), ParticleSystem.Shape.STAR);
            p.gravity = 0.03f;
        }
        if (ring.on()) synchronized (pulses) { pulses.add(new double[]{cx, cy, cz, Math.max(0.6, e.getBbWidth()), System.currentTimeMillis()}); }
    }

    @Override
    public void onRenderWorld(WorldRenderContext ctx) {
        List<double[]> copy;
        long now = System.currentTimeMillis();
        synchronized (pulses) {
            Iterator<double[]> it = pulses.iterator();
            while (it.hasNext()) if (now - it.next()[4] > 400) it.remove();
            if (pulses.isEmpty()) return;
            copy = new ArrayList<>(pulses);
        }
        Render3D.begin(ctx);
        var quads = Render3D.quads(ctx);
        int c = color.color();
        for (double[] p : copy) {
            float t = Anim.easeOut((float) ((now - p[4]) / 400.0));
            double r = p[3] * (0.5 + 1.2 * t);
            int cc = ColorUtil.withAlpha(c, Math.round(220 * (1f - t)));
            Render3D.filledRing(ctx.matrices(), quads, p[0], p[1], p[2], Math.max(0, r - 0.12), r, 40, ColorUtil.withAlpha(cc, 0), cc);
            Render3D.filledRing(ctx.matrices(), quads, p[0], p[1], p[2], r, r + 0.04, 40, cc, ColorUtil.withAlpha(cc, 0));
        }
        Render3D.end(ctx);
    }

    @Override public void onDisconnect() { synchronized (pulses) { pulses.clear(); } }
}
