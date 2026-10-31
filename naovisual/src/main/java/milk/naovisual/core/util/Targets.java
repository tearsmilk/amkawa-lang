package milk.naovisual.core.util;

import net.minecraft.client.Minecraft;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;

/** Текущая цель: последняя атакованная сущность, пока она жива и рядом; иначе — сущность под прицелом. */
public final class Targets {
    private static LivingEntity last;
    private static long lastAttackAt;
    private static LivingEntity lastKilled;
    private static long lastKillAt;

    private Targets() {}

    public static void onAttack(Entity e) {
        if (e instanceof LivingEntity le && e != Minecraft.getInstance().player) {
            last = le;
            lastAttackAt = System.currentTimeMillis();
        }
    }

    public static void tick() {
        Minecraft mc = Minecraft.getInstance();
        if (last != null) {
            if (!last.isAlive() || last.isRemoved()) {
                if (last.getHealth() <= 0 || last.isDeadOrDying()) { lastKilled = last; lastKillAt = System.currentTimeMillis(); }
                last = null;
            } else if (mc.player == null || mc.player.distanceTo(last) > 32 || System.currentTimeMillis() - lastAttackAt > 6000) {
                last = null;
            }
        }
    }

    /** Цель для HUD/рендера или null. */
    public static LivingEntity current() {
        Minecraft mc = Minecraft.getInstance();
        if (mc.player == null) return null;
        if (last != null && last.isAlive()) return last;
        if (mc.crosshairPickEntity instanceof LivingEntity le && le != mc.player && le.isAlive()) return le;
        return null;
    }

    public static LivingEntity lastAttacked() { return last; }
    public static long lastAttackAt() { return lastAttackAt; }

    /** Убитая цель за последние ms миллисекунд. */
    public static LivingEntity recentKill(long ms) {
        return lastKilled != null && System.currentTimeMillis() - lastKillAt < ms ? lastKilled : null;
    }

    public static void consumeKill() { lastKilled = null; }

    public static boolean isPlayer(Entity e) { return e instanceof Player; }

    public static void reset() { last = null; lastKilled = null; }
}
