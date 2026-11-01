package ruruka.suka.rurukasuka.ui;

import net.minecraft.client.gui.GuiGraphics;

/** Мелкие HUD-детали в тактическом стиле: угловые скобки-рамки. */
public final class Hud {

    /** Рисует L-образные скобки по углам прямоугольника. */
    public static void bracket(GuiGraphics g, int x1, int y1, int x2, int y2, int len, int color) {
        // верх-лево
        g.fill(x1, y1, x1 + len, y1 + 1, color);
        g.fill(x1, y1, x1 + 1, y1 + len, color);
        // верх-право
        g.fill(x2 - len, y1, x2, y1 + 1, color);
        g.fill(x2 - 1, y1, x2, y1 + len, color);
        // низ-лево
        g.fill(x1, y2 - 1, x1 + len, y2, color);
        g.fill(x1, y2 - len, x1 + 1, y2, color);
        // низ-право
        g.fill(x2 - len, y2 - 1, x2, y2, color);
        g.fill(x2 - 1, y2 - len, x2, y2, color);
    }

    private Hud() {}

    /** Тонкая рамка 1px (стиль Minecraft/Essential). */
    public static void border(GuiGraphics g, int x1, int y1, int x2, int y2, int color) {
        g.fill(x1, y1, x2, y1 + 1, color);
        g.fill(x1, y2 - 1, x2, y2, color);
        g.fill(x1, y1, x1 + 1, y2, color);
        g.fill(x2 - 1, y1, x2, y2, color);
    }

}
