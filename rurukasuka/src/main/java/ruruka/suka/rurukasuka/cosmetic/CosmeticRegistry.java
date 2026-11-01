package ruruka.suka.rurukasuka.cosmetic;

import java.util.ArrayList;
import java.util.List;

/** Каталог косметики, загружаемый с сайта (не хардкод). */
public final class CosmeticRegistry {
    private static final List<Cosmetic> ALL = new ArrayList<>();
    private static volatile boolean loaded = false;

    public static boolean isLoaded() { return loaded; }

    public static void load(List<Cosmetic> items) {
        ALL.clear();
        ALL.addAll(items);
        loaded = true;
    }

    public static List<Cosmetic> all() { return List.copyOf(ALL); }

    public static List<Cosmetic> byCategory(CosmeticCategory category) {
        List<Cosmetic> out = new ArrayList<>();
        for (Cosmetic c : ALL) if (c.category() == category) out.add(c);
        return out;
    }

    private CosmeticRegistry() {}
}
