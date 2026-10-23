package ruruka.suka.rurukasuka.ui;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.PlayerSkinWidget;
import net.minecraft.client.input.MouseButtonEvent;
import ruruka.suka.rurukasuka.render.SkinLoader;

/**
 * Фабрика превью игрока на базе ванильного PlayerSkinWidget (3D-модель по скину без мира,
 * вращение мышкой встроено). Скин Стива, вращение замедлено относительно ванили.
 * Тип PlayerSkin намеренно не называем — метод-ссылка подставляется в super() по месту.
 */
public final class PlayerPreview {

    /** Во сколько раз медленнее крутить, чем в ванили. */
    private static final double ROTATION_SLOWDOWN = 2.4;

    public static PlayerSkinWidget widget(int width, int height) {
        return new SlowSkinWidget(width, height);
    }

    private static final class SlowSkinWidget extends PlayerSkinWidget {
        SlowSkinWidget(int width, int height) {
            super(width, height,
                    Minecraft.getInstance().getEntityModels(),
                    SkinLoader::currentOrDefault);
        }

        @Override
        protected void onDrag(MouseButtonEvent event, double dragX, double dragY) {
            super.onDrag(event, dragX / ROTATION_SLOWDOWN, dragY / ROTATION_SLOWDOWN);
        }
    }

    private PlayerPreview() {}
}
