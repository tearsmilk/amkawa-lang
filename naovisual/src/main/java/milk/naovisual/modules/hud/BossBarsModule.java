package milk.naovisual.modules.hud;

import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.hud.Panels;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.theme.ThemeManager;
import milk.naovisual.mixin.BossHealthOverlayAccessor;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.LerpingBossEvent;
import net.minecraft.world.BossEvent;

import java.util.ArrayList;
import java.util.List;

/** Боссбары своим стилем вместо ванильных. */
public class BossBarsModule extends HudModule {
    private final BooleanSetting background = add(new BooleanSetting("Фон", "", true));
    private final BooleanSetting percent = add(new BooleanSetting("Проценты", "", true));
    private final BooleanSetting vanillaColors = add(new BooleanSetting("Цвета сервера", "Использовать цвет боссбара с сервера", true));
    private final ColorSetting color = add(new ColorSetting("Свой цвет", "", 0xFFD97757).visibleWhen(() -> !vanillaColors.on()));

    public BossBarsModule() {
        super("BossBars", "Боссбары", "Полосы здоровья боссов и серверные боссбары в своём стиле", 0.5 - 0.1, 0.02);
    }

    @Override
    protected void renderHud(GuiGraphics g, float partial, boolean editor) {
        List<LerpingBossEvent> events = new ArrayList<>();
        if (mc().gui != null) events.addAll(((BossHealthOverlayAccessor) mc().gui.getBossOverlay()).naovisual$events().values());
        int w = 182, rowH = 22;
        int h = Math.max(rowH, events.size() * rowH);
        setSize(w, h);
        var t = ThemeManager.current();
        if (events.isEmpty()) {
            if (editor) drawBar(g, 0, w, "Босс", 0.7f, t.accent);
            return;
        }
        int y = 0;
        for (LerpingBossEvent e : events) {
            int c = vanillaColors.on() ? barColor(e.getColor(), t.accent) : color.color();
            drawBar(g, y, w, e.getName().getString(), e.getProgress(), c);
            y += rowH;
        }
    }

    private void drawBar(GuiGraphics g, int y, int w, String name, float progress, int c) {
        var t = ThemeManager.current();
        if (background.on()) Panels.panel(g, 0, y, w, 20, 0.85f);
        Render2D.textCentered(g, Render2D.trim(name, w - 10), w / 2, y + 3, t.text, false);
        Render2D.bar(g, 5, y + 13, w - 10, 4, progress, 0x33000000, c);
        if (percent.on()) Render2D.textScaled(g, Math.round(progress * 100) + "%", w - 5 - Render2D.width(Math.round(progress * 100) + "%") * 0.7f, y + 4, 0.7f, t.textMuted, false);
    }

    private static int barColor(BossEvent.BossBarColor c, int fallback) {
        return switch (c) {
            case PINK -> 0xFFE88AA8; case BLUE -> 0xFF4FB3D9; case RED -> 0xFFE05A4F; case GREEN -> 0xFF5FB36A;
            case YELLOW -> 0xFFE8B84A; case PURPLE -> 0xFF9A7ED8; case WHITE -> 0xFFF1EFEA; default -> fallback;
        };
    }
}
