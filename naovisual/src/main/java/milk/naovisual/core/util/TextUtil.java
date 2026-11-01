package milk.naovisual.core.util;

/** Строковые мелочи для HUD. */
public final class TextUtil {
    private TextUtil() {}

    public static String time() {
        java.time.LocalTime t = java.time.LocalTime.now();
        return String.format("%02d:%02d", t.getHour(), t.getMinute());
    }

    public static String seconds(int ticks) {
        int s = Math.max(0, ticks) / 20;
        if (s >= 3600) return String.format("%d:%02d:%02d", s / 3600, (s % 3600) / 60, s % 60);
        return String.format("%d:%02d", s / 60, s % 60);
    }

    public static String roman(int n) {
        if (n <= 0 || n > 10) return String.valueOf(n);
        return new String[]{"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}[n - 1];
    }

    public static String fixed(double v, int digits) {
        return String.format(java.util.Locale.ROOT, "%." + digits + "f", v);
    }

    public static String stripFormatting(String s) {
        return s == null ? "" : s.replaceAll("§.", "");
    }
}
