package milk.naovisual.core.hud;

import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.theme.Theme;
import milk.naovisual.core.theme.ThemeManager;
import milk.naovisual.core.util.ColorUtil;
import net.minecraft.client.gui.GuiGraphics;

/** Единый стиль плашек HUD: скруглённая панель темы с рамкой. */
public final class Panels {
    private Panels() {}

    public static void panel(GuiGraphics g, int x, int y, int w, int h, float alpha) {
        Theme t = ThemeManager.current();
        Render2D.roundedRect(g, x, y, w, h, 5, ColorUtil.withAlpha(t.panel, Math.round(255 * alpha)));
        Render2D.roundedOutline(g, x, y, w, h, 5, ColorUtil.withAlpha(t.border, Math.round(255 * alpha)));
    }

    public static void panel(GuiGraphics g, int x, int y, int w, int h, int color) {
        Render2D.roundedRect(g, x, y, w, h, 5, color);
    }

    public static int text() { return ThemeManager.current().text; }
    public static int muted() { return ThemeManager.current().textMuted; }
    public static int accent() { return ThemeManager.current().accent; }
}
