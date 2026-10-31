package milk.naovisual.modules.client;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.theme.Theme;
import milk.naovisual.core.theme.ThemeManager;

/** Тема интерфейса: палитра, свой акцент, размытие и затемнение за меню. */
public class ThemeModule extends Module {
    private final SelectSetting theme = add(new SelectSetting("Тема", "", "Чёрная 75 %", Theme.ALL.stream().map(Theme::name).toArray(String[]::new)).onChange(v -> refresh()));
    private final BooleanSetting customAccent = add(new BooleanSetting("Свой акцент", "", false).onChange(v -> refresh()));
    private final ColorSetting accent = add(new ColorSetting("Акцент", "", 0xFFD97757, false).visibleWhen(customAccent::on).onChange(v -> refresh()));
    private final NumberSetting opacity = add(new NumberSetting("Прозрачность меню", "Непрозрачность панелей меню, %", 75, 10, 100, 5).onChange(v -> refresh()));
    private final BooleanSetting blur = add(new BooleanSetting("Размытие", "Размывать мир за меню", true));
    private final NumberSetting blurStrength = add(new NumberSetting("Сила размытия", "", 6, 1, 10, 1).visibleWhen(blur::on));
    private final NumberSetting dim = add(new NumberSetting("Затемнение", "Затемнение мира за меню", 64, 0, 200, 5));
    private int savedBlurriness = -1;

    public ThemeModule() {
        super("Theme", "Тема", "Палитра интерфейса, акцентный цвет, размытие и затемнение за меню", ModuleCategory.CLIENT);
    }

    @Override public boolean defaultEnabled() { return true; }
    @Override public void onEnable() { refresh(); }
    @Override public void onDisable() { ThemeManager.set(Theme.BLACK); }

    private void refresh() {
        if (!isEnabled()) return;
        Theme t = Theme.byName(theme.get());
        if (customAccent.on()) t = t.withAccent(accent.get() | 0xFF000000);
        ThemeManager.set(t.withOpacity(opacity.getInt() / 100f));
    }

    public boolean blur() { return isEnabled() && blur.on(); }
    public int dim() { return isEnabled() ? dim.getInt() : 64; }

    /** Меню открылось: временно выставляем ванильную силу размытия под свою настройку. */
    public void onMenuOpen() {
        refresh();
        var opt = mc().options.menuBackgroundBlurriness();
        if (savedBlurriness < 0) savedBlurriness = opt.get();
        opt.set(blur() ? blurStrength.getInt() : 0);
    }

    public void onMenuClose() {
        if (savedBlurriness >= 0) { mc().options.menuBackgroundBlurriness().set(savedBlurriness); savedBlurriness = -1; }
    }
}
