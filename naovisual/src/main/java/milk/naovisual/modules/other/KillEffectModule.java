package milk.naovisual.modules.other;

import milk.naovisual.core.hud.Notifications;
import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.particle.ParticleSystem;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.util.ColorUtil;
import milk.naovisual.core.util.Targets;
import net.minecraft.client.resources.sounds.SimpleSoundInstance;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;

import java.util.Random;

/** Эффект при убийстве цели: салют частиц, звук, уведомление, счётчик. */
public class KillEffectModule extends Module {
    private final SelectSetting effect = add(new SelectSetting("Эффект", "", "Салют", "Салют", "Молния", "Сердечки", "Нет"));
    private final BooleanSetting sound = add(new BooleanSetting("Звук", "", true));
    private final BooleanSetting notify = add(new BooleanSetting("Уведомление", "", true));
    private final BooleanSetting onlyPlayers = add(new BooleanSetting("Только игроки", "", true));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xFFD97757));
    private final Random rng = new Random();
    private int kills;

    public KillEffectModule() {
        super("KillEffect", "Эффект убийства", "Салют, звук и уведомление при убийстве цели", ModuleCategory.OTHER);
        color.setMode(ColorSetting.Mode.THEME);
    }

    @Override
    public void onTick() {
        LivingEntity k = Targets.recentKill(1000);
        if (k == null) return;
        Targets.consumeKill();
        if (onlyPlayers.on() && !(k instanceof Player)) return;
        kills++;
        double cx = k.getX(), cy = k.getY() + k.getBbHeight() * 0.5, cz = k.getZ();
        switch (effect.get()) {
            case "Салют" -> burst(cx, cy, cz, ParticleSystem.Shape.STAR, 80, 0.4);
            case "Сердечки" -> burst(cx, cy, cz, ParticleSystem.Shape.HEART, 40, 0.2);
            case "Молния" -> {
                for (int i = 0; i < 25; i++) {
                    var p = ParticleSystem.spawn(cx + (rng.nextDouble() - 0.5) * 0.3, cy + i * 0.5, cz + (rng.nextDouble() - 0.5) * 0.3, 0, 0, 0, 0.25f, ColorUtil.withAlpha(0xFFFFFFFF, 230), 12 + i, ParticleSystem.Shape.SQUARE);
                    p.gravity = 0; p.drag = 1;
                }
                if (sound.on()) mc().getSoundManager().play(SimpleSoundInstance.forUI(SoundEvents.LIGHTNING_BOLT_THUNDER, 1.2f, 0.4f));
            }
            default -> {}
        }
        if (sound.on() && !effect.is("Молния")) mc().getSoundManager().play(SimpleSoundInstance.forUI(SoundEvents.FIREWORK_ROCKET_BLAST, 1f, 0.8f));
        if (notify.on()) Notifications.push("Убийство", k.getDisplayName().getString() + "  •  всего " + kills, Notifications.Type.SUCCESS, 3000);
    }

    private void burst(double cx, double cy, double cz, ParticleSystem.Shape sh, int n, double power) {
        for (int i = 0; i < n; i++) {
            double ang = rng.nextDouble() * Math.PI * 2, pitch = rng.nextDouble() * Math.PI - Math.PI / 2;
            double pw = power * (0.4 + rng.nextDouble());
            int c = ColorUtil.lerp(color.color(), 0xFFFFFFFF, rng.nextFloat() * 0.5f);
            var p = ParticleSystem.spawn(cx, cy, cz, Math.cos(ang) * Math.cos(pitch) * pw, Math.sin(pitch) * pw + 0.1, Math.sin(ang) * Math.cos(pitch) * pw, 0.12f + rng.nextFloat() * 0.1f, c, 40 + rng.nextInt(40), sh);
            p.gravity = 0.01f; p.drag = 0.95f; p.collide = true;
        }
    }

    @Override public void onDisconnect() { kills = 0; }
}
