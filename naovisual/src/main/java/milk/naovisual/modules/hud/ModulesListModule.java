package milk.naovisual.modules.hud;

import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleRegistry;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.theme.ThemeManager;
import milk.naovisual.core.util.ColorUtil;
import net.minecraft.client.gui.GuiGraphics;

import java.util.ArrayList;
import java.util.List;

/** Список включённых модулей, отсортированный по длине. */
public class ModulesListModule extends HudModule {
    private final SelectSetting style = add(new SelectSetting("Стиль", "", "Плашки", "Плашки", "Текст", "Полоса"));
    private final SelectSetting align = add(new SelectSetting("Выравнивание", "", "Справа", "Слева", "Справа"));
    private final BooleanSetting shadow = add(new BooleanSetting("Тень", "", true));
    private final BooleanSetting hideHud = add(new BooleanSetting("Скрывать HUD-модули", "Не показывать модули категории HUD", true));
    private final ColorSetting color = add(new ColorSetting("Цвет", "Цвет текста / градиента", 0xFFD97757));
    private final ColorSetting color2 = add(new ColorSetting("Второй цвет", "Нижний цвет градиента", 0xFFE8B84A));
    private final BooleanSetting gradient = add(new BooleanSetting("Градиент", "Переход цвета сверху вниз", true));

    public ModulesListModule() {
        super("ModulesList", "Список модулей", "Активные модули столбиком в углу экрана", 0.985, 0.015);
        color.setMode(ColorSetting.Mode.THEME);
    }

    @Override public boolean defaultEnabled() { return true; }

    @Override
    protected void renderHud(GuiGraphics g, float partial, boolean editor) {
        List<Module> list = new ArrayList<>();
        for (Module m : ModuleRegistry.all()) {
            if (!m.isEnabled() || m.hideInList.on()) continue;
            if (hideHud.on() && m instanceof HudModule) continue;
            list.add(m);
        }
        if (editor && list.isEmpty()) list.add(this);
        list.sort((a, b) -> Render2D.width(b.displayName()) - Render2D.width(a.displayName()));
        int maxW = 0;
        for (Module m : list) maxW = Math.max(maxW, Render2D.width(m.displayName()));
        int rowH = style.is("Плашки") ? 13 : 11, pad = style.is("Текст") ? 0 : 6;
        int w = maxW + pad * 2 + (style.is("Полоса") ? 3 : 0), h = Math.max(rowH, list.size() * rowH);
        setSize(w, h);
        boolean right = align.is("Справа");
        int y = 0;
        var t = ThemeManager.current();
        for (int i = 0; i < list.size(); i++) {
            Module m = list.get(i);
            String name = m.displayName();
            float f = list.size() <= 1 ? 0 : i / (float) (list.size() - 1);
            int c = gradient.on() ? ColorUtil.lerp(color.color(), color2.color(), f) : color.color();
            int tw = Render2D.width(name);
            int rowW = style.is("Текст") ? tw : tw + pad * 2 + (style.is("Полоса") ? 3 : 0);
            int x = right ? w - rowW : 0;
            if (style.is("Плашки")) {
                Render2D.rect(g, x, y, rowW, rowH, ColorUtil.withAlpha(t.panel, 190));
                Render2D.text(g, name, x + pad, y + 2, c, shadow.on());
            } else if (style.is("Полоса")) {
                Render2D.rect(g, x, y, rowW, rowH, ColorUtil.withAlpha(t.panel, 190));
                Render2D.rect(g, right ? x + rowW - 2 : x, y, 2, rowH, c);
                Render2D.text(g, name, x + (right ? pad - 2 : pad + 2), y + 1, t.text, shadow.on());
            } else {
                Render2D.text(g, name, x, y + 1, c, shadow.on());
            }
            y += rowH;
        }
    }
}
