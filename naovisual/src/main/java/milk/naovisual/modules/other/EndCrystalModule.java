package milk.naovisual.modules.other;

import com.mojang.blaze3d.vertex.PoseStack;
import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.NumberSetting;
import net.minecraft.client.renderer.entity.state.EndCrystalRenderState;

/** Размер и подпрыгивание эндер-кристаллов. */
public class EndCrystalModule extends Module {
    private final NumberSetting scale = add(new NumberSetting("Размер", "", 0.7, 0.2, 2.0, 0.05, "×"));
    private final BooleanSetting bounce = add(new BooleanSetting("Подпрыгивание", "", true));
    private final NumberSetting bounceHeight = add(new NumberSetting("Высота", "", 0.2, 0.0, 1.0, 0.05).visibleWhen(bounce::on));

    public EndCrystalModule() {
        super("EndCrystal", "Кристаллы", "Размер и анимация эндер-кристаллов", ModuleCategory.OTHER);
    }

    public void transform(EndCrystalRenderState state, PoseStack ps) {
        float s = scale.getFloat();
        float b = bounce.on() ? (float) Math.sin((state.ageInTicks) * 0.25f) * bounceHeight.getFloat() : 0f;
        ps.translate(0f, b + (1f - s) * 0.5f, 0f);
        ps.scale(s, s, s);
    }
}
