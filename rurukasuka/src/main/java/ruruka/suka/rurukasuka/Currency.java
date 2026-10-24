package ruruka.suka.rurukasuka;

/**
 * Валюта мода — «руры». Название и склонение в одном месте:
 * 1 рур, 2 рура, 5 руров, 21 рур, 11 руров ...
 */
public final class Currency {

    public static final String ONE = "рур";    // 1, 21, 101 ...
    public static final String FEW = "рура";   // 2–4, 22–24 ...
    public static final String MANY = "руров"; // 0, 5–20, 25–30 ...

    private Currency() {}

    /** Нужная форма слова для числа. */
    public static String word(long n) {
        long a = Math.abs(n);
        long mod100 = a % 100;
        long mod10 = a % 10;
        if (mod100 >= 11 && mod100 <= 14) return MANY;
        if (mod10 == 1) return ONE;
        if (mod10 >= 2 && mod10 <= 4) return FEW;
        return MANY;
    }

    /** «1 234 рура» — число с разделителем тысяч + слово. */
    public static String format(long n) {
        return amount(n) + " " + word(n);
    }

    /**
     * Число с обычным пробелом между тысячами. Не через локаль: на русской Java она даёт
     * узкий неразрывный пробел, который шрифт Minecraft может нарисовать квадратиком.
     */
    public static String amount(long n) {
        return String.format(java.util.Locale.ROOT, "%,d", n).replace(',', ' ');
    }
}
