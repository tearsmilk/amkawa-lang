package milk.naovisual.modules.hud;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.theme.ThemeManager;
import milk.naovisual.core.util.Anim;
import milk.naovisual.core.util.ColorUtil;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.world.item.ItemStack;

/** Хотбар в стиле клиента: скруглённый фон, плавная рамка выбранного слота, вторая рука и полоса опыта. */
public class HotBarModule extends Module {
    private final BooleanSetting xpBar = add(new BooleanSetting("Полоса опыта", "", true));
    private final BooleanSetting itemName = add(new BooleanSetting("Название предмета", "Над хотбаром при смене", true));
    private final NumberSetting alpha = add(new NumberSetting("Прозрачность фона", "", 0.85, 0.1, 1.0, 0.05));
    private final ColorSetting selection = add(new ColorSetting("Цвет выбора", "", 0xFFD97757));
    private final Anim selAnim = new Anim(0f, 16f);
    private int lastSlot = -1;
    private long slotChangedAt;

    public HotBarModule() {
        super("HotBar", "Хотбар", "Собственный хотбар с плавным выделением слота и полосой опыта", ModuleCategory.HUD);
        selection.setMode(ColorSetting.Mode.THEME);
    }

    @Override
    public void onRenderOverlay(GuiGraphics g, DeltaTracker delta) {
        var p = mc().player;
        if (p == null || mc().options.hideGui || p.isSpectator()) return;
        var t = ThemeManager.current();
        int cx = g.guiWidth() / 2, bottom = g.guiHeight();
        int w = 182, h = 22, x = cx - 91, y = bottom - h;
        int a = Math.round(255 * alpha.getFloat());
        Render2D.roundedRect(g, x, y, w, h, 4, ColorUtil.withAlpha(t.panel, a));
        Render2D.roundedOutline(g, x, y, w, h, 4, ColorUtil.withAlpha(t.border, a));
        int slot = p.getInventory().getSelectedSlot();
        if (slot != lastSlot) { lastSlot = slot; slotChangedAt = System.currentTimeMillis(); }
        selAnim.to(slot);
        float sx = x + 1 + selAnim.get() * 20;
        Render2D.roundedRect(g, Math.round(sx), y + 1, 20, 20, 3, ColorUtil.withAlpha(selection.color(), 70));
        Render2D.roundedOutline(g, Math.round(sx), y + 1, 20, 20, 3, selection.color());
        for (int i = 0; i < 9; i++) {
            ItemStack st = p.getInventory().getItem(i);
            if (st.isEmpty()) continue;
            int ix = x + 3 + i * 20, iy = y + 3;
            g.renderItem(st, ix, iy);
            g.renderItemDecorations(mc().font, st, ix, iy);
        }
        ItemStack off = p.getOffhandItem();
        if (!off.isEmpty()) {
            int ox = p.getMainArm() == net.minecraft.world.entity.HumanoidArm.RIGHT ? x - 29 : x + w + 7;
            Render2D.roundedRect(g, ox - 3, y, 22, h, 4, ColorUtil.withAlpha(t.panel, a));
            Render2D.roundedOutline(g, ox - 3, y, 22, h, 4, ColorUtil.withAlpha(t.border, a));
            g.renderItem(off, ox, y + 3);
            g.renderItemDecorations(mc().font, off, ox, y + 3);
        }
        if (xpBar.on() && mc().gameMode != null && mc().gameMode.hasExperience()) {
            Render2D.bar(g, x, y - 5, w, 3, p.experienceProgress, ColorUtil.withAlpha(t.border, a), 0xFF7FD36A);
            if (p.experienceLevel > 0) Render2D.textShadow(g, String.valueOf(p.experienceLevel), cx - Render2D.width(String.valueOf(p.experienceLevel)) / 2, y - 16, 0xFF9CE76B);
        }
        if (itemName.on()) {
            long since = System.currentTimeMillis() - slotChangedAt;
            ItemStack sel = p.getInventory().getSelectedItem();
            if (since < 2500 && !sel.isEmpty()) {
                float f = since > 2000 ? 1f - (since - 2000) / 500f : 1f;
                String name = sel.getHoverName().getString();
                Render2D.textCentered(g, name, cx, y - 28, ColorUtil.withAlpha(0xFFFFFFFF, Math.max(10, Math.round(255 * f))), true);
            }
        }
    }
}
