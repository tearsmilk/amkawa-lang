package milk.naovisual.core.hud;

import milk.naovisual.core.config.ConfigManager;
import milk.naovisual.core.module.ModuleRegistry;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.theme.Theme;
import milk.naovisual.core.theme.ThemeManager;
import milk.naovisual.core.util.ColorUtil;
import milk.naovisual.menu.NaoMenuScreen;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.input.KeyEvent;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.network.chat.Component;
import org.lwjgl.glfw.GLFW;

/** Редактор HUD: перетаскивание элементов, прилипание к центру и краям, колесо — масштаб. */
public class HudEditorScreen extends Screen {
    private final Screen parent;
    private HudModule dragging;
    private int dragDx, dragDy;
    private HudModule hovered;

    public HudEditorScreen(Screen parent) {
        super(Component.literal("Редактор HUD"));
        this.parent = parent;
    }

    @Override
    public void render(GuiGraphics g, int mouseX, int mouseY, float partial) {
        Theme t = ThemeManager.current();
        g.fill(0, 0, width, height, 0x40000000);
        // направляющие
        g.fill(width / 2, 0, width / 2 + 1, height, 0x30FFFFFF);
        g.fill(0, height / 2, width, height / 2 + 1, 0x30FFFFFF);
        hovered = null;
        for (HudModule m : ModuleRegistry.hudModules()) {
            if (!m.isEnabled()) continue;
            m.render(g, partial, true);
            int x = m.x(), y = m.y(), w = m.scaledWidth(), h = m.scaledHeight();
            boolean over = mouseX >= x && mouseX < x + w && mouseY >= y && mouseY < y + h;
            if (over && dragging == null) hovered = m;
            boolean active = m == dragging || (dragging == null && over);
            int c = active ? t.accent : ColorUtil.withAlpha(t.accent, 110);
            Render2D.outline(g, x - 1, y - 1, w + 2, h + 2, c);
            if (active) {
                String label = m.displayName() + "  " + m.scale.format();
                int lw = Render2D.width(label) + 6;
                int lx = Math.min(width - lw, Math.max(0, x));
                int ly = y - 12 < 0 ? y + h + 2 : y - 12;
                Render2D.roundedRect(g, lx, ly, lw, 10, 3, t.panel);
                Render2D.text(g, label, lx + 3, ly + 1, t.text);
            }
        }
        String hint = "Перетаскивайте элементы • колесо — масштаб • ПКМ — настройки • Esc — готово";
        Render2D.roundedRect(g, width / 2 - Render2D.width(hint) / 2 - 6, 6, Render2D.width(hint) + 12, 14, 4, t.panel);
        Render2D.textCentered(g, hint, width / 2, 9, t.text, false);
    }

    @Override
    public boolean mouseClicked(MouseButtonEvent e, boolean doubleClick) {
        HudModule m = at((int) e.x(), (int) e.y());
        if (m == null) return super.mouseClicked(e, doubleClick);
        if (e.button() == GLFW.GLFW_MOUSE_BUTTON_RIGHT) {
            minecraft.setScreen(NaoMenuScreen.forModule(m));
            return true;
        }
        dragging = m;
        dragDx = (int) e.x() - m.x();
        dragDy = (int) e.y() - m.y();
        return true;
    }

    @Override
    public boolean mouseDragged(MouseButtonEvent e, double dx, double dy) {
        if (dragging == null) return super.mouseDragged(e, dx, dy);
        int nx = (int) e.x() - dragDx, ny = (int) e.y() - dragDy;
        int w = dragging.scaledWidth(), h = dragging.scaledHeight();
        // прилипание к центру экрана и краям
        if (Math.abs(nx + w / 2 - width / 2) < 5) nx = width / 2 - w / 2;
        if (Math.abs(ny + h / 2 - height / 2) < 5) ny = height / 2 - h / 2;
        if (Math.abs(nx) < 5) nx = 0;
        if (Math.abs(ny) < 5) ny = 0;
        if (Math.abs(nx + w - width) < 5) nx = width - w;
        if (Math.abs(ny + h - height) < 5) ny = height - h;
        dragging.setPosition(nx, ny);
        return true;
    }

    @Override
    public boolean mouseReleased(MouseButtonEvent e) {
        if (dragging != null) { dragging = null; ConfigManager.markDirty(); return true; }
        return super.mouseReleased(e);
    }

    @Override
    public boolean mouseScrolled(double mx, double my, double hx, double vy) {
        HudModule m = at((int) mx, (int) my);
        if (m == null) return false;
        m.scale.set(m.scale.get() + (vy > 0 ? 0.05 : -0.05));
        ConfigManager.markDirty();
        return true;
    }

    @Override
    public boolean keyPressed(KeyEvent e) {
        if (e.key() == GLFW.GLFW_KEY_ESCAPE) { onClose(); return true; }
        return super.keyPressed(e);
    }

    private HudModule at(int mx, int my) {
        HudModule best = null;
        for (HudModule m : ModuleRegistry.hudModules()) {
            if (!m.isEnabled()) continue;
            if (mx >= m.x() && mx < m.x() + m.scaledWidth() && my >= m.y() && my < m.y() + m.scaledHeight()) best = m;
        }
        return best;
    }

    @Override public void onClose() { ConfigManager.save(); minecraft.setScreen(parent); }
    @Override public boolean isPauseScreen() { return false; }
}
