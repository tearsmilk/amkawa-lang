package milk.naovisual.modules.hud;

import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.hud.Panels;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

import java.util.ArrayList;
import java.util.List;

/** Перезарядки предметов (жемчуг, ветряной заряд, щит, хорус, ядро) — иконка с полосой. */
public class CoolDownsModule extends HudModule {
    private static final Item[] TRACKED = {Items.ENDER_PEARL, Items.WIND_CHARGE, Items.SHIELD, Items.CHORUS_FRUIT, Items.GOAT_HORN, Items.MACE};
    private final BooleanSetting background = add(new BooleanSetting("Фон", "", true));
    private final BooleanSetting percent = add(new BooleanSetting("Проценты", "Показывать процент перезарядки", false));
    private final ColorSetting color = add(new ColorSetting("Цвет полосы", "", 0xFFD97757));

    public CoolDownsModule() {
        super("CoolDowns", "Перезарядки", "Иконки предметов на перезарядке с полосой оставшегося времени", 0.5 + 0.1, 0.72);
        color.setMode(ColorSetting.Mode.THEME);
    }

    @Override
    protected void renderHud(GuiGraphics g, float partial, boolean editor) {
        var player = mc().player;
        List<float[]> rows = new ArrayList<>();
        List<Item> items = new ArrayList<>();
        if (player != null) {
            for (Item it : TRACKED) {
                ItemStack st = new ItemStack(it);
                if (player.getCooldowns().isOnCooldown(st)) { items.add(it); rows.add(new float[]{player.getCooldowns().getCooldownPercent(st, partial)}); }
            }
        }
        if (editor && items.isEmpty()) { items.add(Items.ENDER_PEARL); rows.add(new float[]{0.6f}); }
        int cell = 22, w = Math.max(1, items.size()) * cell + 6, h = cell + 6;
        setSize(w, h);
        if (items.isEmpty()) return;
        if (background.on()) Panels.panel(g, 0, 0, w, h, 0.85f);
        for (int i = 0; i < items.size(); i++) {
            int x = 3 + i * cell, y = 3;
            g.renderItem(new ItemStack(items.get(i)), x + 3, y + 2);
            float f = rows.get(i)[0];
            Render2D.bar(g, x + 2, y + cell - 3, cell - 4, 2, 1f - f, 0x55000000, color.color());
            if (percent.on()) Render2D.textScaled(g, Math.round((1 - f) * 100) + "%", x + 3, y + 1, 0.7f, 0xFFFFFFFF, true);
        }
    }
}
