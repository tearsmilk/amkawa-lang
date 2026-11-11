package milk.naovisual.modules.visual;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.render.Render3D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.util.ColorUtil;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderContext;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.phys.Vec3;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Шлейф за игроками: лента из точек с затуханием. */
public class TrailsModule extends Module {
    private final NumberSetting length = add(new NumberSetting("Длина", "Точек в шлейфе", 30, 5, 120, 1));
    private final NumberSetting width = add(new NumberSetting("Ширина", "", 0.25, 0.05, 1.0, 0.05));
    private final BooleanSetting self = add(new BooleanSetting("Себе", "", true));
    private final BooleanSetting others = add(new BooleanSetting("Другим", "", true));
    private final BooleanSetting onlyMoving = add(new BooleanSetting("Только в движении", "Не копить точки стоя", true));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xCCD97757));
    private final ColorSetting color2 = add(new ColorSetting("Цвет хвоста", "", 0x00E8B84A));
    private final Map<UUID, ArrayDeque<Vec3>> trails = new HashMap<>();

    public TrailsModule() {
        super("Trails", "Шлейфы", "Лента-шлейф за игроками", ModuleCategory.VISUALS);
        color.setMode(ColorSetting.Mode.THEME);
    }

    @Override
    public void onTick() {
        if (mc().level == null) return;
        List<UUID> alive = new ArrayList<>();
        for (Player p : mc().level.players()) {
            boolean isSelf = p == mc().player;
            if (isSelf && !self.on() || !isSelf && !others.on()) continue;
            alive.add(p.getUUID());
            ArrayDeque<Vec3> q = trails.computeIfAbsent(p.getUUID(), k -> new ArrayDeque<>());
            Vec3 pos = p.position().add(0, p.getBbHeight() * 0.5, 0);
            boolean moving = p.position().distanceToSqr(p.xo, p.yo, p.zo) > 1e-4;
            if (moving || !onlyMoving.on()) q.addLast(pos);
            else if (!q.isEmpty()) q.pollFirst();
            while (q.size() > length.getInt()) q.pollFirst();
        }
        trails.keySet().retainAll(alive);
    }

    @Override
    public void onRenderWorld(WorldRenderContext ctx) {
        if (trails.isEmpty()) return;
        Render3D.begin(ctx);
        PoseStack ps = ctx.matrices();
        VertexConsumer quads = Render3D.quads(ctx);
        org.joml.Vector3fc left = Render3D.left(ctx);
        int c1 = color.color(), c2 = color2.color();
        for (ArrayDeque<Vec3> q : trails.values()) {
            if (q.size() < 2) continue;
            Vec3[] pts = q.toArray(new Vec3[0]);
            int n = pts.length;
            for (int i = 0; i < n - 1; i++) {
                float f1 = i / (float) (n - 1), f2 = (i + 1) / (float) (n - 1);
                int ca = ColorUtil.lerp(c2, c1, f1), cb = ColorUtil.lerp(c2, c1, f2);
                float w1 = width.getFloat() * f1 * 0.5f, w2 = width.getFloat() * f2 * 0.5f;
                Vec3 a = pts[i], b = pts[i + 1];
                PoseStack.Pose pose = ps.last();
                quads.addVertex(pose, (float) (a.x - left.x() * w1), (float) (a.y - left.y() * w1), (float) (a.z - left.z() * w1)).setColor(ca);
                quads.addVertex(pose, (float) (a.x + left.x() * w1), (float) (a.y + left.y() * w1), (float) (a.z + left.z() * w1)).setColor(ca);
                quads.addVertex(pose, (float) (b.x + left.x() * w2), (float) (b.y + left.y() * w2), (float) (b.z + left.z() * w2)).setColor(cb);
                quads.addVertex(pose, (float) (b.x - left.x() * w2), (float) (b.y - left.y() * w2), (float) (b.z - left.z() * w2)).setColor(cb);
            }
        }
        Render3D.end(ctx);
    }

    @Override public void onDisconnect() { trails.clear(); }
    @Override public void onDisable() { trails.clear(); }
}
