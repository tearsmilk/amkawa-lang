package ruruka.suka.rurukasuka.render.gui;

import ruruka.suka.rurukasuka.render.BbModel;
import net.minecraft.client.gui.navigation.ScreenRectangle;
import net.minecraft.client.gui.render.state.pip.PictureInPictureRenderState;
import net.minecraft.resources.Identifier;

/** PIP-состояние косметики. key — уникальный ключ кэша текстуры (id + вариант). */
public record CosmeticGuiRenderState(String key, BbModel model, Identifier texture,
                                     float rotationX, float rotationY, float pivotY,
                                     int x0, int y0, int x1, int y1, float scale,
                                     ScreenRectangle scissorArea, ScreenRectangle bounds)
        implements PictureInPictureRenderState {

    public CosmeticGuiRenderState(String key, BbModel model, Identifier texture, float rotationX, float rotationY,
                                  float pivotY, int x0, int y0, int x1, int y1, float scale,
                                  ScreenRectangle scissorArea) {
        this(key, model, texture, rotationX, rotationY, pivotY, x0, y0, x1, y1, scale, scissorArea,
                PictureInPictureRenderState.getBounds(x0, y0, x1, y1, scissorArea));
    }
}
