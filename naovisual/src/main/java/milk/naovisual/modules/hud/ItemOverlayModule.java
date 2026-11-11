package milk.naovisual.modules.hud;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.util.ColorUtil;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.enchantment.EnchantmentHelper;
import net.minecraft.world.item.enchantment.ItemEnchantments;

/** Поверх предметов в хотбаре: прочность в процентах и сокращения чар с уровнем. */
public class ItemOverlayModule extends Module {
    private final BooleanSetting durability = add(new BooleanSetting("Прочность", "Процент прочности над предметом", true));
    private final BooleanSetting enchants = add(new BooleanSetting("Чары", "Сокращения зачарований с уровнем", true));
    private final BooleanSetting onlyHeld = add(new BooleanSetting("Только в руке", "Чары только у выбранного предмета", false));

    public ItemOverlayModule() {
        super("ItemOverlay", "Инфо о предметах", "Прочность и чары поверх предметов хотбара", ModuleCategory.HUD);
    }

    @Override
    public void onRenderOverlay(GuiGraphics g, DeltaTracker delta) {
        var p = mc().player;
        if (p == null || mc().options.hideGui || p.isSpectator()) return;
        int cx = g.guiWidth() / 2, bottom = g.guiHeight();
        int x0 = cx - 91 + 3, y0 = bottom - 22 + 3;
        int selected = p.getInventory().getSelectedSlot();
        for (int i = 0; i < 9; i++) {
            ItemStack st = p.getInventory().getItem(i);
            if (st.isEmpty()) continue;
            int ix = x0 + i * 20, iy = y0;
            if (durability.on() && st.isDamageableItem()) {
                float frac = 1f - st.getDamageValue() / (float) Math.max(1, st.getMaxDamage());
                String s = Math.round(frac * 100) + "%";
                Render2D.textScaled(g, s, ix + 8 - Render2D.width(s) * 0.6f / 2f, iy - 8, 0.6f, ColorUtil.health(frac), true);
            }
            if (enchants.on() && (!onlyHeld.on() || i == selected)) {
                ItemEnchantments ench = EnchantmentHelper.getEnchantmentsForCrafting(st);
                if (ench.isEmpty()) continue;
                int line = 0;
                for (var e : ench.entrySet()) {
                    if (line >= 3) break;
                    String name = e.getKey().value().description().getString();
                    String abbr = abbreviate(name) + (e.getIntValue() > 1 ? e.getIntValue() : "");
                    Render2D.textScaled(g, abbr, ix + 1, iy + 1 + line * 5, 0.5f, 0xFFF1EFEA, true);
                    line++;
                }
            }
        }
    }

    static String abbreviate(String name) {
        String[] parts = name.trim().split("\\s+");
        if (parts.length >= 2) return ("" + parts[0].charAt(0) + parts[1].charAt(0)).toUpperCase();
        return name.length() >= 3 ? name.substring(0, 3) : name;
    }
}
