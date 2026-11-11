package milk.naovisual.modules.hud;

import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.hud.Panels;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.world.item.ItemStack;

/** Инвентарь 9×3 на экране. */
public class InventoryModule extends HudModule {
    private final BooleanSetting background = add(new BooleanSetting("Фон", "", true));
    private final BooleanSetting title = add(new BooleanSetting("Заголовок", "", true));
    private final BooleanSetting hideEmpty = add(new BooleanSetting("Скрывать пустой", "Не показывать, если инвентарь пуст", false));

    public InventoryModule() {
        super("Inventory", "Инвентарь", "Содержимое инвентаря (3 ряда) на экране", 0.8, 0.6);
    }

    @Override
    protected void renderHud(GuiGraphics g, float partial, boolean editor) {
        var p = mc().player;
        int cell = 18, top = title.on() ? 14 : 4;
        int w = 9 * cell + 8, h = 3 * cell + top + 4;
        setSize(w, h);
        boolean empty = true;
        if (p != null) for (int i = 9; i < 36; i++) if (!p.getInventory().getItem(i).isEmpty()) { empty = false; break; }
        if (empty && hideEmpty.on() && !editor) return;
        if (background.on()) Panels.panel(g, 0, 0, w, h, 0.85f);
        if (title.on()) Render2D.text(g, "Инвентарь", 5, 3, Panels.muted());
        for (int i = 9; i < 36; i++) {
            int col = (i - 9) % 9, row = (i - 9) / 9;
            int x = 4 + col * cell, y = top + row * cell;
            Render2D.roundedRect(g, x + 1, y + 1, cell - 2, cell - 2, 2, 0x18000000);
            if (p == null) continue;
            ItemStack st = p.getInventory().getItem(i);
            if (st.isEmpty()) continue;
            g.renderItem(st, x + 1, y + 1);
            g.renderItemDecorations(mc().font, st, x + 1, y + 1);
        }
    }
}
