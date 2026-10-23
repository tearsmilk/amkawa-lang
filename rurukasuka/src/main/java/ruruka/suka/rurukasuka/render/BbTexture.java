package ruruka.suka.rurukasuka.render;

import com.mojang.blaze3d.platform.NativeImage;
import ruruka.suka.rurukasuka.RurukaSuka;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.texture.DynamicTexture;
import net.minecraft.resources.Identifier;

import java.io.ByteArrayInputStream;
import java.util.Base64;

/**
 * Регистрирует текстуру косметики из base64 (.bbmodel) в TextureManager и отдаёт Identifier.
 * Вызывать на рендер-потоке (Minecraft.execute).
 */
public final class BbTexture {

    public static Identifier register(String base64, String name) {
        try {
            byte[] bytes = Base64.getDecoder().decode(base64);
            NativeImage img = NativeImage.read(new ByteArrayInputStream(bytes));
            Identifier id = Identifier.fromNamespaceAndPath("rurukasuka", "cosmetic/" + name);
            Minecraft.getInstance().getTextureManager()
                    .register(id, new DynamicTexture(() -> "rurukasuka_cosmetic_" + name, img));
            return id;
        } catch (Exception e) {
            RurukaSuka.LOGGER.error("RurukaSuka: cosmetic texture load failed", e);
            return null;
        }
    }

    private BbTexture() {}
}
