package milk.naovisual.modules.world;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.BooleanSetting;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;

/** Ночное зрение на стороне клиента: мягкое освещение без выжигания гаммы. */
public class LightModule extends Module {
    private final BooleanSetting hideIcon = add(new BooleanSetting("Скрыть иконку", "Не показывать эффект в списке зелий", true));
    private boolean applied;

    public LightModule() {
        super("Light", "Свет", "Мягкое ночное зрение только на клиенте", ModuleCategory.WORLD);
    }

    @Override
    public void onTick() {
        var p = mc().player;
        if (p == null) return;
        MobEffectInstance cur = p.getEffect(MobEffects.NIGHT_VISION);
        if (cur == null || cur.getDuration() < 300) {
            p.addEffect(new MobEffectInstance(MobEffects.NIGHT_VISION, 1200, 0, true, false, !hideIcon.on()));
            applied = true;
        }
    }

    @Override
    public void onDisable() {
        var p = mc().player;
        if (p != null && applied) p.removeEffect(MobEffects.NIGHT_VISION);
        applied = false;
    }

    @Override public void onDisconnect() { applied = false; }
}
