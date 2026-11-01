package ruruka.suka.rurukasuka.ui;

import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.network.chat.Component;

/**
 * Детали интерфейса в стиле Minecraft — те же, что на сайте rurukaSuka:
 * серое окно с фасками, слоты инвентаря, вкладки как в креативе, чёрная рамка игрока,
 * подсказка предмета, объёмные кнопки. Всё рисуется через fill(), без текстур.
 */
public final class McGui {

    // окно контейнера
    public static final int GUI      = 0xFFC6C6C6;
    public static final int GUI_HI   = 0xFFFFFFFF;
    public static final int GUI_LO   = 0xFF555555;
    public static final int EDGE     = 0xFF000000;
    // слот
    public static final int SLOT     = 0xFF8B8B8B;
    public static final int SLOT_HOV = 0xFFA4A4A4;
    public static final int SLOT_LO  = 0xFF373737;
    // вкладка, которая не выбрана
    public static final int TAB_OFF  = 0xFFA9A9A9;
    // текст на сером
    public static final int INK      = 0xFF3F3F3F;
    public static final int INK_SOFT = 0xFF5E5E5E;
    // вишнёвая роща (акцент сайта)
    public static final int CHERRY    = 0xFFB5476A;
    public static final int CHERRY_HI = 0xFFE58BA8;
    public static final int CHERRY_LO = 0xFF7A2A45;
    public static final int BLOSSOM   = 0xFFF4A6C0;
    // цвета текста Minecraft
    public static final int MC_GOLD  = 0xFFFFAA00;
    public static final int MC_GREEN = 0xFF55FF55;
    public static final int MC_RED   = 0xFFFF5555;
    public static final int MC_GRAY  = 0xFFAAAAAA;
    public static final int WHITE    = 0xFFFFFFFF;
    // подсказка предмета
    public static final int TIP_BG   = 0xF0100010;
    public static final int TIP_B1   = 0xFF5000FF;
    public static final int TIP_B2   = 0xFF28007F;

    /** Окно: чёрный контур со срезанными углами, белая фаска сверху-слева, тёмная снизу-справа. */
    public static void panel(GuiGraphics g, int x1, int y1, int x2, int y2) {
        g.fill(x1 + 1, y1, x2 - 1, y1 + 1, EDGE);
        g.fill(x1 + 1, y2 - 1, x2 - 1, y2, EDGE);
        g.fill(x1, y1 + 1, x1 + 1, y2 - 1, EDGE);
        g.fill(x2 - 1, y1 + 1, x2, y2 - 1, EDGE);
        g.fill(x1 + 1, y1 + 1, x2 - 1, y2 - 1, GUI);
        g.fill(x1 + 1, y1 + 1, x2 - 3, y1 + 3, GUI_HI);   // верхняя фаска
        g.fill(x1 + 1, y1 + 1, x1 + 3, y2 - 3, GUI_HI);   // левая фаска
        g.fill(x1 + 3, y2 - 3, x2 - 1, y2 - 1, GUI_LO);   // нижняя тень
        g.fill(x2 - 3, y1 + 3, x2 - 1, y2 - 1, GUI_LO);   // правая тень
    }

    /** Вкладка над окном. Выбранная заходит в окно и сливается с ним (без нижней кромки). */
    public static void tab(GuiGraphics g, int x1, int y1, int x2, int y2, boolean selected) {
        int body = selected ? GUI : TAB_OFF;
        int bottom = selected ? y2 + 3 : y2;
        g.fill(x1 + 1, y1, x2 - 1, y1 + 1, EDGE);
        g.fill(x1, y1 + 1, x1 + 1, bottom, EDGE);
        g.fill(x2 - 1, y1 + 1, x2, bottom, EDGE);
        g.fill(x1 + 1, y1 + 1, x2 - 1, bottom, body);
        g.fill(x1 + 1, y1 + 1, x2 - 3, y1 + 3, GUI_HI);
        g.fill(x1 + 1, y1 + 1, x1 + 3, bottom, GUI_HI);
        g.fill(x2 - 3, y1 + 3, x2 - 1, bottom, selected ? GUI : GUI_LO);
    }

