package milk.naovisual.core;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import milk.naovisual.core.setting.*;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class SettingsTest {
    @Test
    void numberClampsAndSnapsToStep() {
        NumberSetting n = new NumberSetting("Размер", "", 5, 1, 10, 0.5);
        n.set(7.26);
        assertEquals(7.5, n.get(), 1e-9);
        n.set(99.0);
        assertEquals(10.0, n.get(), 1e-9);
        n.set(-3.0);
        assertEquals(1.0, n.get(), 1e-9);
        n.setFraction(0.5);
        assertEquals(5.5, n.get(), 1e-9);
        assertEquals("5.5", n.format());
        assertEquals("size", new NumberSetting("Size", "", 1, 0, 1, 1).key());
    }

    @Test
    void numberFormatsIntegers() {
        NumberSetting n = new NumberSetting("Кол-во", "", 3, 0, 10, 1, " шт");
        assertEquals("3 шт", n.format());
        assertEquals(3, n.getInt());
    }

    @Test
    void colorSavesModeAndRestores() {
        ColorSetting c = new ColorSetting("Цвет", "", 0x80D97757);
        c.setMode(ColorSetting.Mode.RAINBOW);
        c.set(0x40112233);
        JsonObject saved = c.save().getAsJsonObject();
        ColorSetting restored = new ColorSetting("Цвет", "", 0xFFFFFFFF);
        restored.load(JsonParser.parseString(saved.toString()));
        assertEquals(0x40112233, restored.get());
        assertEquals(ColorSetting.Mode.RAINBOW, restored.mode());
        // радуга сохраняет альфу исходного цвета
        assertEquals(0x40, (restored.color() >>> 24) & 0xFF);
        // старый формат — просто число
        restored.load(JsonParser.parseString("-16777216"));
        assertEquals(0xFF000000, restored.get());
    }

    @Test
    void selectRejectsUnknownAndCycles() {
        SelectSetting s = new SelectSetting("Стиль", "", "Б", "А", "Б", "В");
        s.set("Ж");
        assertEquals("Б", s.get());
        s.next();
        assertEquals("В", s.get());
        s.next();
        assertEquals("А", s.get());
        s.previous();
        assertEquals("В", s.get());
        assertThrows(IllegalArgumentException.class, () -> new SelectSetting("x", "", "нет", "А"));
    }

    @Test
    void multiSelectRoundTrip() {
        MultiSelectSetting m = new MultiSelectSetting("Кого", "", List.of("Игроки", "Мобы", "Предметы"), "Игроки");
        m.toggle("Мобы");
        m.toggle("Игроки");
        m.toggle("Чужое");
        assertTrue(m.has("Мобы"));
        assertFalse(m.has("Игроки"));
        MultiSelectSetting copy = new MultiSelectSetting("Кого", "", List.of("Игроки", "Мобы", "Предметы"));
        copy.load(m.save());
        assertEquals(m.get(), copy.get());
        m.reset();
        assertTrue(m.has("Игроки"));
        assertFalse(m.has("Мобы"));
    }

    @Test
    void keybindMouseEncoding() {
        KeybindSetting k = new KeybindSetting("Клавиша", "", KeybindSetting.NONE);
        assertFalse(k.isBound());
        assertEquals("Нет", k.display());
        k.set(KeybindSetting.ofMouse(2));
        assertTrue(k.isMouse());
        assertEquals(2, k.mouseButton());
        assertEquals("Мышь 3", k.display());
        k.set(344); // GLFW_KEY_RIGHT_SHIFT
        assertEquals("RShift", k.display());
    }

    @Test
    void textTruncatesAndGroupSerializesChildren() {
        TextSetting t = new TextSetting("Текст", "", "abc", 4);
        t.set("abcdefgh");
        assertEquals("abcd", t.get());
        BooleanSetting b = new BooleanSetting("Флаг", "", false);
        GroupSetting g = new GroupSetting("Группа", "", b, t);
        b.set(true);
        g.toggleExpanded();
        JsonObject saved = g.save().getAsJsonObject();
        assertTrue(saved.get("expanded").getAsBoolean());
        assertTrue(saved.get("флаг").getAsBoolean());
        g.reset();
        assertFalse(b.get());
        assertEquals("abc", t.get());
        g.load(saved);
        assertTrue(b.get());
        assertEquals("abcd", t.get());
    }

    @Test
    void visibleWhenAndOnChange() {
        BooleanSetting master = new BooleanSetting("Вкл", "", false);
        int[] changes = {0};
        NumberSetting dep = new NumberSetting("Зависимая", "", 1, 0, 5, 1).visibleWhen(master::on).onChange(v -> changes[0]++);
        assertFalse(dep.isVisible());
        master.set(true);
        assertTrue(dep.isVisible());
        dep.set(1.0);   // то же значение — без события
        dep.set(2.0);
        assertEquals(1, changes[0]);
    }
}
