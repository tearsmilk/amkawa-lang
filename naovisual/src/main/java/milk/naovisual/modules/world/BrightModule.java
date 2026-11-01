package milk.naovisual.modules.world;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.NumberSetting;

/** Полная яркость через подмену гаммы при построении текстуры освещения. */
public class BrightModule extends Module {
    private final NumberSetting gamma = add(new NumberSetting("Яркость", "Уровень гаммы (1 — ванильный максимум)", 12, 1, 20, 0.5));

    public BrightModule() {
        super("Bright", "Яркость", "Полная яркость: видно в пещерах и ночью", ModuleCategory.WORLD);
    }

    public double gamma() { return gamma.get(); }
}
