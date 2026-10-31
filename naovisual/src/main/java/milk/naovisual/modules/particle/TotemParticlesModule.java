package milk.naovisual.modules.particle;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.particle.ParticleSystem;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.util.ColorUtil;
import net.minecraft.world.entity.LivingEntity;

import java.util.Random;

/** Взрыв частиц при срабатывании тотема. */
public class TotemParticlesModule extends Module {
    private final SelectSetting shape = add(new SelectSetting("Форма", "", "Звёзды", "Звёзды", "Квадраты", "Сердечки"));
    private final NumberSetting amount = add(new NumberSetting("Количество", "", 60, 10, 200, 5));
    private final NumberSetting size = add(new NumberSetting("Размер", "", 0.15, 0.05, 0.5, 0.01));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xFF5FB36A));
    private final ColorSetting color2 = add(new ColorSetting("Второй цвет", "", 0xFFE8B84A));
    private final Random rng = new Random();

    public TotemParticlesModule() {
        super("TotemParticles", "Частицы тотема", "Салют из частиц, когда у кого-то срабатывает тотем", ModuleCategory.PARTICLES);
    }

    @Override
    public void onTotemPop(LivingEntity e) {
        ParticleSystem.Shape sh = switch (shape.get()) {
            case "Квадраты" -> ParticleSystem.Shape.SQUARE;
            case "Сердечки" -> ParticleSystem.Shape.HEART;
            default -> ParticleSystem.Shape.STAR;
        };
        double cx = e.getX(), cy = e.getY() + e.getBbHeight() * 0.7, cz = e.getZ();
        for (int i = 0; i < amount.getInt(); i++) {
            double ang = rng.nextDouble() * Math.PI * 2, pitch = rng.nextDouble() * Math.PI - Math.PI / 2;
            double pw = 0.15 + rng.nextDouble() * 0.35;
            int c = ColorUtil.lerp(color.color(), color2.color(), rng.nextFloat());
            var p = ParticleSystem.spawn(cx, cy, cz, Math.cos(ang) * Math.cos(pitch) * pw, Math.sin(pitch) * pw + 0.15, Math.sin(ang) * Math.cos(pitch) * pw,
                    (float) (size.get() * (0.5 + rng.nextDouble())), c, 40 + rng.nextInt(40), sh);
            p.gravity = 0.012f; p.drag = 0.95f; p.collide = true;
        }
    }
}
