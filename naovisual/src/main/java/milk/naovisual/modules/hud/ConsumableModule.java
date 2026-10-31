package milk.naovisual.modules.hud;

import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.hud.Panels;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.MultiSelectSetting;
import milk.naovisual.core.setting.SelectSetting;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class ConsumableModule extends HudModule {
    private static final Map<String, Item> ITEMS = new LinkedHashMap<>();
    static {
        ITEMS.put("Тотемы", Items.TOTEM_OF_UNDYING);
        ITEMS.put("Жемчуг", Items.ENDER_PEARL);
        ITEMS.put("Кристаллы", Items.END_CRYSTAL);
        ITEMS.put("Обсидиан", Items.OBSIDIAN);
        ITEMS.put("Золотые яблоки", Items.GOLDEN_APPLE);
        ITEMS.put("Зачарованные яблоки", Items.ENCHANTED_GOLDEN_APPLE);
        ITEMS.put("Опыт", Items.EXPERIENCE_BOTTLE);
        ITEMS.put("Якоря", Items.RESPAWN_ANCHOR);
        ITEMS.put("Светокамень", Items.GLOWSTONE);
        ITEMS.put("Ветряные заряды", Items.WIND_CHARGE);
        ITEMS.put("Стрелы", Items.ARROW);
        ITEMS.put("Хорус", Items.CHORUS_FRUIT);
    }

    private final MultiSelectSetting shown = add(new MultiSelectSetting("Предметы", "Какие расходники считать", List.copyOf(ITEMS.keySet()),
            "Тотемы", "Жемчуг", "Кристаллы", "Обсидиан", "Золотые яблоки", "Опыт"));
    private final SelectSetting layout = add(new SelectSetting("Расположение", "", "Горизонтально", "Горизонтально", "Вертикально"));
    private final BooleanSetting hideEmpty = add(new BooleanSetting("Скрывать нули", "Не показывать предметы, которых нет", true));
    private final BooleanSetting background = add(new BooleanSetting("Фон", "", true));

    public ConsumableModule() {
        super("Consumable", "Расходники", "Счётчик тотемов, жемчуга, кристаллов, яблок и других расходников в инвентаре", 0.5 + 0.1, 0.78);
    }

    @Override
    protected void renderHud(GuiGraphics g, float partial, boolean editor) {
        var player = mc().player;
        boolean horizontal = layout.is("Горизонтально");
        int cell = 20;
        java.util.List<Map.Entry<Item, Integer>> rows = new java.util.ArrayList<>();
        for (Map.Entry<String, Item> e : ITEMS.entrySet()) {
            if (!shown.has(e.getKey())) continue;
            int n = 0;
            if (player != null) {
                for (ItemStack st : player.getInventory().getNonEquipmentItems()) if (st.is(e.getValue())) n += st.getCount();
                if (player.getOffhandItem().is(e.getValue())) n += player.getOffhandItem().getCount();
            }
            if (editor && n == 0) n = 1 + rows.size();
            if (n == 0 && hideEmpty.on()) continue;
            rows.add(Map.entry(e.getValue(), n));
        }
        int count = Math.max(1, rows.size());
        int w = horizontal ? count * cell + 6 : cell + 30, h = horizontal ? cell + 6 : count * cell + 6;
        setSize(w, h);
        if (background.on()) Panels.panel(g, 0, 0, w, h, 0.85f);
        int i = 0;
        for (var r : rows) {
            int x = horizontal ? 3 + i * cell : 3, y = horizontal ? 3 : 3 + i * cell;
            ItemStack st = new ItemStack(r.getKey());
            g.renderItem(st, x + 2, y + 2);
            String n = String.valueOf(r.getValue());
            if (horizontal) Render2D.textScaled(g, n, x + cell - Render2D.width(n) * 0.8f - 1, y + cell - 7, 0.8f, 0xFFFFFFFF, true);
            else Render2D.text(g, n, x + cell + 3, y + 6, Panels.text());
            i++;
        }
    }
}
