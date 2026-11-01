package ruruka.suka.rurukasuka.cosmetic;

/** Категории косметики RurukaSuka. slotKey — куда крепится (для будущего рендера на игроке). */
public enum CosmeticCategory {
    HATS("rurukasuka.category.hats", "rurukasuka.slot.head"),
    WINGS("rurukasuka.category.wings", "rurukasuka.slot.back"),
    BACK("rurukasuka.category.back", "rurukasuka.slot.back"),
    PETS("rurukasuka.category.pets", "rurukasuka.slot.shoulders"),
    ARMS("rurukasuka.category.arms", "rurukasuka.slot.arms"),
    LEGS("rurukasuka.category.legs", "rurukasuka.slot.legs"),
    AURAS("rurukasuka.category.auras", "rurukasuka.slot.aura"),
    COSTUMES("rurukasuka.category.costumes", "rurukasuka.slot.costume");

    public final String translationKey;
    public final String slotKey;

    CosmeticCategory(String translationKey, String slotKey) {
        this.translationKey = translationKey;
        this.slotKey = slotKey;
    }

    /** Маппинг из ключа сайта ("hats" и т.п.). */
    public static CosmeticCategory fromApi(String key) {
        if (key == null) return HATS;
        try {
            return valueOf(key.trim().toUpperCase());
        } catch (IllegalArgumentException e) {
            return HATS;
        }
    }
}
