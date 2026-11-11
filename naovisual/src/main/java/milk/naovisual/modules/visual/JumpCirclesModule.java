package milk.naovisual.modules.visual;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.render.Render3D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.util.Anim;
import milk.naovisual.core.util.ColorUtil;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderContext;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

/** Расширяющиеся кольца на месте прыжка. */
public class JumpCirclesModule extends Module {
    private final NumberSetting radius = add(new NumberSetting("Радиус", "", 1.2, 0.3, 3.0, 0.1));
    private final NumberSetting duration = add(new NumberSetting("Длительность", "", 0.8, 0.2, 3.0, 0.1, " с"));
    private final NumberSetting thickness = add(new NumberSetting("Толщина", "", 0.12, 0.02, 0.5, 0.01));
    private final BooleanSetting others = add(new BooleanSetting("Другие игроки", "", true));
    private final BooleanSetting doubleRing = add(new BooleanSetting("Двойное кольцо", "", true));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xCCD97757));
    private final List<double[]> rings = new ArrayList<>(); // x, y, z, startMs

    public JumpCirclesModule() {
        super("JumpCircles", "Круги прыжка", "Расходящиеся кольца под ногами при прыжке", ModuleCategory.VISUALS);
        color.setMode(ColorSetting.Mode.THEME);
    }

    private final java.util.Map<Integer, Boolean> wasOnGround = new java.util.HashMap<>();
    private final java.util.Map<Integer, Long> lastSpawn = new java.util.HashMap<>();

    @Override
    public void onJump(LivingEntity e) {
        if (!(e instanceof Player)) return;
        if (e != mc().player && !others.on()) return;
        spawn(e);
    }

    /** Отрыв от земли вверх — тоже прыжок (ловит прыжок на месте и чужих игроков, у которых jumpFromGround не вызывается). */
    @Override
    public void onTick() {
        if (mc().level == null || mc().player == null) return;
        for (Player p : mc().level.players()) {
            if (p != mc().player && !others.on()) continue;
            boolean ground = p.onGround();
            Boolean was = wasOnGround.put(p.getId(), ground);
            if (Boolean.TRUE.equals(was) && !ground && p.getDeltaMovement().y > 0.08 && !p.isInWater() && !p.onClimbable()) spawn(p);
        }
        if (wasOnGround.size() > 256) wasOnGround.clear();
    }

    private void spawn(Entity e) {
        long now = System.currentTimeMillis();
        Long last = lastSpawn.get(e.getId());
        if (last != null && now - last < 250) return;
        lastSpawn.put(e.getId(), now);
        synchronized (rings) { rings.add(new double[]{e.getX(), Math.floor(e.getY() * 16) / 16 + 0.04, e.getZ(), now}); }
    }

    @Override
    public void onRenderWorld(WorldRenderContext ctx) {
        List<double[]> copy;
        long now = System.currentTimeMillis();
        double dur = duration.get() * 1000;
        synchronized (rings) {
            Iterator<double[]> it = rings.iterator();
            while (it.hasNext()) if (now - it.next()[3] > dur) it.remove();
            if (rings.isEmpty()) return;
            copy = new ArrayList<>(rings);
        }
        Render3D.begin(ctx);
        var quads = Render3D.quads(ctx);
        int c = color.color();
        for (double[] r : copy) {
            float t = Anim.easeOut((float) ((now - r[3]) / dur));
            double rad = radius.get() * t;
            int cc = ColorUtil.withAlpha(c, Math.round(ColorUtil.alpha(c) * (1f - t)));
            Render3D.filledRing(ctx.matrices(), quads, r[0], r[1], r[2], Math.max(0, rad - thickness.get()), rad, 40, ColorUtil.withAlpha(cc, 0), cc);
            if (doubleRing.on()) {
                double rad2 = rad * 0.6;
                Render3D.filledRing(ctx.matrices(), quads, r[0], r[1], r[2], Math.max(0, rad2 - thickness.get() * 0.5), rad2, 32, ColorUtil.withAlpha(cc, 0), ColorUtil.withAlpha(cc, ColorUtil.alpha(cc) / 2));
            }
        }
        Render3D.end(ctx);
    }

    @Override public void onDisconnect() { synchronized (rings) { rings.clear(); } wasOnGround.clear(); lastSpawn.clear(); }

}
