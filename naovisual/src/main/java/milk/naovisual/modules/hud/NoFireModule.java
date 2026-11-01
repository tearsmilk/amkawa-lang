package milk.naovisual.modules.hud;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.NumberSetting;

/** Убирает или опускает огонь на экране от первого лица. */
public class NoFireModule extends Module {
    private final BooleanSetting hide = add(new BooleanSetting("Скрыть полностью", "Не рисовать огонь вообще", false));
    private final NumberSetting offset = add(new NumberSetting("Смещение вниз", "Насколько опустить пламя", 0.3, 0.0, 1.0, 0.05).visibleWhen(() -> !hide.on()));

    public NoFireModule() {
        super("NoFire", "Без огня", "Опускает или скрывает огонь, закрывающий обзор, когда вы горите", ModuleCategory.HUD);
    }

    public boolean hide() { return hide.on(); }
    public float offset() { return offset.getFloat(); }
}
