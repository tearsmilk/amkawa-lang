package milk.naovisual.modules.particle;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.particle.ParticleSystem;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import net.minecraft.world.entity.Entity;

import java.util.Random;

/** Пузыри, разлетающиеся от цели при ударе. */
public class HitBubblesModule extends Module {
    private final NumberSetting amount = add(new NumberSetting("Количество", "", 12, 1, 60, 1));
    private final NumberSetting size = add(new NumberSetting("Размер", "", 0.15, 0.05, 0.6, 0.01));
    private final NumberSetting life = add(new NumberSetting("Время жизни", "Тиков", 40, 10, 120, 1));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xB04FB3D9));
    private final Random rng = new Random();

    public HitBubblesModule() {
        super("HitBubbles", "Пузыри удара", "Пузыри, всплывающие от цели при попадании", ModuleCategory.PARTICLES);
    }

    @Override
    public void onAttack(Entity e) {
        for (int i = 0; i < amount.getInt(); i++) {
            double x = e.getX() + (rng.nextDouble() - 0.5) * e.getBbWidth(), z = e.getZ() + (rng.nextDouble() - 0.5) * e.getBbWidth();
            double y = e.getY() + rng.nextDouble() * e.getBbHeight();
            var p = ParticleSystem.spawn(x, y, z, (rng.nextDouble() - 0.5) * 0.08, rng.nextDouble() * 0.06 + 0.02, (rng.nextDouble() - 0.5) * 0.08,
                    (float) (size.get() * (0.6 + rng.nextDouble() * 0.8)), color.color(), life.getInt(), ParticleSystem.Shape.BUBBLE);
            p.gravity = -0.002f; p.drag = 0.95f;
        }
    }
}
