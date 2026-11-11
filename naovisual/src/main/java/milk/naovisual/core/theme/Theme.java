package milk.naovisual.core.theme;

/** Палитра интерфейса: фон, панели, рамки, текст, акцент. */
public final class Theme {
    public final String name;
    public final int background, panel, panelAlt, border, text, textMuted, accent, accentSoft, danger, success;
    public final boolean light;

    public Theme(String name, int background, int panel, int panelAlt, int border, int text, int textMuted,
                 int accent, int accentSoft, int danger, int success, boolean light) {
        this.name = name; this.background = background; this.panel = panel; this.panelAlt = panelAlt; this.border = border;
        this.text = text; this.textMuted = textMuted; this.accent = accent; this.accentSoft = accentSoft;
        this.danger = danger; this.success = success; this.light = light;
    }

    public String name() { return name; }

    /** Основная тема: тёплые тёмно-угольные полупрозрачные панели, тёплый молочный текст, терракотовый акцент;
     *  непрозрачность задаёт слайдер «Прозрачность меню» модуля «Тема» (по умолчанию 75 %). */
    public static final Theme BLACK = new Theme("Тёплая 75 %",
            0xFF1E1A17, 0xFF2A2420, 0xFF241F1B, 0x24FFE9D6,
            0xFFF2E8DF, 0xFFC9BBAF, 0xFFD97757, 0x40D97757, 0xFFE05A4F, 0xFF6FBF7A, false);

    /** Слоновая кость / уголь / терракота — «как у Клода». */
    public static final Theme CLAUDE = new Theme("Клод",
            0xF2F4F1EC, 0xFFFFFFFF, 0xFFF0EDE6, 0xFFE2DDD3,
            0xFF2B2A28, 0xFF8A857C, 0xFFD97757, 0x33D97757, 0xFFC84B3C, 0xFF5FA36A, true);

    public static final Theme NIGHT = new Theme("Ночь",
            0xF2191817, 0xFF242321, 0xFF2E2C29, 0xFF3A3733,
            0xFFF1EFEA, 0xFF9B968D, 0xFFD97757, 0x40D97757, 0xFFE05A4F, 0xFF6FBF7A, false);

    public static final Theme MILK = new Theme("Молоко",
            0xF2FBFAF7, 0xFFFFFFFF, 0xFFF4F1EA, 0xFFE6E1D8,
            0xFF2E2D2A, 0xFF8E8880, 0xFF7E8ED8, 0x337E8ED8, 0xFFC84B3C, 0xFF5FA36A, true);

    public static final Theme SAKURA = new Theme("Сакура",
            0xF2241A20, 0xFF2F2229, 0xFF3A2A33, 0xFF4A3540,
            0xFFFBEFF3, 0xFFB79AA6, 0xFFE88AA8, 0x40E88AA8, 0xFFE05A4F, 0xFF6FBF7A, false);

    public static final Theme OCEAN = new Theme("Океан",
            0xF2101A22, 0xFF18262F, 0xFF1F303B, 0xFF2B4150,
            0xFFE9F1F5, 0xFF8FA6B3, 0xFF4FB3D9, 0x404FB3D9, 0xFFE05A4F, 0xFF6FBF7A, false);

    public static final java.util.List<Theme> ALL = java.util.List.of(BLACK, CLAUDE, NIGHT, MILK, SAKURA, OCEAN);

    public static Theme byName(String name) {
        for (Theme t : ALL) if (t.name.equals(name)) return t;
        if ("Чёрная 75 %".equals(name)) return BLACK;
        return BLACK;
    }

    /** Подсветка строки под курсором: на тёмных темах — белый 8 %, на светлых — панель. */
    public int hover() { return light ? panel : 0x14FFE9D6; }

    /** Умножает непрозрачность фона, панелей и рамок (текст и акцент не трогаем). */
    public Theme withOpacity(float factor) {
        float f = Math.max(0f, Math.min(1f, factor));
        return new Theme(name, mulA(background, f), mulA(panel, f), mulA(panelAlt, f), mulA(border, f),
                text, textMuted, accent, accentSoft, danger, success, light);
    }

    private static int mulA(int c, float f) { return (c & 0xFFFFFF) | (Math.round(((c >>> 24) & 0xFF) * f) << 24); }

    public Theme withAccent(int newAccent) {
        return new Theme(name, background, panel, panelAlt, border, text, textMuted, newAccent,
                (newAccent & 0xFFFFFF) | (light ? 0x33000000 : 0x40000000), danger, success, light);
    }
}
