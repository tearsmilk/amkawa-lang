package ruruka.suka.rurukasuka.render;

import ruruka.suka.rurukasuka.RurukaSuka;
import ruruka.suka.rurukasuka.account.RurukaAccount;
import ruruka.suka.rurukasuka.cosmetic.Cosmetic;
import ruruka.suka.rurukasuka.cosmetic.CosmeticCategory;
import ruruka.suka.rurukasuka.cosmetic.CosmeticRegistry;
import ruruka.suka.rurukasuka.net.SiteApi;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.Identifier;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/** Кэш собранной косметики + фоновое обновление каталога (real-time трансформ). */
public final class CosmeticManager {
    private static final Map<Integer, BakedCosmetic> CACHE = new ConcurrentHashMap<>();
    private static final Set<Integer> LOADING = ConcurrentHashMap.newKeySet();
    private static volatile boolean pollerStarted = false;

    public static BakedCosmetic get(int id) { return CACHE.get(id); }

    /** Живой трансформ (масштаб + смещение) из свежего каталога. */
    public static float[] transformOf(int id) {
        for (Cosmetic c : CosmeticRegistry.all())
            if (c.id() == id) return new float[]{c.scale(), c.offX(), c.offY(), c.offZ()};
        return new float[]{1f, 0f, 0f, 0f};
    }

    public static void ensure(int id) {
        if (CACHE.containsKey(id) || LOADING.contains(id)) return;
        Cosmetic cos = cosmeticOf(id);
        if (cos == null) return;
        LOADING.add(id);
        new Thread(() -> {
            try {
                byte[] bytes = SiteApi.download(RurukaSuka.SITE_URL + "/api/cosmetics/" + id + "/model");
                BbModel bb = BbParser.parse(new String(bytes, StandardCharsets.UTF_8));
                Minecraft.getInstance().execute(() -> {
                    try {
                        var tex = bb.textureBase64 != null ? BbTexture.register(bb.textureBase64, "c" + id) : null;
                        CACHE.put(id, new BakedCosmetic(bb, tex, cos.category()));
                    } catch (Throwable t) {
                        RurukaSuka.LOGGER.error("RurukaSuka: prepare cosmetic {} failed", id, t);
                    } finally {
                        LOADING.remove(id);
                    }
                });
            } catch (Exception e) {
                RurukaSuka.LOGGER.error("RurukaSuka: load cosmetic {} failed", id, e);
                LOADING.remove(id);
            }
        }, "RurukaSuka-cosmetic-" + id).start();
    }

    /** Фоновый опрос каталога — обновляет трансформы/новые модели без перезапуска игры. */
    public static void startPoller() {
        if (pollerStarted) return;
        pollerStarted = true;
        Thread t = new Thread(() -> {
            while (true) {
                try {
                    var list = SiteApi.cosmetics().stream()
                            .map(it -> new Cosmetic(it.id(), it.name(),
                                    CosmeticCategory.fromApi(it.category()), it.price(),
                                    it.scale(), it.offX(), it.offY(), it.offZ(), it.variants()))
                            .toList();
                    Minecraft.getInstance().execute(() -> CosmeticRegistry.load(list));
                } catch (Exception ignored) {}
                try { Thread.sleep(4000); } catch (InterruptedException e) { return; }
            }
        }, "RurukaSuka-catalog-poller");
        t.setDaemon(true);
        t.start();
    }

    private static final Map<Integer, Identifier> VARIANT_TEX = new ConcurrentHashMap<>();
    private static final Set<Integer> VARIANT_LOADING = ConcurrentHashMap.newKeySet();

    /** Текстура для рендера: выбранный вариант-цвет, иначе базовая текстура модели. */
    public static Identifier textureFor(int cosmeticId) {
        int vid = RurukaAccount.LOCAL.variantOf(cosmeticId);
        if (vid > 0) {
            ensureVariant(vid, cosmeticId);
            Identifier t = VARIANT_TEX.get(vid);
            if (t != null) return t;
        }
        BakedCosmetic b = CACHE.get(cosmeticId);
        return b != null ? b.texture() : null;
    }

    private static void ensureVariant(int variantId, int cosmeticId) {
        if (VARIANT_TEX.containsKey(variantId) || VARIANT_LOADING.contains(variantId)) return;
        String url = variantUrl(cosmeticId, variantId);
        if (url == null) return;
        VARIANT_LOADING.add(variantId);
        new Thread(() -> {
            try {
                byte[] png = SiteApi.download(RurukaSuka.abs(url));
                Minecraft.getInstance().execute(() -> {
                    try {
                        var img = com.mojang.blaze3d.platform.NativeImage.read(new java.io.ByteArrayInputStream(png));
                        Identifier id = Identifier.fromNamespaceAndPath("rurukasuka", "variant/" + variantId);
                        Minecraft.getInstance().getTextureManager().register(id,
                                new net.minecraft.client.renderer.texture.DynamicTexture(() -> "rurukasuka_variant_" + variantId, img));
                        VARIANT_TEX.put(variantId, id);
                    } catch (Throwable t) {
                        RurukaSuka.LOGGER.error("RurukaSuka: variant texture {} failed", variantId, t);
                    } finally {
                        VARIANT_LOADING.remove(variantId);
                    }
                });
            } catch (Exception e) {
                RurukaSuka.LOGGER.error("RurukaSuka: variant download {} failed", variantId, e);
                VARIANT_LOADING.remove(variantId);
            }
        }, "RurukaSuka-variant-" + variantId).start();
    }

    private static String variantUrl(int cosmeticId, int variantId) {
        for (Cosmetic c : CosmeticRegistry.all())
            if (c.id() == cosmeticId)
                for (Cosmetic.Variant v : c.variants())
                    if (v.id() == variantId) return v.textureUrl();
        return null;
    }

    private static Cosmetic cosmeticOf(int id) {
        for (Cosmetic c : CosmeticRegistry.all()) if (c.id() == id) return c;
        return null;
    }

    private CosmeticManager() {}
}
