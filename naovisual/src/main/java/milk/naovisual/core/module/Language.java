package milk.naovisual.core.module;

/** Язык названий модулей (сам интерфейс — на русском, модуль «Язык» переключает на английский). */
public final class Language {
    private static boolean english = false;

    private Language() {}

    public static boolean english() { return english; }
    public static void setEnglish(boolean e) { english = e; }
}
