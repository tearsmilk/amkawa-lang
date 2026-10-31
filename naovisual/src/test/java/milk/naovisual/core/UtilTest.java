package milk.naovisual.core;

import milk.naovisual.core.config.ConfigManager;
import milk.naovisual.core.theme.Theme;
import milk.naovisual.core.util.Anim;
import milk.naovisual.core.util.ColorUtil;
import milk.naovisual.core.util.KeyNames;
import milk.naovisual.core.util.TextUtil;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class UtilTest {
    @Test
    void colorChannels() {
        int c = ColorUtil.argb(0x80, 0xD9, 0x77, 0x57);
        assertEquals(0x80D97757, c);
        assertEquals(0x80, ColorUtil.alpha(c));
        assertEquals(0xD9, ColorUtil.red(c));
        assertEquals(0x77, ColorUtil.green(c));
        assertEquals(0x57, ColorUtil.blue(c));
        assertEquals(0x40D97757, ColorUtil.withAlpha(c, 0x40));
        assertEquals(0x40D97757, ColorUtil.fade(c, 0.5f));
        assertEquals("#80D97757", ColorUtil.hex(c));
        assertEquals(0xFFD97757, ColorUtil.parseHex("#D97757", 0));
        assertEquals(0x80D97757, ColorUtil.parseHex("80D97757", 0));
        assertEquals(7, ColorUtil.parseHex("мусор", 7));
    }

    @Test
    void lerpAndHsv() {
        assertEquals(0xFF000000, ColorUtil.lerp(0xFF000000, 0xFFFFFFFF, 0f));
        assertEquals(0xFFFFFFFF, ColorUtil.lerp(0xFF000000, 0xFFFFFFFF, 1f));
        assertEquals(0xFF808080, ColorUtil.lerp(0xFF000000, 0xFFFFFFFF, 0.5f) | 0xFF000000);
        assertEquals(0xFFFF0000, ColorUtil.hsv(0f, 1f, 1f));
        assertEquals(0xFF00FF00, ColorUtil.hsv(1f / 3f, 1f, 1f));
        assertEquals(0xFF0000FF, ColorUtil.hsv(2f / 3f, 1f, 1f));
        assertEquals(255, ColorUtil.alpha(ColorUtil.rainbow(0)));
        assertEquals(0xFF5FB36A, ColorUtil.health(1f));
        assertEquals(0xFFE05A4F, ColorUtil.health(0f));
    }

    @Test
    void easing() {
        assertEquals(0f, Anim.easeOut(0f), 1e-6);
        assertEquals(1f, Anim.easeOut(1f), 1e-6);
        assertEquals(1f, Anim.easeOut(5f), 1e-6);
        assertEquals(0.5f, Anim.easeInOut(0.5f), 1e-6);
        Anim a = new Anim(0f, 1000f);
        a.to(10f);
        a.snap(3f);
        assertEquals(3f, a.get(), 1e-6);
        assertTrue(a.done());
    }

    @Test
    void textHelpers() {
        assertEquals("1:05", TextUtil.seconds(65 * 20));
        assertEquals("1:00:00", TextUtil.seconds(3600 * 20));
        assertEquals("IV", TextUtil.roman(4));
        assertEquals("11", TextUtil.roman(11));
        assertEquals("3.14", TextUtil.fixed(Math.PI, 2));
        assertEquals("abc", TextUtil.stripFormatting("§6a§lb§rc"));
    }

    @Test
    void keyNames() {
        assertEquals("A", KeyNames.name(65));
        assertEquals("F5", KeyNames.name(294));
        assertEquals("Space", KeyNames.name(32));
        assertEquals("Нет", KeyNames.name(-1));
    }

    @Test
    void profileNamesSanitized() {
        assertEquals("default", ConfigManager.sanitize(""));
        assertEquals("default", ConfigManager.sanitize("  ../.. "));
        assertEquals("мойпрофиль_2", ConfigManager.sanitize("мой/профиль_2"));
        assertEquals("мой профиль", ConfigManager.sanitize("мой профиль"));
        assertEquals(32, ConfigManager.sanitize("a".repeat(50)).length());
    }

    @Test
    void themes() {
        assertSame(Theme.CLAUDE, Theme.byName("нет такой"));
        assertEquals("Ночь", Theme.byName("Ночь").name());
        Theme t = Theme.CLAUDE.withAccent(0xFF112233);
        assertEquals(0xFF112233, t.accent);
        assertEquals(0x112233, t.accentSoft & 0xFFFFFF);
        assertEquals(5, Theme.ALL.size());
    }
}
