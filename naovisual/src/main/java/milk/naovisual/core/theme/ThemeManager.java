package milk.naovisual.core.theme;

/** Текущая тема; модуль «Тема» подменяет её. */
public final class ThemeManager {
    private static Theme current = Theme.BLACK.withOpacity(0.75f);

    private ThemeManager() {}

    public static Theme current() { return current; }
    public static void set(Theme t) { if (t != null) current = t; }
}
