package ruruka.suka.rurukasuka.cosmetic;

import java.util.List;

/** Косметика из каталога сайта. variants — цветовые варианты текстуры. */
public record Cosmetic(int id, String name, CosmeticCategory category, int price,
                       float scale, float offX, float offY, float offZ,
                       List<Variant> variants) {

    public record Variant(int id, String name, String textureUrl) {}
}
