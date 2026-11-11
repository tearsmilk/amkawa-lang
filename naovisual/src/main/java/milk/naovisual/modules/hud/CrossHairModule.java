package milk.naovisual.modules.hud;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.*;
import milk.naovisual.core.util.Anim;
import milk.naovisual.core.util.ColorUtil;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.world.entity.LivingEntity;

/** Свой прицел: крест, точка, кольцо; динамика при движении, индикатор удара, градиент. */
public class CrossHairModule extends Module {
    private final SelectSetting style = add(new SelectSetting("Стиль", "", "Крест", "Крест", "Точка", "Кольцо", "Крест + точка"));
    private final NumberSetting size = add(new NumberSetting("Размер", "", 5, 1, 15, 1));
    private final NumberSetting gap = add(new NumberSetting("Зазор", "Расстояние от центра", 2, 0, 10, 1));
    private final NumberSetting thickness = add(new NumberSetting("Толщина", "", 1, 1, 4, 1));
    private final BooleanSetting dynamic = add(new BooleanSetting("Динамика", "Расширяется при движении и прыжках", true));
    private final BooleanSetting outline = add(new BooleanSetting("Обводка", "", true));
    private final BooleanSetting hitMarker = add(new BooleanSetting("Индикатор удара", "Крестик при попадании", true));
    private final BooleanSetting cooldownRing = add(new BooleanSetting("Кольцо перезарядки", "Кольцо заряда атаки", false));
    private final BooleanSetting gradient = add(new BooleanSetting("Градиент", "", false));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xFFFFFFFF));
    private final ColorSetting color2 = add(new ColorSetting("Второй цвет", "", 0xFFD97757).visibleWhen(gradient::on));
    private final ColorSetting hitColor = add(new ColorSetting("Цвет при цели", "Когда прицел на существе", 0xFFE05A4F));
    private final Anim spread = new Anim(0f, 10f);
    private long lastHit;

    public CrossHairModule() {
        super("CrossHair", "Прицел", "Собственный прицел вместо ванильного: стили, динамика, индикатор удара", ModuleCategory.HUD);
    }

    @Override public void onAttack(net.minecraft.world.entity.Entity e) { lastHit = System.currentTimeMillis(); }

    @Override
    public void onRenderOverlay(GuiGraphics g, DeltaTracker delta) {
        var p = mc().player;
        if (p == null || mc().options.hideGui || mc().screen != null) return;
        if (mc().options.getCameraType() != net.minecraft.client.CameraType.FIRST_PERSON) return;
        int cx = g.guiWidth() / 2, cy = g.guiHeight() / 2;
        float moving = (float) Math.hypot(p.getX() - p.xo, p.getZ() - p.zo) * 20f;
        float target = dynamic.on() ? Math.min(6f, moving * 0.8f + (p.onGround() ? 0 : 3f) + (p.isSprinting() ? 1.5f : 0)) : 0f;
        spread.to(target);
        float s = spread.get();
        boolean onTarget = mc().crosshairPickEntity instanceof LivingEntity;
        int c = onTarget ? hitColor.color() : color.color();
        int c2 = gradient.on() ? color2.color() : c;
        int sz = size.getInt(), gp = gap.getInt() + Math.round(s), th = thickness.getInt();
        switch (style.get()) {
            case "Точка" -> dot(g, cx, cy, Math.max(1, th), c);
            case "Кольцо" -> Render2D.ring(g, cx + 0.5f, cy + 0.5f, sz + gp, th, 1f, c);
            case "Крест + точка" -> { cross(g, cx, cy, sz, gp, th, c, c2); dot(g, cx, cy, th, c2); }
            default -> cross(g, cx, cy, sz, gp, th, c, c2);
        }
        if (cooldownRing.on()) {
            float f = p.getAttackStrengthScale(0f);
            if (f < 1f) Render2D.ring(g, cx + 0.5f, cy + 0.5f, sz + gp + 4, 1f, f, ColorUtil.withAlpha(c, 160));
        }
        if (hitMarker.on()) {
            long since = System.currentTimeMillis() - lastHit;
            if (since < 350) {
                float f = 1f - since / 350f;
                int hc = ColorUtil.withAlpha(hitColor.color(), Math.round(255 * f));
                int d = sz + gp + 3 + Math.round((1 - f) * 3);
                for (int i = 0; i < 3; i++) {
                    g.fill(cx - d - i, cy - d - i, cx - d - i + 1, cy - d - i + 1, hc);
                    g.fill(cx + d + i, cy - d - i, cx + d + i + 1, cy - d - i + 1, hc);
                    g.fill(cx - d - i, cy + d + i, cx - d - i + 1, cy + d + i + 1, hc);
                    g.fill(cx + d + i, cy + d + i, cx + d + i + 1, cy + d + i + 1, hc);
                }
            }
        }
    }

    private void dot(GuiGraphics g, int cx, int cy, int r, int c) {
        if (outline.on()) g.fill(cx - r - 1 + 1 - 1, cy - r, cx + r + 1, cy + r + 1, 0x80000000);
        g.fill(cx - r + 1, cy - r + 1, cx + r, cy + r, c);
    }

    private void cross(GuiGraphics g, int cx, int cy, int sz, int gp, int th, int c, int c2) {
        int half = th / 2;
        if (outline.on()) {
            int o = 0x90000000;
            g.fill(cx - half - 1, cy - gp - sz - 1, cx + th - half + 1, cy - gp + 1, o);
            g.fill(cx - half - 1, cy + gp, cx + th - half + 1, cy + gp + sz + 2, o);
            g.fill(cx - gp - sz - 1, cy - half - 1, cx - gp + 1, cy + th - half + 1, o);
            g.fill(cx + gp, cy - half - 1, cx + gp + sz + 2, cy + th - half + 1, o);
        }
        // вертикаль: градиент сверху вниз, горизонталь: слева направо
        g.fillGradient(cx - half, cy - gp - sz, cx + th - half, cy - gp, c, c2);
        g.fillGradient(cx - half, cy + gp + 1, cx + th - half, cy + gp + sz + 1, c2, c);
        Render2D.gradientH(g, cx - gp - sz, cy - half, sz, th, c, c2);
        Render2D.gradientH(g, cx + gp + 1, cy - half, sz, th, c2, c);
    }
}
