package milk.naovisual.core;

import milk.naovisual.core.theme.Theme;
import milk.naovisual.core.util.ColorUtil;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/** Контраст текста к панелям темы по умолчанию (WCAG 2.x) при 75 % непрозрачности поверх серого мира. */
class ThemeContrastTest {
    private static double channel(int v) {
        double c = v / 255.0;
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    }

    private static double luminance(int rgb) {
        return 0.2126 * channel(ColorUtil.red(rgb)) + 0.7152 * channel(ColorUtil.green(rgb)) + 0.0722 * channel(ColorUtil.blue(rgb));
    }

    /** Полупрозрачный цвет поверх фона. */
    private static int over(int top, int bottom) {
        double a = ColorUtil.alpha(top) / 255.0;
        int r = (int) Math.round(ColorUtil.red(top) * a + ColorUtil.red(bottom) * (1 - a));
        int g = (int) Math.round(ColorUtil.green(top) * a + ColorUtil.green(bottom) * (1 - a));
        int b = (int) Math.round(ColorUtil.blue(top) * a + ColorUtil.blue(bottom) * (1 - a));
        return ColorUtil.rgb(r, g, b);
    }

    static double ratio(int text, int bg) {
        double l1 = luminance(text), l2 = luminance(bg);
        double hi = Math.max(l1, l2), lo = Math.min(l1, l2);
        return (hi + 0.05) / (lo + 0.05);
    }

    @Test
    void defaultThemeIsBlack75() {
        Theme t = Theme.byName("нет такой");
        assertSame(Theme.BLACK, t);
        Theme o = Theme.BLACK.withOpacity(0.75f);
        assertEquals(191, ColorUtil.alpha(o.background));
        assertEquals(0xFFF2E8DF, o.text);          // текст не бледнеет
    }

    @Test
    void textReadableOnPanelsOverWorld() {
        Theme t = Theme.BLACK.withOpacity(0.75f);
        int[] worlds = {0xFF808080, 0xFFFFFFFF, 0xFFC8E0FF};   // серый, белый, небо
        for (int world : worlds) {
            int panel = over(t.panel, over(t.background, world));
            int alt = over(t.panelAlt, over(t.background, world));
            assertTrue(ratio(t.text, panel) >= 4.5, "text/panel " + ratio(t.text, panel));
            assertTrue(ratio(t.textMuted, panel) >= 4.5, "muted/panel " + ratio(t.textMuted, panel));
            assertTrue(ratio(t.text, alt) >= 4.5, "text/sidebar " + ratio(t.text, alt));
            assertTrue(ratio(0xFFFFFFFF, ColorUtil.withAlpha(t.accent, 255)) >= 3.0, "white on accent");
        }
    }

    @Test
    void opacityScalesOnlyPanels() {
        Theme t = Theme.CLAUDE.withOpacity(0.5f);
        assertEquals(Math.round(0xF2 * 0.5f), ColorUtil.alpha(t.background));
        assertEquals(ColorUtil.alpha(Theme.CLAUDE.text), ColorUtil.alpha(t.text));
        assertEquals(Theme.CLAUDE.accent, t.accent);
        assertEquals(6, Theme.ALL.size());
    }
}
