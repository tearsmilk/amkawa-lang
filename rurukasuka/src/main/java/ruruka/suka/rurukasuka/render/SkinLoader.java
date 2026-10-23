package ruruka.suka.rurukasuka.render;

import com.mojang.blaze3d.platform.NativeImage;
import ruruka.suka.rurukasuka.RurukaSuka;
import ruruka.suka.rurukasuka.net.SiteApi;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.texture.DynamicTexture;
import net.minecraft.client.resources.DefaultPlayerSkin;
import net.minecraft.core.ClientAsset;
import net.minecraft.resources.Identifier;
import net.minecraft.world.entity.player.PlayerModelType;
import net.minecraft.world.entity.player.PlayerSkin;

import java.io.ByteArrayInputStream;

/**
 * Грузит скин игрока с сайта и строит из него PlayerSkin (пайплайн текстур 1.21.11:
 * NativeImage -> DynamicTexture -> ClientAsset.Texture -> PlayerSkin.insecure).
 * Всё в try/catch: при любой ошибке остаётся дефолтный Стив, экран не падает.
 */
public final class SkinLoader {
    private static final Identifier TEX_ID =
            Identifier.fromNamespaceAndPath("rurukasuka", "site_skin");

    private static volatile PlayerSkin custom = null;
    private static volatile String loadedUrl = null;
    private static volatile String loadedModel = null;

    public static PlayerSkin currentOrDefault() {
        return custom != null ? custom : DefaultPlayerSkin.getDefaultSkin();
    }

    public static void reset() {
        custom = null;
        loadedUrl = null;
        loadedModel = null;
    }

    public static void loadFrom(String fullUrl, String model) {
        if (fullUrl == null) { reset(); return; }
        final String type = model == null ? "wide" : model;
        if (fullUrl.equals(loadedUrl) && type.equals(loadedModel) && custom != null) return;
        loadedUrl = fullUrl;
        loadedModel = type;
        new Thread(() -> {
            try {
                byte[] bytes = SiteApi.download(fullUrl);
                Minecraft.getInstance().execute(() -> {
                    try {
                        NativeImage img = NativeImage.read(new ByteArrayInputStream(bytes));
                        Minecraft.getInstance().getTextureManager()
                                .register(TEX_ID, new DynamicTexture(() -> "rurukasuka_site_skin", img));
                        ClientAsset.Texture asset = new ClientAsset.ResourceTexture(TEX_ID, TEX_ID);
                        PlayerModelType pmt = "slim".equalsIgnoreCase(type)
                                ? PlayerModelType.SLIM : PlayerModelType.WIDE;
                        custom = PlayerSkin.insecure(asset, null, null, pmt);
                    } catch (Throwable t) {
                        RurukaSuka.LOGGER.error("RurukaSuka: build site skin failed", t);
                    }
                });
            } catch (Exception e) {
                RurukaSuka.LOGGER.error("RurukaSuka: download site skin failed", e);
            }
        }, "RurukaSuka-skin").start();
    }

    private SkinLoader() {}
}
