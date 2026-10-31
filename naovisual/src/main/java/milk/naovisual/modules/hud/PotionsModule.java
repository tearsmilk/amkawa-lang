package milk.naovisual.modules.hud;

import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.hud.Panels;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.theme.ThemeManager;
import milk.naovisual.core.util.TextUtil;
import net.minecraft.client.gui.Gui;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.renderer.RenderPipelines;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;

import java.util.ArrayList;
import java.util.List;

/** Активные эффекты списком: иконка, название, уровень и время. Заменяет ванильные иконки. */
public class PotionsModule extends HudModule {
    private final SelectSetting style = add(new SelectSetting("Стиль", "", "Список", "Список", "Компакт"));
    private final BooleanSetting background = add(new BooleanSetting("Фон", "", true));
    private final BooleanSetting showIcons = add(new BooleanSetting("Иконки", "", true));
    private final BooleanSetting hideAmbient = add(new BooleanSetting("Скрывать маяк", "Не показывать эффекты маяка", false));

    public PotionsModule() {
        super("Potions", "Эффекты", "Активные эффекты зелий своим списком вместо ванильных иконок", 0.985, 0.3);
    }

    @Override
    protected void renderHud(GuiGraphics g, float partial, boolean editor) {
        var p = mc().player;
        List<MobEffectInstance> effects = new ArrayList<>();
        if (p != null) for (MobEffectInstance e : p.getActiveEffects()) if (e.showIcon() && !(hideAmbient.on() && e.isAmbient())) effects.add(e);
        if (editor && effects.isEmpty()) { effects.add(new MobEffectInstance(MobEffects.SPEED, 1200, 1)); effects.add(new MobEffectInstance(MobEffects.STRENGTH, 300, 0)); }
        effects.sort((a, b) -> Integer.compare(b.getDuration(), a.getDuration()));
        boolean compact = style.is("Компакт");
        int rowH = compact ? 12 : 20, w = compact ? 90 : 120;
        int h = Math.max(rowH, effects.size() * rowH) + 4;
        setSize(w, h);
        if (effects.isEmpty()) return;
        if (background.on()) Panels.panel(g, 0, 0, w, h, 0.85f);
        var t = ThemeManager.current();
        int y = 2;
        for (MobEffectInstance e : effects) {
            String name = e.getEffect().value().getDisplayName().getString();
            if (e.getAmplifier() > 0) name += " " + TextUtil.roman(e.getAmplifier() + 1);
            String time = e.isInfiniteDuration() ? "∞" : TextUtil.seconds(e.getDuration());
            int x = 4;
            if (showIcons.on()) {
                var sprite = Gui.getMobEffectSprite(e.getEffect());
                int size = compact ? 9 : 16;
                g.blitSprite(RenderPipelines.GUI_TEXTURED, sprite, x, y + (rowH - size) / 2, size, size);
                x += size + 4;
            }
            int timeColor = e.getDuration() < 200 && !e.isInfiniteDuration() ? t.danger : t.textMuted;
            if (compact) {
                Render2D.text(g, Render2D.trim(name, w - x - Render2D.width(time) - 8), x, y + 2, t.text);
                Render2D.textRight(g, time, w - 4, y + 2, timeColor, false);
            } else {
                Render2D.text(g, Render2D.trim(name, w - x - 6), x, y + 2, t.text);
                Render2D.text(g, time, x, y + 11, timeColor);
                if (!e.isInfiniteDuration()) {
                    float frac = Math.min(1f, e.getDuration() / 1200f);
                    Render2D.bar(g, w - 34, y + 13, 30, 3, frac, 0x33000000, e.getEffect().value().getColor() | 0xFF000000);
                }
            }
            y += rowH;
        }
    }
}
