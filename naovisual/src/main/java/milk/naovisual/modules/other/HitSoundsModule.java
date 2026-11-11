package milk.naovisual.modules.other;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.setting.SelectSetting;
import net.minecraft.client.resources.sounds.SimpleSoundInstance;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;

/** Звук при попадании по сущности и при убийстве. */
public class HitSoundsModule extends Module {
    private final SelectSetting sound = add(new SelectSetting("Звук", "", "Опыт", "Опыт", "Крит", "Колокол", "Аметист", "Наковальня", "Нота", "Стрела"));
    private final NumberSetting volume = add(new NumberSetting("Громкость", "", 0.8, 0.1, 2.0, 0.05));
    private final NumberSetting pitch = add(new NumberSetting("Высота", "", 1.0, 0.5, 2.0, 0.05));
    private final BooleanSetting onlyLiving = add(new BooleanSetting("Только существа", "", true));
    private final BooleanSetting critPitch = add(new BooleanSetting("Выше при крите", "Прыжковый удар звучит выше", true));

    public HitSoundsModule() {
        super("HitSounds", "Звук удара", "Проигрывает звук при попадании по сущности", ModuleCategory.OTHER);
    }

    @Override
    public void onAttack(Entity e) {
        if (onlyLiving.on() && !(e instanceof LivingEntity)) return;
        var p = mc().player;
        boolean crit = critPitch.on() && p != null && p.fallDistance > 0 && !p.onGround() && !p.isInWater();
        float pt = pitch.getFloat() * (crit ? 1.25f : 1f);
        mc().getSoundManager().play(SimpleSoundInstance.forUI(event(), pt, volume.getFloat()));
    }

    private SoundEvent event() {
        return switch (sound.get()) {
            case "Крит" -> SoundEvents.PLAYER_ATTACK_CRIT;
            case "Колокол" -> SoundEvents.BELL_BLOCK;
            case "Аметист" -> SoundEvents.AMETHYST_BLOCK_CHIME;
            case "Наковальня" -> SoundEvents.ANVIL_LAND;
            case "Нота" -> SoundEvents.NOTE_BLOCK_PLING.value();
            case "Стрела" -> SoundEvents.ARROW_HIT_PLAYER;
            default -> SoundEvents.EXPERIENCE_ORB_PICKUP;
        };
    }
}
