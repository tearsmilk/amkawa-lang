package milk.naovisual.core.render;

import com.mojang.blaze3d.platform.NativeImage;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.textures.FilterMode;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.texture.DynamicTexture;
import net.minecraft.resources.Identifier;

import java.util.HashMap;
import java.util.Map;

/** Сглаженные маски (диск, кольцо, мягкая тень), сгенерированные под реальный размер в пикселях экрана и
 *  закешированные. Рисуются белыми текстурами с тонировкой, поэтому края без ступенек и без щелей между частями. */
public final class Shapes {
    private Shapes() {}

    private static final Map<Long, Identifier> CACHE = new HashMap<>();
    private static int counter;

    private static final class Tex extends DynamicTexture {
        Tex(String name, NativeImage img) {
            super(() -> name, img);
            this.sampler = RenderSystem.getSamplerCache().getClampToEdge(FilterMode.LINEAR);
        }
    }

    /** Покрытие круга радиуса r в точке на расстоянии d от центра (антиалиасинг на один пиксель). */
    public static float coverage(float r, float d) {
        return Math.max(0f, Math.min(1f, r - d + 0.5f));
    }

    private static Identifier make(long key, String kind, int size, Mask mask) {
        Identifier id = CACHE.get(key);
        if (id != null) return id;
        NativeImage img = new NativeImage(size, size, false);
        float c = size / 2f;
        for (int y = 0; y < size; y++) {
            for (int x = 0; x < size; x++) {
                float d = (float) Math.hypot(x + 0.5f - c, y + 0.5f - c);
                int a = Math.round(255f * Math.max(0f, Math.min(1f, mask.alpha(d))));
                img.setPixel(x, y, (a << 24) | 0xFFFFFF);
            }
        }
        id = Identifier.fromNamespaceAndPath("naovisual", "shape/" + kind + "_" + (counter++));
        Minecraft.getInstance().getTextureManager().register(id, new Tex("naovisual " + kind, img));
        CACHE.put(key, id);
        return id;
    }

    private interface Mask { float alpha(float d); }

    /** Диск радиусом rPx (текстура 2·rPx). */
    public static Identifier disk(int rPx) {
        return make(((long) 1 << 40) | rPx, "disk", rPx * 2, d -> coverage(rPx, d));
    }

    /** Кольцо радиусом rPx и толщиной tPx. */
    public static Identifier ring(int rPx, int tPx) {
        return make(((long) 2 << 40) | ((long) tPx << 20) | rPx, "ring", rPx * 2,
                d -> coverage(rPx, d) - coverage(rPx - tPx, d));
    }

    /** Мягкая тень вокруг скругления радиуса rPx шириной sPx (внутри пусто). Текстура 2·(rPx+sPx). */
    public static Identifier shadow(int rPx, int sPx) {
        return make(((long) 3 << 40) | ((long) sPx << 20) | rPx, "shadow", (rPx + sPx) * 2, d -> {
            if (d <= rPx) return 0f;
            float t = 1f - (d - rPx) / Math.max(1f, sPx);
            return t <= 0 ? 0f : t * t;
        });
    }
}
