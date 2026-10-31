package milk.naovisual.core.util;

/** Работа с цветами ARGB: радуга, смешивание, прозрачность. */
public final class ColorUtil {
    private ColorUtil() {}

    public static int alpha(int c) { return (c >>> 24) & 0xFF; }
    public static int red(int c) { return (c >> 16) & 0xFF; }
    public static int green(int c) { return (c >> 8) & 0xFF; }
    public static int blue(int c) { return c & 0xFF; }

    public static int argb(int a, int r, int g, int b) {
        return (clamp(a) << 24) | (clamp(r) << 16) | (clamp(g) << 8) | clamp(b);
    }

    public static int rgb(int r, int g, int b) { return argb(255, r, g, b); }

    public static int withAlpha(int c, int a) { return (c & 0xFFFFFF) | (clamp(a) << 24); }

    public static int withAlpha(int c, float factor) { return withAlpha(c, Math.round(alpha(c) * clamp01(factor))); }

    /** Умножает альфу на коэффициент (0..1). */
    public static int fade(int c, float factor) { return withAlpha(c, Math.round(alpha(c) * clamp01(factor))); }

    public static int lerp(int a, int b, float t) {
        t = clamp01(t);
        return argb(
                Math.round(alpha(a) + (alpha(b) - alpha(a)) * t),
                Math.round(red(a) + (red(b) - red(a)) * t),
                Math.round(green(a) + (green(b) - green(a)) * t),
                Math.round(blue(a) + (blue(b) - blue(a)) * t));
    }

    /** Радуга по времени (полный круг — 4 секунды), offset в долях круга. */
    public static int rainbow(double offset) {
        double t = (System.currentTimeMillis() % 4000L) / 4000.0 + offset;
        t -= Math.floor(t);
        return hsv((float) t, 0.65f, 1f);
    }

    public static int hsv(float h, float s, float v) {
        h -= (float) Math.floor(h);
        float r, g, b;
        int i = (int) (h * 6f);
        float f = h * 6f - i;
        float p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
        switch (i % 6) {
            case 0 -> { r = v; g = t; b = p; }
            case 1 -> { r = q; g = v; b = p; }
            case 2 -> { r = p; g = v; b = t; }
            case 3 -> { r = p; g = q; b = v; }
            case 4 -> { r = t; g = p; b = v; }
            default -> { r = v; g = p; b = q; }
        }
        return rgb(Math.round(r * 255), Math.round(g * 255), Math.round(b * 255));
    }

    /** Цвет для доли здоровья: красный → жёлтый → зелёный. */
    public static int health(float fraction) {
        fraction = clamp01(fraction);
        if (fraction < 0.5f) return lerp(0xFFE05A4F, 0xFFE8B84A, fraction * 2f);
        return lerp(0xFFE8B84A, 0xFF5FB36A, (fraction - 0.5f) * 2f);
    }

    public static int darker(int c, float factor) {
        return argb(alpha(c), Math.round(red(c) * factor), Math.round(green(c) * factor), Math.round(blue(c) * factor));
    }

    public static int brighter(int c, float add) {
        return argb(alpha(c), Math.round(red(c) + (255 - red(c)) * add), Math.round(green(c) + (255 - green(c)) * add), Math.round(blue(c) + (255 - blue(c)) * add));
    }

    public static float luminance(int c) {
        return (0.2126f * red(c) + 0.7152f * green(c) + 0.0722f * blue(c)) / 255f;
    }

    public static String hex(int argb) { return String.format("#%08X", argb); }

    public static int parseHex(String s, int fallback) {
        try {
            String h = s.trim();
            if (h.startsWith("#")) h = h.substring(1);
            if (h.length() == 6) return (int) (Long.parseLong(h, 16) | 0xFF000000L);
            if (h.length() == 8) return (int) Long.parseLong(h, 16);
        } catch (NumberFormatException ignored) {}
        return fallback;
    }

    private static int clamp(int v) { return Math.max(0, Math.min(255, v)); }
    private static float clamp01(float v) { return Math.max(0f, Math.min(1f, v)); }
}
