package ruruka.suka.rurukasuka.ui;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.narration.NarrationElementOutput;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.network.chat.Component;

/** Объёмная кнопка в стиле Minecraft (серая или вишнёвая). Устроена как TextButton. */
public class McButton extends AbstractWidget {

    @FunctionalInterface
    public interface OnPress { void onPress(McButton button); }

    private final OnPress onPress;
    private boolean cherry = false;

    public McButton(int x, int y, int width, int height, Component message, OnPress onPress) {
        super(x, y, width, height, message);
        this.onPress = onPress;
    }

    /** Вишнёвая — для главного действия на экране. */
    public McButton cherry() { this.cherry = true; return this; }

    @Override
    protected void renderWidget(GuiGraphics g, int mouseX, int mouseY, float partialTick) {
        var font = Minecraft.getInstance().font;
        boolean hover = isHoveredOrFocused();
        McGui.button(g, getX(), getY(), getX() + getWidth(), getY() + getHeight(), cherry, hover, this.active);
        String text = McGui.fit(font, getMessage().getString(), getWidth() - 8);
        int ty = getY() + (getHeight() - 8) / 2 - 1;
        g.drawCenteredString(font, Component.literal(text), getX() + getWidth() / 2, ty,
                this.active ? McGui.WHITE : 0xFFA0A0A0);
    }

    @Override
    public boolean mouseClicked(MouseButtonEvent event, boolean doubleClick) {
        if (!this.active || !this.visible || event.button() != 0) return false;
        double mx = event.x(), my = event.y();
        if (mx >= getX() && mx < getX() + getWidth() && my >= getY() && my < getY() + getHeight()) {
            playDownSound(Minecraft.getInstance().getSoundManager());
            onPress.onPress(this);
            return true;
        }
        return false;
    }

    @Override
    protected void updateWidgetNarration(NarrationElementOutput narration) {
        defaultButtonNarrationText(narration);
    }
}
