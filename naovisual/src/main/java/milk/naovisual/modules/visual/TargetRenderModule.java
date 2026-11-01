package milk.naovisual.modules.visual;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.render.Render3D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.util.Anim;
import milk.naovisual.core.util.ColorUtil;
import milk.naovisual.core.util.Targets;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderContext;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Подсветка цели в мире: рамка, кольца, спираль «призраков», столб. */
public class TargetRenderModule extends Module {
    private final SelectSetting style = add(new SelectSetting("Стиль", "", "Кольца", "Кольца", "Рамка", "Призраки", "Столб", "Капля"));
    private final NumberSetting speed = add(new NumberSetting("Скорость", "", 1.0, 0.2, 3.0, 0.1));
    private final BooleanSetting hurtColor = add(new BooleanSetting("Цвет по урону", "Краснеть, когда цель получает урон", true));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xCCD97757));
    private final ColorSetting color2 = add(new ColorSetting("Второй цвет", "", 0x66E8B84A));
    private final Anim appear = new Anim(0f, 10f);
    private LivingEntity last;

    public TargetRenderModule() {
        super("TargetRender", "Подсветка цели", "Эффект вокруг атакуемой цели: кольца, рамка, призраки или столб", ModuleCategory.VISUALS);
        color.setMode(ColorSetting.Mode.THEME);
    }

    @Override public boolean defaultEnabled() { return true; }

    @Override
    public void onRenderWorld(WorldRenderContext ctx) {
        LivingEntity t = Targets.current();
        if (t != null) last = t;
        appear.to(t != null ? 1f : 0f);
        float a = appear.get();
        if (last == null || a < 0.02f || !last.isAlive()) { if (t == null) last = null; return; }
        float partial = Render3D.partial();
        Vec3 pos = Render3D.lerpPos(last, partial);
        AABB box = Render3D.lerpBox(last, partial);
        int c = ColorUtil.withAlpha(color.color(), Math.round(ColorUtil.alpha(color.color()) * a));
        int c2 = ColorUtil.withAlpha(color2.color(), Math.round(ColorUtil.alpha(color2.color()) * a));
        if (hurtColor.on() && last.hurtTime > 0) c = ColorUtil.lerp(c, ColorUtil.withAlpha(0xFFE05A4F, ColorUtil.alpha(c)), last.hurtTime / 10f);
        double time = System.currentTimeMillis() / 1000.0 * speed.get();
        Render3D.begin(ctx);
        PoseStack ps = ctx.matrices();
        VertexConsumer quads = Render3D.quads(ctx), lines = Render3D.lines(ctx);
        double h = last.getBbHeight(), w = last.getBbWidth();
        switch (style.get()) {
            case "Рамка" -> {
                AABB b = box.inflate(0.03 + Math.sin(time * 3) * 0.02);
                Render3D.lineBox(ps, lines, b, ColorUtil.withAlpha(c, 255));
                Render3D.gradientBox(ps, quads, b, ColorUtil.withAlpha(c, ColorUtil.alpha(c) / 4), ColorUtil.withAlpha(c2, 0));
            }
            case "Призраки" -> {
                for (int i = 0; i < 3; i++) {
                    double ang = time * 2 + i * Math.PI * 2 / 3;
                    double rr = w * 0.9;
                    double y = pos.y + h * 0.5 + Math.sin(time * 3 + i) * h * 0.4;
                    Render3D.billboard(ps, quads, ctx, pos.x + Math.cos(ang) * rr, y, pos.z + Math.sin(ang) * rr, 0.22f, c);
                    for (int k = 1; k <= 6; k++) {
                        double ang2 = ang - k * 0.12, y2 = pos.y + h * 0.5 + Math.sin(time * 3 + i - k * 0.12 * 1.5) * h * 0.4;
                        Render3D.billboard(ps, quads, ctx, pos.x + Math.cos(ang2) * rr, y2, pos.z + Math.sin(ang2) * rr, 0.22f * (1f - k / 7f), ColorUtil.withAlpha(c, Math.round(ColorUtil.alpha(c) * (1f - k / 7f))));
                    }
                }
            }
            case "Столб" -> {
                AABB b = new AABB(pos.x - w / 2, pos.y, pos.z - w / 2, pos.x + w / 2, pos.y + h * 1.6, pos.z + w / 2);
                Render3D.gradientBox(ps, quads, b, c, ColorUtil.withAlpha(c2, 0));
            }
            case "Капля" -> {
                double y = pos.y + h + 0.35 + Math.sin(time * 4) * 0.08;
                Render3D.billboard(ps, quads, ctx, pos.x, y, pos.z, 0.3f, c);
                Render3D.billboard(ps, quads, ctx, pos.x, y - 0.2, pos.z, 0.15f, c);
                Render3D.filledRing(ps, quads, pos.x, pos.y + 0.02, pos.z, w * 0.6, w * 0.8, 32, ColorUtil.withAlpha(c2, 0), c2);
            }
            default -> {
                double y1 = pos.y + (h * 0.5) * (1 + Math.sin(time * 2.5)) ;
                Render3D.filledRing(ps, quads, pos.x, y1, pos.z, w * 0.7, w * 0.9, 40, ColorUtil.withAlpha(c, 0), c);
                Render3D.filledRing(ps, quads, pos.x, pos.y + 0.02, pos.z, w * 0.55, w * 0.95, 40, c2, ColorUtil.withAlpha(c2, 0));
                for (int i = 0; i < 2; i++) {
                    double ang = time * 3 + i * Math.PI;
                    Render3D.billboard(ps, quads, ctx, pos.x + Math.cos(ang) * w * 0.9, y1, pos.z + Math.sin(ang) * w * 0.9, 0.12f, ColorUtil.withAlpha(c, 255));
                }
            }
        }
        Render3D.end(ctx);
    }
}
