package milk.naovisual.modules.particle;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.particle.ParticleSystem;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.util.ColorUtil;

import java.util.Random;

/** Атмосферные частицы вокруг игрока: светлячки, лепестки, снег, звёзды. */
public class AmbientParticlesModule extends Module {
    private final SelectSetting type = add(new SelectSetting("Тип", "", "Светлячки", "Светлячки", "Лепестки", "Снег", "Звёзды"));
    private final NumberSetting amount = add(new NumberSetting("Количество", "Частиц в секунду", 6, 1, 40, 1));
    private final NumberSetting radius = add(new NumberSetting("Радиус", "", 10, 3, 30, 1, " бл"));
    private final NumberSetting size = add(new NumberSetting("Размер", "", 0.12, 0.03, 0.5, 0.01));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xDDE8B84A));
    private final Random rng = new Random();
    private double acc;

    public AmbientParticlesModule() {
        super("AmbientParticles", "Атмосфера", "Светлячки, лепестки или снег вокруг игрока", ModuleCategory.PARTICLES);
    }

    @Override
    public void onTick() {
        var p = mc().player;
        if (p == null) return;
        acc += amount.get() / 20.0;
        while (acc >= 1) {
            acc -= 1;
            double r = radius.get();
            double x = p.getX() + (rng.nextDouble() * 2 - 1) * r, z = p.getZ() + (rng.nextDouble() * 2 - 1) * r;
            double y = p.getY() + rng.nextDouble() * 6 - 1;
            int c = color.mode() == ColorSetting.Mode.CUSTOM && type.is("Лепестки") ? ColorUtil.lerp(0xDDE88AA8, 0xDDFFFFFF, rng.nextFloat()) : color.color();
            switch (type.get()) {
                case "Лепестки" -> {
                    var pt = ParticleSystem.spawn(x, y + 4, z, (rng.nextDouble() - 0.5) * 0.04, -0.03, (rng.nextDouble() - 0.5) * 0.04, size.getFloat() * 1.3f, c, 160, ParticleSystem.Shape.DIAMOND);
                    pt.gravity = 0.0005f; pt.drag = 0.995f;
                }
                case "Снег" -> {
                    var pt = ParticleSystem.spawn(x, y + 5, z, (rng.nextDouble() - 0.5) * 0.02, -0.04, (rng.nextDouble() - 0.5) * 0.02, size.getFloat(), ColorUtil.withAlpha(0xFFFFFFFF, 220), 200, ParticleSystem.Shape.SQUARE);
                    pt.gravity = 0.0003f; pt.drag = 0.999f;
                }
                case "Звёзды" -> {
                    var pt = ParticleSystem.spawn(x, y + 1, z, 0, 0.002, 0, size.getFloat(), c, 90, ParticleSystem.Shape.STAR);
                    pt.gravity = 0f; pt.drag = 1f;
                }
                default -> {
                    var pt = ParticleSystem.spawn(x, y, z, (rng.nextDouble() - 0.5) * 0.02, (rng.nextDouble() - 0.4) * 0.01, (rng.nextDouble() - 0.5) * 0.02, size.getFloat(), c, 120, ParticleSystem.Shape.BUBBLE);
                    pt.gravity = 0f; pt.drag = 0.99f;
                }
            }
        }
    }
}
