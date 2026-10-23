package ruruka.suka.rurukasuka.ui;

/** Палитра RurukaSuka — минимализм: тёмно-серые плоские панели, тонкие линии, белый акцент. */
public final class Palette {
    public static final int BG         = 0xFF101012; // фон-подложка (тёмно-серый, непрозрачный)
    public static final int PANEL      = 0xFF17181B; // окно
    public static final int PANEL_2    = 0xFF1E1F23; // вложенные панели
    public static final int CARD       = 0xFF1C1D20;
    public static final int CARD_HOVER = 0xFF26272C;
    public static final int PREVIEW    = 0xFF141416; // фон превью-бокса (темнее — модель читается)
    public static final int STROKE     = 0xFF303136; // тонкая линия-разделитель
    public static final int ACCENT     = 0xFFFFFFFF; // белый — выбранное/активное
    public static final int ACCENT_2   = 0xFFC85A5A; // приглушённый красный — только ошибки
    public static final int TEXT       = 0xFFECECEE;
    public static final int MUTED      = 0xFF74757A;

    private Palette() {}
}
