package milk.naovisual.core.util;

import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;

import java.util.HashMap;
import java.util.Map;

/** Определение критического удара на стороне клиента в момент атаки (условия как в Player.attack). */
public final class Crits {
    private Crits() {}

    private static final Map<Integer, Long> RECENT = new HashMap<>();

    public static boolean isCrit(Player p) {
        return p.getAttackStrengthScale(0.5f) > 0.9f && p.fallDistance > 0 && !p.onGround() && !p.onClimbable()
                && !p.isInWater() && !p.hasEffect(MobEffects.BLINDNESS) && !p.isPassenger() && !p.isSprinting();
    }

    public static void mark(Entity e) {
        if (RECENT.size() > 64) RECENT.clear();
        RECENT.put(e.getId(), System.currentTimeMillis());
    }

    /** Был ли крит по этой сущности за последние 0,7 с. */
    public static boolean recent(int entityId) {
        Long t = RECENT.get(entityId);
        return t != null && System.currentTimeMillis() - t < 700;
    }
}
