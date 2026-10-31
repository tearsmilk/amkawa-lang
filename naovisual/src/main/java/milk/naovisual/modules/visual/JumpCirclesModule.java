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

    @Override
    public void onJump(LivingEntity e) {
        if (!(e instanceof Player)) return;
        if (e != mc().player && !others.on()) return;
        synchronized (rings) { rings.add(new double[]{e.getX(), e.getY() + 0.02, e.getZ(), System.currentTimeMillis()}); }
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

    @Override public void onDisconnect() { synchronized (rings) { rings.clear(); } }

}
