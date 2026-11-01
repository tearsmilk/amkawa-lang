package milk.naovisual.modules.world;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.render.Projection;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.render.Render3D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.setting.TextSetting;
import milk.naovisual.core.theme.ThemeManager;
import milk.naovisual.core.util.ColorUtil;
import milk.naovisual.core.util.TextUtil;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderContext;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Точка назначения: столб в мире, метка с дистанцией на экране и стрелка у края, если точка вне обзора. */
public class GpsModule extends Module {
    private final TextSetting label = add(new TextSetting("Название", "", "База", 24));
    private final NumberSetting x = add(new NumberSetting("X", "", 0, -30_000_000, 30_000_000, 1));
    private final NumberSetting y = add(new NumberSetting("Y", "", 64, -64, 320, 1));
    private final NumberSetting z = add(new NumberSetting("Z", "", 0, -30_000_000, 30_000_000, 1));
    private final BooleanSetting beam = add(new BooleanSetting("Столб", "Светящийся столб в мире", true));
    private final BooleanSetting arrow = add(new BooleanSetting("Стрелка", "Указатель у края экрана, когда точка не видна", true));
    private final BooleanSetting setHere = add(new BooleanSetting("Поставить здесь", "Включите, чтобы записать текущие координаты", false));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xAAD97757));

    public GpsModule() {
        super("Gps", "Навигатор", "Метка на координатах с дистанцией, столбом и стрелкой-указателем", ModuleCategory.WORLD);
        color.setMode(ColorSetting.Mode.THEME);
    }

    @Override
    public void onTick() {
        if (setHere.on() && mc().player != null) {
            x.set(Math.floor(mc().player.getX()));
            y.set(Math.floor(mc().player.getY()));
            z.set(Math.floor(mc().player.getZ()));
            setHere.set(false);
            milk.naovisual.core.config.ConfigManager.markDirty();
        }
    }

    public Vec3 point() { return new Vec3(x.get() + 0.5, y.get(), z.get() + 0.5); }

    @Override
    public void onRenderWorld(WorldRenderContext ctx) {
        if (!beam.on()) return;
        Vec3 p = point();
        Render3D.begin(ctx);
        int c = color.color();
        Render3D.gradientBox(ctx.matrices(), Render3D.quads(ctx), new AABB(p.x - 0.3, p.y, p.z - 0.3, p.x + 0.3, p.y + 60, p.z + 0.3), c, ColorUtil.withAlpha(c, 0));
        Render3D.lineBox(ctx.matrices(), Render3D.lines(ctx), new AABB(p.x - 0.5, p.y, p.z - 0.5, p.x + 0.5, p.y + 1, p.z + 0.5), ColorUtil.withAlpha(c, 255));
        Render3D.end(ctx);
    }

    @Override
    public void onRenderOverlay(GuiGraphics g, DeltaTracker delta) {
        var pl = mc().player;
        if (pl == null || mc().options.hideGui) return;
        Vec3 p = point();
        double dist = pl.position().distanceTo(p);
        String text = label.get() + "  " + (dist >= 1000 ? TextUtil.fixed(dist / 1000, 1) + " км" : Math.round(dist) + " м");
        var t = ThemeManager.current();
        float[] s = Projection.toScreen(p.add(0, 1.5, 0));
        int w = g.guiWidth(), h = g.guiHeight();
        if (s != null && s[0] >= 0 && s[0] <= w && s[1] >= 0 && s[1] <= h) {
            int tw = Render2D.width(text) + 8;
            int tx = Math.round(s[0]) - tw / 2, ty = Math.round(s[1]) - 14;
            Render2D.roundedRect(g, tx, ty, tw, 12, 4, ColorUtil.withAlpha(t.panel, 220));
            Render2D.rect(g, tx, ty + 3, 2, 6, color.color() | 0xFF000000);
            Render2D.text(g, text, tx + 5, ty + 2, t.text);
            return;
        }
        if (!arrow.on()) return;
        // стрелка по направлению к точке относительно взгляда
        double dx = p.x - pl.getX(), dz = p.z - pl.getZ();
        double angleTo = Math.toDegrees(Math.atan2(dz, dx)) - 90;
        double rel = Math.toRadians(((angleTo - pl.getYRot()) % 360 + 540) % 360 - 180);
        int cx = w / 2, cy = h / 2, r = Math.min(w, h) / 2 - 24;
        int ax = cx + (int) (Math.sin(rel) * r), ay = cy - (int) (Math.cos(rel) * r * 0.75);
        int c = color.color() | 0xFF000000;
        for (int i = 0; i < 6; i++) {
            int px = ax - (int) (Math.sin(rel) * i * 2), py = ay + (int) (Math.cos(rel) * i * 2);
            Render2D.rect(g, px - i / 2, py - i / 2, i + 1, i + 1, c);
        }
        Render2D.textCentered(g, text, ax, ay + 12, t.text, true);
    }
}
