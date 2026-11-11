package milk.naovisual.menu;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;

/** Состояние меню между открытиями: категория, выбранный модуль, прокрутка. */
public final class MenuState {
    public static ModuleCategory category = ModuleCategory.HUD;
    public static Module selected;
    public static Page page = Page.MODULES;

    public enum Page { MODULES, FRIENDS, PROFILES }

    private MenuState() {}
}
