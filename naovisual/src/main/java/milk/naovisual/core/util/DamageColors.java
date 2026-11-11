package milk.naovisual.core.util;

import java.util.Locale;

/** Цвета и формат чисел урона: золото — обычный урон, красный — крит, зелёный — лечение. */
public final class DamageColors {
    private DamageColors() {}

    public static final int NORMAL = 0xFFFFC94D;
    public static final int CRIT = 0xFFFF4D4D;
    public static final int HEAL = 0xFF5BE37D;

    /** delta = новое здоровье − старое (отрицательно при уроне). */
    public static int colorFor(float delta, boolean crit) {
        if (delta > 0) return HEAL;
        return crit ? CRIT : NORMAL;
    }

    public static String format(float delta) {
        float a = Math.abs(delta);
        String n = Math.abs(a - Math.round(a)) < 0.05f ? String.valueOf(Math.round(a)) : String.format(Locale.ROOT, "%.1f", a);
        return (delta > 0 ? "+" : "") + n;
    }
}