    /** Слот инвентаря: вдавленный — тёмная кромка сверху-слева, белая снизу-справа. */
    public static void slot(GuiGraphics g, int x1, int y1, int x2, int y2, boolean hover) {
        g.fill(x1, y1, x2, y2, hover ? SLOT_HOV : SLOT);
        g.fill(x1, y1, x2 - 1, y1 + 1, SLOT_LO);
        g.fill(x1, y1, x1 + 1, y2 - 1, SLOT_LO);
        g.fill(x1 + 1, y2 - 1, x2, y2, GUI_HI);
        g.fill(x2 - 1, y1 + 1, x2, y2, GUI_HI);
    }

    /** Выделение выбранного слота — белая рамка с чёрной обводкой, как в хотбаре. */
    public static void selection(GuiGraphics g, int x1, int y1, int x2, int y2) {
        outline(g, x1 - 3, y1 - 3, x2 + 3, y2 + 3, EDGE);
        outline(g, x1 - 2, y1 - 2, x2 + 2, y2 + 2, WHITE);
        outline(g, x1 - 1, y1 - 1, x2 + 1, y2 + 1, WHITE);
    }

    /** Чёрная рамка игрока, вдавленная как слот. */
    public static void frame(GuiGraphics g, int x1, int y1, int x2, int y2) {
        slot(g, x1, y1, x2, y2, false);
        g.fill(x1 + 1, y1 + 1, x2 - 1, y2 - 1, EDGE);
    }

    /** Подсказка предмета: почти чёрный фон, фиолетовая рамка с переходом сверху вниз. */
    public static void tooltip(GuiGraphics g, int x1, int y1, int x2, int y2) {
        g.fill(x1 + 1, y1, x2 - 1, y2, TIP_BG);
        g.fill(x1, y1 + 1, x2, y2 - 1, TIP_BG);
        int mid = (y1 + y2) / 2;
        g.fill(x1 + 1, y1 + 1, x2 - 1, y1 + 2, TIP_B1);
        g.fill(x1 + 1, y2 - 2, x2 - 1, y2 - 1, TIP_B2);
        g.fill(x1 + 1, y1 + 2, x1 + 2, mid, TIP_B1);
        g.fill(x2 - 2, y1 + 2, x2 - 1, mid, TIP_B1);
        g.fill(x1 + 1, mid, x1 + 2, y2 - 2, TIP_B2);
        g.fill(x2 - 2, mid, x2 - 1, y2 - 2, TIP_B2);
    }

    /** Объёмная кнопка. cherry — вишнёвая (главное действие), иначе серая как в игре. */
    public static void button(GuiGraphics g, int x1, int y1, int x2, int y2,
                              boolean cherry, boolean hover, boolean active) {
        int body = !active ? 0xFF4A4A4A : cherry ? CHERRY : 0xFF727272;
        int hi   = !active ? 0xFF5A5A5A : cherry ? CHERRY_HI : 0xFFA5A5A5;
        int lo   = !active ? 0xFF3A3A3A : cherry ? CHERRY_LO : 0xFF4C4C4C;
        g.fill(x1, y1, x2, y2, (hover && active) ? WHITE : EDGE);
        g.fill(x1 + 1, y1 + 1, x2 - 1, y2 - 1, body);
        g.fill(x1 + 1, y1 + 1, x2 - 1, y1 + 2, hi);
        g.fill(x1 + 1, y2 - 3, x2 - 1, y2 - 1, lo);
    }

    public static void outline(GuiGraphics g, int x1, int y1, int x2, int y2, int color) {
        g.fill(x1, y1, x2, y1 + 1, color);
        g.fill(x1, y2 - 1, x2, y2, color);
        g.fill(x1, y1, x1 + 1, y2, color);
        g.fill(x2 - 1, y1, x2, y2, color);
    }

    /** Тёмный текст на сером окне — без тени, как заголовки контейнеров в игре. */
    public static void ink(GuiGraphics g, Font font, String text, int x, int y, int color) {
        g.drawString(font, Component.literal(text), x, y, color, false);
    }

    /** То же, по центру. */
    public static void inkCentered(GuiGraphics g, Font font, String text, int cx, int y, int color) {
        g.drawString(font, Component.literal(text), cx - font.width(text) / 2, y, color, false);
    }

