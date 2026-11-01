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

    /** Размер одной единицы текущей матрицы в пикселях экрана. */
    private static float pxScale(GuiGraphics g) {
        float m = Math.abs(g.pose().m00());
        return m < 0.01f ? 1f : m * (float) Minecraft.getInstance().getWindow().getGuiScale();
    }

    private static int px(GuiGraphics g, float units) { return Math.max(1, Math.round(units * pxScale(g))); }

    /** Четверть текстуры (2·n × 2·n) в прямоугольник (x, y, s, s). qx/qy — 0 или 1 (левая/правая, верх/низ). */
    private static void quarter(GuiGraphics g, net.minecraft.resources.Identifier tex, int x, int y, int s, int n, int qx, int qy, int color) {
        g.blit(net.minecraft.client.renderer.RenderPipelines.GUI_TEXTURED, tex, x, y, qx * n, qy * n, s, s, n, n, n * 2, n * 2, color);
    }

    /** Скруглённый прямоугольник со сглаженными углами: крест из заливок + четыре угла-текстуры, без щелей. */
    public static void roundedRect(GuiGraphics g, int x, int y, int w, int h, int radius, int color) {
        if (w <= 0 || h <= 0 || ColorUtil.alpha(color) == 0) return;
        int r = Math.max(0, Math.min(radius, Math.min(w, h) / 2));
        if (r == 0) { g.fill(x, y, x + w, y + h, color); return; }
        g.fill(x + r, y, x + w - r, y + h, color);
        g.fill(x, y + r, x + r, y + h - r, color);
        g.fill(x + w - r, y + r, x + w, y + h - r, color);
        int n = px(g, r);
        var tex = Shapes.disk(n);
        quarter(g, tex, x, y, r, n, 0, 0, color);
        quarter(g, tex, x + w - r, y, r, n, 1, 0, color);
        quarter(g, tex, x, y + h - r, r, n, 0, 1, color);
        quarter(g, tex, x + w - r, y + h - r, r, n, 1, 1, color);
    }

    /** Тонкая сглаженная обводка (1 единица) того же скругления. */
    public static void roundedOutline(GuiGraphics g, int x, int y, int w, int h, int radius, int color) {
        if (w <= 0 || h <= 0 || ColorUtil.alpha(color) == 0) return;
        int r = Math.max(1, Math.min(radius, Math.min(w, h) / 2));
        g.fill(x + r, y, x + w - r, y + 1, color);
        g.fill(x + r, y + h - 1, x + w - r, y + h, color);
        g.fill(x, y + r, x + 1, y + h - r, color);
        g.fill(x + w - 1, y + r, x + w, y + h - r, color);
        int n = px(g, r);
        var tex = Shapes.ring(n, Math.min(n, px(g, 1)));
        quarter(g, tex, x, y, r, n, 0, 0, color);
        quarter(g, tex, x + w - r, y, r, n, 1, 0, color);
        quarter(g, tex, x, y + h - r, r, n, 0, 1, color);
        quarter(g, tex, x + w - r, y + h - r, r, n, 1, 1, color);
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

    /** Мягкая тень вокруг панели (гауссоподобный спад), внутри панели не рисуется. */
    public static void shadow(GuiGraphics g, int x, int y, int w, int h, int radius, int strength) {
        if (strength <= 0 || w <= 0 || h <= 0) return;
        int r = Math.max(1, Math.min(radius, Math.min(w, h) / 2));
        int s = 10;
        int n = px(g, r), sp = px(g, s), c = r + s, nc = n + sp;
        var tex = Shapes.shadow(n, sp);
        int color = ColorUtil.argb(Math.min(255, strength * 2), 0, 0, 0);
        y += 2;
        quarter(g, tex, x - s, y - s, c, nc, 0, 0, color);
        quarter(g, tex, x + w - r, y - s, c, nc, 1, 0, color);
        quarter(g, tex, x - s, y + h - r, c, nc, 0, 1, color);
        quarter(g, tex, x + w - r, y + h - r, c, nc, 1, 1, color);
        var pl = net.minecraft.client.renderer.RenderPipelines.GUI_TEXTURED;
        int t = nc * 2;
        if (w > 2 * r) {
            g.blit(pl, tex, x + r, y - s, nc - 1, 0, w - 2 * r, s, 1, sp, t, t, color);
            g.blit(pl, tex, x + r, y + h, nc - 1, nc + n, w - 2 * r, s, 1, sp, t, t, color);
        }
        if (h > 2 * r) {
            g.blit(pl, tex, x - s, y + r, 0, nc - 1, s, h - 2 * r, sp, 1, t, t, color);
            g.blit(pl, tex, x + w, y + r, nc + n, nc - 1, s, h - 2 * r, sp, 1, t, t, color);
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

    /** Текст без размытия внутри масштабированной матрицы: точка переводится в экранные пиксели и округляется, а шрифт
     *  рисуется с чистым масштабом (кратным 0,5, не меньше 1), чтобы глифы ложились на пиксели. */
    public static void textCrisp(GuiGraphics g, String s, float x, float y, float scale, int color, boolean shadow) {
        var pose = g.pose();
        float m = pose.m00();
        float e = crispScale(scale * m);
        org.joml.Vector2f p = pose.transformPosition(new org.joml.Vector2f(x, y));
        pose.pushMatrix();
        pose.identity();
        pose.translate(Math.round(p.x), Math.round(p.y));
        pose.scale(e, e);
        g.drawString(font(), s, 0, 0, color, shadow);
        pose.popMatrix();
    }

    /** Ближайший «чистый» масштаб шрифта: кратный 0,5 и не меньше 1. */
    public static float crispScale(float effective) {
        return Math.max(1f, Math.round(effective * 2f) / 2f);
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
        if (radius <= 0 || ColorUtil.alpha(color) == 0) return;
        int n = px(g, radius);
        g.blit(net.minecraft.client.renderer.RenderPipelines.GUI_TEXTURED, Shapes.disk(n), cx - radius, cy - radius, 0, 0,
                radius * 2, radius * 2, n * 2, n * 2, n * 2, n * 2, color);
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
