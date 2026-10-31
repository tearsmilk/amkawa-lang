package milk.naovisual.core.render;

import milk.naovisual.core.util.ColorUtil;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.GuiGraphics;

/** Примитивы 2D: прямоугольники со скруглением, градиенты, рамки, текст, полосы прогресса. */
public final class Render2D {
    private Render2D() {}

    public static Font font() { return Minecraft.getInstance().font; }

    public static void rect(GuiGraphics g, int x, int y, int w, int h, int color) {
        if (w <= 0 || h <= 0 || ColorUtil.alpha(color) == 0) return;
        g.fill(x, y, x + w, y + h, color);
    }

    /** Скруглённый прямоугольник: центр + ступенчатые углы по окружности. */
    public static void roundedRect(GuiGraphics g, int x, int y, int w, int h, int radius, int color) {
        if (w <= 0 || h <= 0 || ColorUtil.alpha(color) == 0) return;
        int r = Math.max(0, Math.min(radius, Math.min(w, h) / 2));
        if (r == 0) { g.fill(x, y, x + w, y + h, color); return; }
        g.fill(x, y + r, x + w, y + h - r, color);
        for (int i = 0; i < r; i++) {
            // горизонтальная полоса на расстоянии i от края: ширина выреза по окружности
            double dy = r - i - 0.5;
            int cut = r - (int) Math.round(Math.sqrt(Math.max(0, r * r - dy * dy)));
            g.fill(x + cut, y + i, x + w - cut, y + i + 1, color);
            g.fill(x + cut, y + h - i - 1, x + w - cut, y + h - i, color);
        }
    }

    public static void roundedOutline(GuiGraphics g, int x, int y, int w, int h, int radius, int color) {
        if (w <= 0 || h <= 0) return;
        int r = Math.max(0, Math.min(radius, Math.min(w, h) / 2));
        g.fill(x + r, y, x + w - r, y + 1, color);
        g.fill(x + r, y + h - 1, x + w - r, y + h, color);
        g.fill(x, y + r, x + 1, y + h - r, color);
        g.fill(x + w - 1, y + r, x + w, y + h - r, color);
        for (int i = 0; i < r; i++) {
            double dy = r - i - 0.5;
            int cut = r - (int) Math.round(Math.sqrt(Math.max(0, r * r - dy * dy)));
            double dy2 = r - i - 1.5;
            int cut2 = i + 1 < r ? r - (int) Math.round(Math.sqrt(Math.max(0, r * r - dy2 * dy2))) : 0;
            int from = Math.min(cut, cut2 == 0 ? cut : cut2), to = Math.max(cut, cut2 == 0 ? cut + 1 : cut2);
            if (to <= from) to = from + 1;
            g.fill(x + from, y + i, x + to, y + i + 1, color);
            g.fill(x + w - to, y + i, x + w - from, y + i + 1, color);
            g.fill(x + from, y + h - i - 1, x + to, y + h - i, color);
            g.fill(x + w - to, y + h - i - 1, x + w - from, y + h - i, color);
        }
    }

    public static void gradientV(GuiGraphics g, int x, int y, int w, int h, int top, int bottom) {
        if (w <= 0 || h <= 0) return;
        g.fillGradient(x, y, x + w, y + h, top, bottom);
    }

    /** Горизонтальный градиент — полосами по 1 px. */
    public static void gradientH(GuiGraphics g, int x, int y, int w, int h, int left, int right) {
        if (w <= 0 || h <= 0) return;
        for (int i = 0; i < w; i++) {
            g.fill(x + i, y, x + i + 1, y + h, ColorUtil.lerp(left, right, i / (float) Math.max(1, w - 1)));
        }
    }

    public static void outline(GuiGraphics g, int x, int y, int w, int h, int color) {
        g.renderOutline(x, y, w, h, color);
    }

    /** Тень под панелью: несколько полупрозрачных рамок. */
    public static void shadow(GuiGraphics g, int x, int y, int w, int h, int radius, int strength) {
        for (int i = 1; i <= 4; i++) {
            int a = Math.max(0, strength - i * (strength / 5));
            roundedOutline(g, x - i, y - i + 1, w + i * 2, h + i * 2, radius + i, ColorUtil.argb(a, 0, 0, 0));
        }
    }

