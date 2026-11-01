package milk.naovisual.modules.hud;

import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.hud.Panels;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.util.ColorUtil;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

public class ArmorModule extends HudModule {
    private final SelectSetting layout = add(new SelectSetting("Расположение", "", "Горизонтально", "Горизонтально", "Вертикально"));
    private final BooleanSetting durability = add(new BooleanSetting("Прочность", "Процент прочности под предметом", true));
    private final BooleanSetting bars = add(new BooleanSetting("Полосы", "Полоса прочности", true));
    private final BooleanSetting offhand = add(new BooleanSetting("Вторая рука", "Показывать предмет во второй руке", true));
    private final BooleanSetting background = add(new BooleanSetting("Фон", "", true));
    private static final EquipmentSlot[] SLOTS = {EquipmentSlot.HEAD, EquipmentSlot.CHEST, EquipmentSlot.LEGS, EquipmentSlot.FEET};

    public ArmorModule() {
        super("Armor", "Броня", "Надетая броня с прочностью рядом с хотбаром", 0.5 - 0.06, 0.78);
    }

    @Override
    protected void renderHud(GuiGraphics g, float partial, boolean editor) {
        var player = mc().player;
        boolean horizontal = layout.is("Горизонтально");
        int cell = 18, labelH = durability.on() ? 8 : 0;
        int count = SLOTS.length + (offhand.on() ? 1 : 0);
        int w = horizontal ? count * cell + 6 : cell + 6 + (durability.on() ? 22 : 0);
        int h = horizontal ? cell + labelH + 6 : count * cell + 6;
        setSize(w, h);
        if (background.on()) Panels.panel(g, 0, 0, w, h, 0.85f);
        int i = 0;
        for (EquipmentSlot slot : SLOTS) {
            ItemStack st = player == null ? ItemStack.EMPTY : player.getItemBySlot(slot);
            if (editor && st.isEmpty()) st = switch (slot) { case HEAD -> new ItemStack(Items.NETHERITE_HELMET); case CHEST -> new ItemStack(Items.NETHERITE_CHESTPLATE); case LEGS -> new ItemStack(Items.NETHERITE_LEGGINGS); default -> new ItemStack(Items.NETHERITE_BOOTS); };
            drawCell(g, st, horizontal, i++, cell, labelH);
        }
        if (offhand.on()) {
            ItemStack st = player == null ? ItemStack.EMPTY : player.getOffhandItem();
            if (editor && st.isEmpty()) st = new ItemStack(Items.TOTEM_OF_UNDYING);
            drawCell(g, st, horizontal, i, cell, labelH);
        }
    }

    private void drawCell(GuiGraphics g, ItemStack st, boolean horizontal, int i, int cell, int labelH) {
        int x = horizontal ? 3 + i * cell : 3, y = horizontal ? 3 : 3 + i * cell;
        if (st.isEmpty()) {
            Render2D.roundedRect(g, x + 2, y + 2, cell - 4, cell - 4, 3, 0x22000000);
            return;
        }
        g.renderItem(st, x + 1, y + 1);
        if (st.isDamageableItem()) {
            float frac = 1f - st.getDamageValue() / (float) Math.max(1, st.getMaxDamage());
            int c = ColorUtil.health(frac);
            if (bars.on()) Render2D.bar(g, x + 2, y + cell - 2, cell - 4, 2, frac, 0x55000000, c);
            if (durability.on()) {
                String pct = Math.round(frac * 100) + "%";
                if (horizontal) Render2D.textScaled(g, pct, x + cell / 2f - Render2D.width(pct) * 0.5f * 0.75f, y + cell + 1, 0.75f, c, true);
                else Render2D.textScaled(g, pct, x + cell + 2, y + 5, 0.75f, c, true);
            }
        } else if (st.getCount() > 1) {
            g.renderItemDecorations(mc().font, st, x + 1, y + 1);
        }
    }
}
