package milk.naovisual.modules.world;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.util.ColorUtil;
import net.minecraft.client.renderer.fog.FogData;
import org.joml.Vector4f;

/** Туман: своя дистанция начала/конца и цвет. */
public class FogModule extends Module {
    private final NumberSetting start = add(new NumberSetting("Начало", "Доля дальности прорисовки", 0.2, 0.0, 1.0, 0.01));
    private final NumberSetting end = add(new NumberSetting("Конец", "Доля дальности прорисовки", 0.8, 0.05, 2.0, 0.01));
    private final BooleanSetting customColor = add(new BooleanSetting("Свой цвет", "", false));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xFFD9CFC2, false).visibleWhen(customColor::on));
    private final NumberSetting blend = add(new NumberSetting("Смешивание", "Насколько свой цвет перекрывает цвет неба", 0.7, 0.0, 1.0, 0.05).visibleWhen(customColor::on));

    public FogModule() {
        super("Fog", "Туман", "Дистанция и цвет тумана", ModuleCategory.WORLD);
    }

    public void apply(FogData data, float viewDistance) {
        float s = (float) (viewDistance * start.get()), e = (float) (viewDistance * end.get());
        if (e <= s) e = s + 1f;
        data.environmentalStart = s;
        data.environmentalEnd = e;
        data.renderDistanceStart = s;
        data.renderDistanceEnd = e;
        data.skyEnd = Math.max(data.skyEnd, e);
        data.cloudEnd = Math.max(data.cloudEnd, e);
    }

    public void applyColor(Vector4f c) {
        if (!customColor.on()) return;
        int col = color.color();
        float f = blend.getFloat();
        c.x = c.x + (ColorUtil.red(col) / 255f - c.x) * f;
        c.y = c.y + (ColorUtil.green(col) / 255f - c.y) * f;
        c.z = c.z + (ColorUtil.blue(col) / 255f - c.z) * f;
    }
}
