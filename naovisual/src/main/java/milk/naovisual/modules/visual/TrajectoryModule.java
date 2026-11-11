package milk.naovisual.modules.visual;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.render.Render3D;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.util.ColorUtil;
import milk.naovisual.core.util.TrajectoryMath;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderContext;
import net.minecraft.core.BlockPos;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.BowItem;
import net.minecraft.world.item.CrossbowItem;
import net.minecraft.world.item.EggItem;
import net.minecraft.world.item.EnderpearlItem;
import net.minecraft.world.item.ExperienceBottleItem;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.SnowballItem;
import net.minecraft.world.item.ThrowablePotionItem;
import net.minecraft.world.item.TridentItem;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;

import java.util.ArrayList;
import java.util.List;

/** Предсказание траектории стрел, трезубца и бросаемых предметов с учётом гравитации и сопротивления. */
public class TrajectoryModule extends Module {
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xE6D97757));
    private final NumberSetting maxSteps = add(new NumberSetting("Длина", "Максимум тиков полёта", 160, 20, 400, 10));

    private record Kind(double speed, double gravity, double drag, double waterDrag, float pitchOffset) {}

    public TrajectoryModule() {
        super("Trajectory", "Траектория", "Линия полёта снаряда и точка попадания", ModuleCategory.VISUALS);
        color.setMode(ColorSetting.Mode.THEME);
    }

    private Kind kind(Player p, ItemStack st, boolean using) {
        var item = st.getItem();
        if (item instanceof BowItem) {
            if (!using) return null;
            float power = BowItem.getPowerForTime(p.getTicksUsingItem());
            return power < 0.1f ? null : new Kind(power * 3.0, 0.05, 0.99, 0.6, 0);
        }
        if (item instanceof CrossbowItem) return CrossbowItem.isCharged(st) ? new Kind(3.15, 0.05, 0.99, 0.6, 0) : null;
        if (item instanceof TridentItem) return using ? new Kind(2.5, 0.05, 0.99, 0.99, 0) : null;
        if (item instanceof SnowballItem || item instanceof EggItem || item instanceof EnderpearlItem) return new Kind(1.5, 0.03, 0.99, 0.8, 0);
        if (item instanceof ThrowablePotionItem) return new Kind(0.5, 0.05, 0.99, 0.8, -20);
        if (item instanceof ExperienceBottleItem) return new Kind(0.7, 0.07, 0.99, 0.8, -20);
        return null;
    }

    @Override
    public void onRenderWorld(WorldRenderContext ctx) {
        Player p = mc().player;
        if (p == null || mc().level == null) return;
        Kind k = null;
        for (InteractionHand hand : InteractionHand.values()) {
            ItemStack st = p.getItemInHand(hand);
            k = kind(p, st, p.isUsingItem() && p.getUsedItemHand() == hand);
            if (k != null) break;
        }
        if (k == null) return;
        float partial = Render3D.partial();
        Vec3 eye = p.getEyePosition(partial);
        double[] v = TrajectoryMath.velocity(p.getViewYRot(partial), p.getViewXRot(partial), k.pitchOffset(), k.speed());
        Vec3 mv = p.getDeltaMovement();
        double[] s = {eye.x, eye.y - 0.1, eye.z, v[0] + mv.x, v[1] + (p.onGround() ? 0 : mv.y), v[2] + mv.z};
        List<Vec3> pts = new ArrayList<>();
        pts.add(new Vec3(s[0], s[1], s[2]));
        Vec3 hit = null;
        int steps = maxSteps.get().intValue();
        for (int i = 0; i < steps; i++) {
            Vec3 from = new Vec3(s[0], s[1], s[2]);
            boolean water = !mc().level.getFluidState(BlockPos.containing(from)).isEmpty();
            TrajectoryMath.step(s, k.gravity(), water ? k.waterDrag() : k.drag());
            Vec3 to = new Vec3(s[0], s[1], s[2]);
            var bh = mc().level.clip(new ClipContext(from, to, ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, p));
            Vec3 end = bh.getType() != HitResult.Type.MISS ? bh.getLocation() : null;
            AABB sweep = new AABB(from, to).inflate(0.5);
            for (Entity e : mc().level.getEntities(p, sweep, en -> en.isPickable() && !en.isSpectator())) {
                var c = e.getBoundingBox().inflate(0.3).clip(from, to);
                if (c.isPresent() && (end == null || from.distanceToSqr(c.get()) < from.distanceToSqr(end))) end = c.get();
            }
            if (end != null) { pts.add(end); hit = end; break; }
            pts.add(to);
            if (s[1] < mc().level.getMinY() - 16) break;
        }
        Render3D.begin(ctx);
        var lines = Render3D.lines(ctx);
        int c = color.color();
        int n = pts.size();
        for (int i = 1; i < n; i++) {
            float f = 0.35f + 0.65f * (i / (float) n);
            Vec3 a = pts.get(i - 1), b = pts.get(i);
            Render3D.line(ctx.matrices(), lines, a.x, a.y, a.z, b.x, b.y, b.z, ColorUtil.withAlpha(c, Math.round(ColorUtil.alpha(c) * f)));
        }
        if (hit != null) {
            var quads = Render3D.quads(ctx);
            Render3D.filledRing(ctx.matrices(), quads, hit.x, hit.y + 0.02, hit.z, 0.18, 0.3, 32, ColorUtil.withAlpha(c, 40), c);
            Render3D.circle(ctx.matrices(), lines, hit.x, hit.y + 0.03, hit.z, 0.3, 32, c);
        }
        Render3D.end(ctx);
    }
}
