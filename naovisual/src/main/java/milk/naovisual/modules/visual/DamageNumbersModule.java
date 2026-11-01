package milk.naovisual.modules.visual;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.render.Projection;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.util.Anim;
import milk.naovisual.core.util.ColorUtil;
import milk.naovisual.core.util.Crits;
import milk.naovisual.core.util.DamageColors;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.Vec3;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

/** Всплывающие числа урона и лечения над сущностями. */
public class DamageNumbersModule extends Module {
    private final NumberSetting duration = add(new NumberSetting("Длительность", "", 1.2, 0.4, 3.0, 0.1, " с"));
    private final NumberSetting size = add(new NumberSetting("Размер", "", 1.0, 0.5, 2.5, 0.1));
    private final BooleanSetting healing = add(new BooleanSetting("Показывать лечение", "Зелёные числа при восстановлении здоровья", true));
    private final BooleanSetting self = add(new BooleanSetting("На себе", "Числа урона по своему игроку", false));

    private record Num(double x, double y, double z, double dx, double dz, String text, int color, boolean crit, long start) {}

    private final List<Num> nums = new ArrayList<>();
    private final Map<Integer, Float> health = new HashMap<>();

    public DamageNumbersModule() {
        super("DamageNumbers", "Числа урона", "Всплывающий урон: золото — обычный, красный — крит, зелёный — лечение", ModuleCategory.VISUALS);
    }

    @Override
    public void onTick() {
        if (mc().level == null || mc().player == null) return;
        Map<Integer, Float> seen = new HashMap<>();
        for (Entity e : mc().level.entitiesForRendering()) {
            if (!(e instanceof LivingEntity le) || e.distanceToSqr(mc().player) > 48 * 48) continue;
            if (e == mc().player && !self.on()) continue;
            float h = le.getHealth();
            seen.put(e.getId(), h);
            Float prev = health.get(e.getId());
            if (prev == null) continue;
            float delta = h - prev;
            if (Math.abs(delta) < 0.05f || (delta > 0 && !healing.on())) continue;
            if (delta < 0 && le.isDeadOrDying() && h <= 0 && prev <= 0) continue;
            boolean crit = delta < 0 && Crits.recent(e.getId());
            var rnd = mc().level.random;
            synchronized (nums) {
                nums.add(new Num(e.getX() + (rnd.nextDouble() - 0.5) * 0.5, e.getY() + e.getBbHeight() * 0.8, e.getZ() + (rnd.nextDouble() - 0.5) * 0.5,
                        (rnd.nextDouble() - 0.5) * 0.4, (rnd.nextDouble() - 0.5) * 0.4,
                        DamageColors.format(delta), DamageColors.colorFor(delta, crit), crit, System.currentTimeMillis()));
                if (nums.size() > 80) nums.remove(0);
            }
        }
        health.clear();
        health.putAll(seen);
    }

    @Override
    public void onRenderOverlay(GuiGraphics g, DeltaTracker delta) {
        List<Num> copy;
        long now = System.currentTimeMillis();
        double dur = duration.get() * 1000;
        synchronized (nums) {
            Iterator<Num> it = nums.iterator();
            while (it.hasNext()) if (now - it.next().start() > dur) it.remove();
            if (nums.isEmpty()) return;
            copy = new ArrayList<>(nums);
        }
        Vec3 cam = mc().gameRenderer.getMainCamera().position();
        for (Num n : copy) {
            float t = (float) ((now - n.start()) / dur);
            float rise = Anim.easeOut(t);
            Vec3 p = new Vec3(n.x() + n.dx() * rise, n.y() + 0.9 * rise, n.z() + n.dz() * rise);
            float[] s = Projection.toScreen(p);
            if (s == null) continue;
            double dist = Math.max(1, p.distanceTo(cam));
            float pop = n.crit() ? 1f + 0.5f * (1f - Anim.easeOut(Math.min(1f, t * 4f))) : 1f;
            float sc = (float) Math.max(0.6, Math.min(2.2, 7.0 / dist)) * size.get().floatValue() * (n.crit() ? 1.35f : 1f) * pop;
            float alpha = t < 0.6f ? 1f : 1f - (t - 0.6f) / 0.4f;
            int c = ColorUtil.withAlpha(n.color(), Math.max(8, Math.round(255 * alpha)));
            String text = n.crit() ? n.text() + "!" : n.text();
            float w = Render2D.width(text) * sc;
            Render2D.textScaled(g, text, s[0] - w / 2f, s[1] - 4 * sc, sc, c, true);
        }
    }

    @Override public void onDisconnect() { synchronized (nums) { nums.clear(); } health.clear(); }
}
