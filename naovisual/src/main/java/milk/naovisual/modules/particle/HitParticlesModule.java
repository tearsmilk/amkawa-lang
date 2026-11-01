package milk.naovisual.modules.particle;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.particle.ParticleSystem;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.util.ColorUtil;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;

import java.util.Random;

/** Частицы при ударе: сердечки, искры, осколки — с физикой и отскоком. */
public class HitParticlesModule extends Module {
    private final SelectSetting shape = add(new SelectSetting("Форма", "", "Искры", "Искры", "Сердечки", "Осколки", "Звёзды"));
    private final NumberSetting amount = add(new NumberSetting("Количество", "", 16, 1, 80, 1));
    private final NumberSetting size = add(new NumberSetting("Размер", "", 0.12, 0.03, 0.5, 0.01));
    private final NumberSetting power = add(new NumberSetting("Разлёт", "", 0.25, 0.05, 1.0, 0.05));
    private final BooleanSetting collide = add(new BooleanSetting("Столкновения", "Отскок от блоков", true));
    private final BooleanSetting onDamage = add(new BooleanSetting("На получении урона", "Частицы и когда бьют вас", true));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xFFD97757));
    private final ColorSetting color2 = add(new ColorSetting("Второй цвет", "", 0xFFE8B84A));
    private final Random rng = new Random();

    public HitParticlesModule() {
        super("HitParticles", "Частицы удара", "Искры, сердечки или осколки от цели при ударе", ModuleCategory.PARTICLES);
        color.setMode(ColorSetting.Mode.THEME);
    }

    @Override public boolean defaultEnabled() { return true; }

    @Override public void onAttack(Entity e) { burst(e); }

    @Override
    public void onDamage(LivingEntity e) {
        if (onDamage.on() && e == mc().player) burst(e);
    }

    private void burst(Entity e) {
        ParticleSystem.Shape sh = switch (shape.get()) {
            case "Сердечки" -> ParticleSystem.Shape.HEART;
            case "Осколки" -> ParticleSystem.Shape.DIAMOND;
            case "Звёзды" -> ParticleSystem.Shape.STAR;
            default -> ParticleSystem.Shape.SQUARE;
        };
        double cx = e.getX(), cy = e.getY() + e.getBbHeight() * 0.6, cz = e.getZ();
        for (int i = 0; i < amount.getInt(); i++) {
            double ang = rng.nextDouble() * Math.PI * 2, pitch = (rng.nextDouble() - 0.3) * Math.PI;
            double pw = power.get() * (0.5 + rng.nextDouble());
            double vx = Math.cos(ang) * Math.cos(pitch) * pw, vy = Math.sin(pitch) * pw * 0.8 + 0.1, vz = Math.sin(ang) * Math.cos(pitch) * pw;
            int c = ColorUtil.lerp(color.color(), color2.color(), rng.nextFloat());
            var p = ParticleSystem.spawn(cx, cy, cz, vx, vy, vz, (float) (size.get() * (0.6 + rng.nextDouble() * 0.8)), c, 30 + rng.nextInt(30), sh);
            p.collide = collide.on();
            p.gravity = sh == ParticleSystem.Shape.HEART ? 0.005f : 0.03f;
            p.drag = 0.96f;
        }
    }
}
