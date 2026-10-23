package ruruka.suka.rurukasuka.render.gui;

import ruruka.suka.rurukasuka.cosmetic.CosmeticCategory;
import ruruka.suka.rurukasuka.render.BbModel;
import net.minecraft.client.gui.navigation.ScreenRectangle;
import net.minecraft.client.gui.render.state.pip.PictureInPictureRenderState;
import net.minecraft.client.model.player.PlayerModel;
import net.minecraft.resources.Identifier;

import java.util.List;

/** PIP-состояние: модель игрока + надетая/примеряемая косметика (для превью в гардеробе). */
public record PlayerCosmeticGuiRenderState(String key, PlayerModel playerModel, Identifier skin,
                                           float rotationX, float rotationY,
                                           int x0, int y0, int x1, int y1, float scale,
                                           List<Piece> pieces,
                                           ScreenRectangle scissorArea, ScreenRectangle bounds)
        implements PictureInPictureRenderState {

    public record Piece(BbModel model, Identifier texture, CosmeticCategory category,
                        float scale, float offX, float offY, float offZ) {}

    public PlayerCosmeticGuiRenderState(String key, PlayerModel playerModel, Identifier skin,
                                        float rotationX, float rotationY, int x0, int y0, int x1, int y1,
                                        float scale, List<Piece> pieces, ScreenRectangle scissorArea) {
        this(key, playerModel, skin, rotationX, rotationY, x0, y0, x1, y1, scale, pieces, scissorArea,
                PictureInPictureRenderState.getBounds(x0, y0, x1, y1, scissorArea));
    }
}
