package milk.naovisual.modules.world;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.setting.SelectSetting;

/** Время суток только на клиенте: фиксированное или с своей скоростью. */
public class TimeModule extends Module {
    private final SelectSetting preset = add(new SelectSetting("Пресет", "", "Закат", "Утро", "День", "Закат", "Ночь", "Своё"));
    private final NumberSetting time = add(new NumberSetting("Время", "Тики суток (0–24000)", 13000, 0, 24000, 100).visibleWhen(() -> preset.is("Своё")));
    private final BooleanSetting cycle = add(new BooleanSetting("Движение", "Время идёт со своей скоростью", false));
    private final NumberSetting speed = add(new NumberSetting("Скорость", "Тиков в тик", 20, 1, 500, 1).visibleWhen(cycle::on));
    private long offset;

    public TimeModule() {
        super("Time", "Время", "Своё время суток на клиенте: утро, день, закат, ночь", ModuleCategory.WORLD);
    }

    @Override public void onTick() { if (cycle.on()) offset = (offset + speed.getInt()) % 24000; }

    public long dayTime() {
        long base = switch (preset.get()) {
            case "Утро" -> 1000;
            case "День" -> 6000;
            case "Ночь" -> 18000;
            case "Своё" -> time.getInt();
            default -> 13000;
        };
        return (base + (cycle.on() ? offset : 0)) % 24000;
    }
}
