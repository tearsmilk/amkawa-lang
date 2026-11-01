package milk.naovisual.modules.other;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.NumberSetting;
import org.joml.Matrix4f;

/** Растяжение картинки по горизонтали (как игра в 4:3 на широком экране). */
public class AspectRatioModule extends Module {
    private final NumberSetting stretch = add(new NumberSetting("Растяжение", "1 — без изменений, больше — шире", 1.33, 0.5, 2.0, 0.01));

    public AspectRatioModule() {
        super("AspectRatio", "Соотношение сторон", "Растягивает изображение мира по горизонтали", ModuleCategory.OTHER);
    }

    public void apply(Matrix4f projection) {
        if (projection == null) return;
        projection.scaleLocal(1f / stretch.getFloat(), 1f, 1f);
    }
}