    public static void text(GuiGraphics g, String s, int x, int y, int color) {
        g.drawString(font(), s, x, y, color, false);
    }

    public static void textShadow(GuiGraphics g, String s, int x, int y, int color) {
        g.drawString(font(), s, x, y, color, true);
    }

    public static void text(GuiGraphics g, String s, int x, int y, int color, boolean shadow) {
        g.drawString(font(), s, x, y, color, shadow);
    }

    public static void textCentered(GuiGraphics g, String s, int cx, int y, int color, boolean shadow) {
        g.drawString(font(), s, cx - width(s) / 2, y, color, shadow);
    }

    public static void textRight(GuiGraphics g, String s, int rightX, int y, int color, boolean shadow) {
        g.drawString(font(), s, rightX - width(s), y, color, shadow);
    }

    /** Текст, масштабированный через матрицу (для дробных размеров). */
    public static void textScaled(GuiGraphics g, String s, float x, float y, float scale, int color, boolean shadow) {
        g.pose().pushMatrix();
        g.pose().translate(x, y);
        g.pose().scale(scale, scale);
        g.drawString(font(), s, 0, 0, color, shadow);
        g.pose().popMatrix();
    }

    public static int width(String s) { return font().width(s); }
    public static int lineHeight() { return font().lineHeight; }

    public static String trim(String s, int maxWidth) {
        if (width(s) <= maxWidth) return s;
        String t = font().plainSubstrByWidth(s, Math.max(0, maxWidth - width("…")));
        return t + "…";
    }

    /** Полоса прогресса со скруглением. */
    public static void bar(GuiGraphics g, int x, int y, int w, int h, float fraction, int back, int fill) {
        roundedRect(g, x, y, w, h, h / 2, back);
        int fw = Math.round(w * Math.max(0, Math.min(1, fraction)));
        if (fw > 0) roundedRect(g, x, y, Math.max(fw, Math.min(w, h)), h, h / 2, fill);
    }

    /** Полоса с градиентом слева направо. */
    public static void barGradient(GuiGraphics g, int x, int y, int w, int h, float fraction, int back, int from, int to) {
        roundedRect(g, x, y, w, h, h / 2, back);
        int fw = Math.round(w * Math.max(0, Math.min(1, fraction)));
        if (fw <= 0) return;
        g.enableScissor(x, y, x + fw, y + h);
        for (int i = 0; i < fw; i++) {
            int c = ColorUtil.lerp(from, to, i / (float) Math.max(1, w - 1));
            g.fill(x + i, y, x + i + 1, y + h, c);
        }
        g.disableScissor();
    }

    /** Заполненный круг. */
    public static void circle(GuiGraphics g, int cx, int cy, int radius, int color) {
        for (int dy = -radius; dy < radius; dy++) {
            double yy = dy + 0.5;
            int dx = (int) Math.round(Math.sqrt(Math.max(0, radius * radius - yy * yy)));
            g.fill(cx - dx, cy + dy, cx + dx, cy + dy + 1, color);
        }
    }

    /** Кольцо (дуга в долях 0..1 от верха по часовой), шагами по 1 px. */
    public static void ring(GuiGraphics g, float cx, float cy, float radius, float thickness, float fraction, int color) {
        int steps = (int) Math.max(24, radius * 8);
        int n = (int) Math.round(steps * Math.max(0, Math.min(1, fraction)));
        for (int i = 0; i < n; i++) {
            double a = -Math.PI / 2 + i / (double) steps * Math.PI * 2;
            for (float t = 0; t < thickness; t += 0.5f) {
                int px = Math.round(cx + (float) Math.cos(a) * (radius - t));
                int py = Math.round(cy + (float) Math.sin(a) * (radius - t));
                g.fill(px, py, px + 1, py + 1, color);
            }
        }
    }

    public static void scissor(GuiGraphics g, int x, int y, int w, int h) { g.enableScissor(x, y, x + w, y + h); }
    public static void unscissor(GuiGraphics g) { g.disableScissor(); }
}
