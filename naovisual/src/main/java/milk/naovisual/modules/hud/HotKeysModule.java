package milk.naovisual.modules.hud;

import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.hud.Panels;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.util.ColorUtil;
import net.minecraft.client.KeyMapping;
import net.minecraft.client.gui.GuiGraphics;

/** Нажатые клавиши: WASD, пробел, shift, ЛКМ/ПКМ с подсветкой. */
public class HotKeysModule extends HudModule {
    private final BooleanSetting mouse = add(new BooleanSetting("Мышь", "Показывать ЛКМ и ПКМ", true));
    private final BooleanSetting space = add(new BooleanSetting("Пробел", "", true));
    private final BooleanSetting shift = add(new BooleanSetting("Shift и Ctrl", "", true));
    private final BooleanSetting cps = add(new BooleanSetting("CPS", "Клики в секунду на кнопках мыши", true));
    private final ColorSetting active = add(new ColorSetting("Цвет нажатия", "", 0xFFD97757));
    private final java.util.ArrayDeque<Long> leftClicks = new java.util.ArrayDeque<>(), rightClicks = new java.util.ArrayDeque<>();
    private boolean leftWas, rightWas;

    public HotKeysModule() {
        super("HotKeys", "Клавиши", "Нажатые клавиши движения и кнопки мыши", 0.9, 0.5);
        active.setMode(ColorSetting.Mode.THEME);
    }

    @Override
    public void onTick() {
        var o = mc().options;
        long now = System.currentTimeMillis();
        boolean l = o.keyAttack.isDown(), r = o.keyUse.isDown();
        if (l && !leftWas) leftClicks.add(now);
        if (r && !rightWas) rightClicks.add(now);
        leftWas = l; rightWas = r;
        while (!leftClicks.isEmpty() && now - leftClicks.peekFirst() > 1000) leftClicks.pollFirst();
        while (!rightClicks.isEmpty() && now - rightClicks.peekFirst() > 1000) rightClicks.pollFirst();
    }

    @Override
    protected void renderHud(GuiGraphics g, float partial, boolean editor) {
        var o = mc().options;
        int k = 20, gap = 2, w = k * 3 + gap * 2, y = 0;
        key(g, o.keyUp, "W", k + gap, 0, k, k, editor);
        y += k + gap;
        key(g, o.keyLeft, "A", 0, y, k, k, editor);
        key(g, o.keyDown, "S", k + gap, y, k, k, editor);
        key(g, o.keyRight, "D", (k + gap) * 2, y, k, k, editor);
        y += k + gap;
        if (mouse.on()) {
            String ls = cps.on() ? "ЛКМ " + leftClicks.size() : "ЛКМ", rs = cps.on() ? "ПКМ " + rightClicks.size() : "ПКМ";
            key(g, o.keyAttack, ls, 0, y, (w - gap) / 2, 14, false);
            key(g, o.keyUse, rs, (w - gap) / 2 + gap, y, (w - gap) / 2, 14, false);
            y += 14 + gap;
        }
        if (shift.on()) {
            key(g, o.keyShift, "Shift", 0, y, (w - gap) / 2, 14, false);
            key(g, o.keySprint, "Ctrl", (w - gap) / 2 + gap, y, (w - gap) / 2, 14, false);
            y += 14 + gap;
        }
        if (space.on()) { key(g, o.keyJump, "▬", 0, y, w, 12, false); y += 12 + gap; }
        setSize(w, y - gap);
    }

    private void key(GuiGraphics g, KeyMapping m, String label, int x, int y, int w, int h, boolean forceOn) {
        boolean down = m.isDown() || forceOn;
        int bg = down ? active.color() : ColorUtil.withAlpha(milk.naovisual.core.theme.ThemeManager.current().panel, 200);
        Render2D.roundedRect(g, x, y, w, h, 4, bg);
        Render2D.textCentered(g, label, x + w / 2, y + h / 2 - 4, down ? 0xFFFFFFFF : Panels.text(), false);
    }
}
