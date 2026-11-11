package milk.naovisual.modules.visual;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.util.ColorUtil;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.gui.GuiGraphics;

/** Эффект на руках: свечение по нижним углам экрана, усиливается при взмахе и ударе. */
public class HandsGlowModule extends Module {
    private final SelectSetting style = add(new SelectSetting("Стиль", "", "Свечение", "Свечение", "Полосы", "Пульс"));
    private final NumberSetting strength = add(new NumberSetting("Сила", "", 0.5, 0.1, 1.0, 0.05));
    private final NumberSetting size = add(new NumberSetting("Размер", "Доля ширины экрана", 0.25, 0.1, 0.5, 0.01));
    private final BooleanSetting swing = add(new BooleanSetting("Реакция на взмах", "", true));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xFFD97757));

    public HandsGlowModule() {
        super("HandsShader", "Эффект рук", "Свечение у рук в нижних углах экрана, реагирует на взмах", ModuleCategory.VISUALS);
        color.setMode(ColorSetting.Mode.THEME);
    }

    @Override
    public void onRenderOverlay(GuiGraphics g, DeltaTracker delta) {
        var p = mc().player;
        if (p == null || mc().options.hideGui || !mc().options.getCameraType().isFirstPerson()) return;
        float partial = delta.getGameTimeDeltaPartialTick(false);
        float sw = swing.on() ? p.getAttackAnim(partial) : 0f;
        float pulse = style.is("Пульс") ? 0.5f + 0.5f * (float) Math.sin(System.currentTimeMillis() / 350.0) : 1f;
        float s = strength.getFloat() * (0.6f + 0.4f * pulse) * (1f + sw * 0.8f);
        int w = g.guiWidth(), h = g.guiHeight();
        int gw = Math.round(w * size.getFloat()), gh = Math.round(h * 0.45f * (1f + sw * 0.3f));
        int c = color.color();
        boolean right = p.getMainArm() == net.minecraft.world.entity.HumanoidArm.RIGHT;
        if (style.is("Полосы")) {
            for (int i = 0; i < 6; i++) {
                int a = Math.round(90 * s * (1f - i / 6f));
                int bx = right ? w - gw + i * (gw / 6) : gw - (i + 1) * (gw / 6);
                g.fill(bx, h - gh, bx + gw / 12, h, ColorUtil.withAlpha(c, a));
            }
            return;
        }
        int steps = 10;
        for (int i = 0; i < steps; i++) {
            float f = i / (float) steps;
            int a = Math.round(70 * s * (1f - f) * (1f - f));
            int cw = Math.round(gw * (1f - f * 0.5f)), ch = Math.round(gh * (1f - f * 0.5f));
            int x = right ? w - cw : 0;
            g.fillGradient(x, h - ch, x + cw, h, ColorUtil.withAlpha(c, 0), ColorUtil.withAlpha(c, a));
        }
        // слабое свечение второй руки
        int cw = gw / 2, ch = gh / 2;
        int x = right ? 0 : w - cw;
        g.fillGradient(x, h - ch, x + cw, h, ColorUtil.withAlpha(c, 0), ColorUtil.withAlpha(c, Math.round(35 * s)));
    }
}
