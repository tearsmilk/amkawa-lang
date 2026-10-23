package ruruka.suka.rurukasuka.ui;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.narration.NarrationElementOutput;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.network.chat.Component;

/** Кастомная кнопка без ванильной плашки — только текст. Наследник AbstractWidget. */
public class TextButton extends AbstractWidget {

    @FunctionalInterface
    public interface OnPress { void onPress(TextButton button); }

    private final OnPress onPress;
    private boolean selected = false;
    private boolean centered = false;
    private int baseColor = Palette.MUTED;

    public TextButton(int x, int y, int width, int height, Component message, OnPress onPress) {
        super(x, y, width, height, message);
        this.onPress = onPress;
    }

    public TextButton centered() { this.centered = true; return this; }
    public TextButton base(int color) { this.baseColor = color; return this; }
    public void setSelected(boolean selected) { this.selected = selected; }

    @Override
    protected void renderWidget(GuiGraphics g, int mouseX, int mouseY, float partialTick) {
        var font = Minecraft.getInstance().font;
        boolean hover = isHoveredOrFocused();
        int color = selected ? Palette.ACCENT_2 : (hover ? Palette.TEXT : baseColor);
        if (selected) {
            g.fill(getX() - 8, getY() + 1, getX() - 5, getY() + getHeight() - 1, Palette.ACCENT_2);
        }
        int ty = getY() + (getHeight() - 8) / 2;
        if (centered) {
            g.drawCenteredString(font, getMessage(), getX() + getWidth() / 2, ty, color);
        } else {
            g.drawString(font, getMessage(), getX(), ty, color);
        }
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