    /** Обрезать строку под ширину с многоточием. */
    public static String fit(Font font, String s, int maxPx) {
        if (s == null) return "";
        if (font.width(s) <= maxPx) return s;
        while (s.length() > 1 && font.width(s + "…") > maxPx) s = s.substring(0, s.length() - 1);
        return s + "…";
    }

    // ── общие куски экранов ──

    /** Звёзды для фона: пары x,y. Один раз на init(). */
    public static int[] stars(int width, int height) {
        java.util.Random r = new java.util.Random(7);
        int[] st = new int[70 * 2];
        for (int i = 0; i < st.length; i += 2) {
            st[i] = r.nextInt(Math.max(1, width));
            st[i + 1] = r.nextInt(Math.max(1, height));
        }
        return st;
    }

    /** Сумеречное небо со звёздами — тот же фон, что на сайте. */
    public static void sky(GuiGraphics g, int width, int height, int[] stars) {
        int top = 0xFF1F1A33, bottom = 0xFF4A3358, bands = 24;
        for (int i = 0; i < bands; i++) {
            float t = i / (float) (bands - 1);
            g.fill(0, height * i / bands, width, height * (i + 1) / bands, lerp(top, bottom, t));
        }
        if (stars == null) return;
        for (int i = 0; i + 1 < stars.length; i += 2) {
            g.fill(stars[i], stars[i + 1], stars[i] + 1, stars[i + 1] + 1, (i % 6 == 0) ? 0xCCFFD6E6 : 0x99FFFFFF);
        }
    }

    private static int lerp(int a, int b, float t) {
        int ar = (a >> 16) & 255, ag = (a >> 8) & 255, ab = a & 255;
        int br = (b >> 16) & 255, bg = (b >> 8) & 255, bb = b & 255;
        return 0xFF000000 | ((int) (ar + (br - ar) * t) << 16) | ((int) (ag + (bg - ag) * t) << 8) | (int) (ab + (bb - ab) * t);
    }

    /** Сообщение строкой чата: «<rurukaSuka> текст» на полупрозрачной плашке. */
    public static void chat(GuiGraphics g, Font font, int x, int y, int maxW, String msg, int color) {
        if (msg == null || msg.isEmpty()) return;
        String who = "<rurukaSuka> ";
        String m = fit(font, msg, maxW - font.width(who) - 10);
        int w = font.width(who) + font.width(m) + 8;
        g.fill(x, y, x + w, y + 12, 0x8C000000);
        g.drawString(font, Component.literal(who), x + 4, y + 2, BLOSSOM);
        g.drawString(font, Component.literal(m), x + 4 + font.width(who), y + 2, color);
    }

    /** Строка «подпись … значение» с разделителем, как в статистике. */
    public static void statRow(GuiGraphics g, Font font, int x1, int x2, int y, String label, String value) {
        g.fill(x1, y, x2, y + 1, SLOT);
        g.fill(x1, y + 1, x2, y + 2, GUI_HI);
        ink(g, font, label, x1, y + 6, INK_SOFT);
        ink(g, font, value, x2 - font.width(value), y + 6, INK);
    }

    /** Перенос текста по словам под ширину (без API шрифта, только width()). */
    public static java.util.List<String> wrap(Font font, String text, int maxPx) {
        java.util.List<String> out = new java.util.ArrayList<>();
        if (text == null) return out;
        StringBuilder line = new StringBuilder();
        for (String word : text.split(" ")) {
            String cand = line.length() == 0 ? word : line + " " + word;
            if (font.width(cand) <= maxPx) { line.setLength(0); line.append(cand); continue; }
            if (line.length() > 0) { out.add(line.toString()); line.setLength(0); }
            // слово длиннее строки — режем по символам
            String w = word;
            while (font.width(w) > maxPx && w.length() > 1) {
                int n = w.length();
                while (n > 1 && font.width(w.substring(0, n)) > maxPx) n--;
                out.add(w.substring(0, n));
                w = w.substring(n);
            }
            line.append(w);
        }
        if (line.length() > 0) out.add(line.toString());
        return out;
    }

    private McGui() {}
}
