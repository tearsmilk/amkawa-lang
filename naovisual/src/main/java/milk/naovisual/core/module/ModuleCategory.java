package milk.naovisual.core.module;

public enum ModuleCategory {
    HUD("HUD", "HUD"),
    VISUALS("Визуалы", "Visuals"),
    PARTICLES("Частицы", "Particles"),
    WORLD("Мир", "World"),
    OTHER("Прочее", "Other"),
    CLIENT("Клиент", "Client");

    public final String ru;
    public final String en;

    ModuleCategory(String ru, String en) {
        this.ru = ru;
        this.en = en;
    }

    public String title() {
        return milk.naovisual.core.module.Language.english() ? en : ru;
    }
}
