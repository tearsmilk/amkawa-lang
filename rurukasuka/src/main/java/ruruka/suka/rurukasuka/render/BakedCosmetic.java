package ruruka.suka.rurukasuka.render;

import ruruka.suka.rurukasuka.cosmetic.CosmeticCategory;
import net.minecraft.resources.Identifier;

public record BakedCosmetic(BbModel model, Identifier texture, CosmeticCategory category) {}
