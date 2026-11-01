package milk.naovisual.modules.other;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.render.Render3D;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.util.ColorUtil;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderContext;
import net.minecraft.world.phys.Vec3;

/** Талисман: светящиеся фигурки, кружащие вокруг игрока. */
public class TrinketModule extends Module {
    private final SelectSetting shape = add(new SelectSetting("Форма", "", "Орбиты", "Орбиты", "Спутник", "Ореол", "Хвост"));
    private final NumberSetting count = add(new NumberSetting("Количество", "", 3, 1, 8, 1));
    private final NumberSetting radius = add(new NumberSetting("Радиус", "", 0.9, 0.3, 2.0, 0.05));
    private final NumberSetting size = add(new NumberSetting("Размер", "", 0.12, 0.04, 0.4, 0.01));
    private final NumberSetting speed = add(new NumberSetting("Скорость", "", 1.0, 0.1, 3.0, 0.1));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xFFD97757));
    private final Vec3[] history = new Vec3[24];
    private int head;

    public TrinketModule() {
        super("Trinket", "Талисман", "Светящиеся фигурки, кружащие вокруг игрока", ModuleCategory.OTHER);
        color.setMode(ColorSetting.Mode.THEME);
    }

    @Override
    public void onTick() {
        var p = mc().player;
        if (p == null) return;
        history[head] = p.position().add(0, p.getBbHeight() * 0.6, 0);
        head = (head + 1) % history.length;
    }

    @Override
    public void onRenderWorld(WorldRenderContext ctx) {
        var p = mc().player;
        if (p == null || mc().options.getCameraType().isFirstPerson() && !shape.is("Хвост")) return;
        float partial = Render3D.partial();
        Vec3 pos = Render3D.lerpPos(p, partial);
        double time = System.currentTimeMillis() / 1000.0 * speed.get();
        int c = color.color();
        float sz = size.getFloat();
        Render3D.begin(ctx);
        var quads = Render3D.quads(ctx);
        var ps = ctx.matrices();
        switch (shape.get()) {
            case "Спутник" -> {
                double a = time * 2;
                double x = pos.x + Math.cos(a) * radius.get(), z = pos.z + Math.sin(a) * radius.get(), y = pos.y + 1.2 + Math.sin(time * 3) * 0.2;
                Render3D.billboard(ps, quads, ctx, x, y, z, sz * 1.5f, c);
                for (int k = 1; k <= 8; k++) {
                    double a2 = a - k * 0.15;
                    Render3D.billboard(ps, quads, ctx, pos.x + Math.cos(a2) * radius.get(), pos.y + 1.2 + Math.sin(time * 3 - k * 0.15 * 1.5) * 0.2, pos.z + Math.sin(a2) * radius.get(), sz * (1f - k / 9f), ColorUtil.withAlpha(c, Math.round(255 * (1f - k / 9f))));
                }
            }
            case "Ореол" -> Render3D.filledRing(ps, quads, pos.x, pos.y + p.getBbHeight() + 0.15 + Math.sin(time * 2) * 0.04, pos.z, 0.28, 0.4, 32, c, ColorUtil.withAlpha(c, 60));
            case "Хвост" -> {
                for (int i = 0; i < history.length; i++) {
                    Vec3 h = history[(head + i) % history.length];
                    if (h == null) continue;
                    float f = i / (float) history.length;
                    Render3D.billboard(ps, quads, ctx, h.x, h.y + Math.sin(time * 4 + i * 0.4) * 0.1, h.z, sz * f, ColorUtil.withAlpha(c, Math.round(200 * f)));
                }
            }
            default -> {
                int n = count.getInt();
                for (int i = 0; i < n; i++) {
                    double a = time * 1.5 + i * Math.PI * 2 / n;
                    double y = pos.y + p.getBbHeight() * 0.5 + Math.sin(time * 2 + i) * 0.3;
                    Render3D.billboard(ps, quads, ctx, pos.x + Math.cos(a) * radius.get(), y, pos.z + Math.sin(a) * radius.get(), sz, c);
                }
            }
        }
        Render3D.end(ctx);
    }
}
