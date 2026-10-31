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
import milk.naovisual.core.util.Friends;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderContext;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.phys.Vec3;

/** Конусная «китайская шляпа» над головой — своя, друзей или всех игроков. */
public class ChinaHatModule extends Module {
    private final NumberSetting radius = add(new NumberSetting("Радиус", "", 0.6, 0.2, 1.5, 0.05));
    private final NumberSetting height = add(new NumberSetting("Высота", "", 0.35, 0.1, 1.0, 0.05));
    private final NumberSetting segments = add(new NumberSetting("Сегменты", "", 24, 6, 64, 1));
    private final BooleanSetting self = add(new BooleanSetting("Себе", "", true));
    private final BooleanSetting friends = add(new BooleanSetting("Друзьям", "", true));
    private final BooleanSetting others = add(new BooleanSetting("Всем игрокам", "", false));
    private final BooleanSetting wire = add(new BooleanSetting("Каркас", "Линии вместо заливки", false));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xAAD97757));
    private final ColorSetting tip = add(new ColorSetting("Цвет вершины", "", 0xFFFFFFFF));

    public ChinaHatModule() {
        super("ChinaHat", "Шляпа", "Конусная шляпа над головой игрока", ModuleCategory.VISUALS);
        color.setMode(ColorSetting.Mode.THEME);
    }

    @Override
    public void onRenderWorld(WorldRenderContext ctx) {
        if (mc().level == null) return;
        float partial = Render3D.partial();
        Render3D.begin(ctx);
        PoseStack ps = ctx.matrices();
        VertexConsumer quads = Render3D.quads(ctx), lines = Render3D.lines(ctx);
        for (Player p : mc().level.players()) {
            boolean isSelf = p == mc().player;
            if (isSelf && (!self.on() || mc().options.getCameraType().isFirstPerson())) continue;
            if (!isSelf && !(others.on() || friends.on() && Friends.isFriend(p))) continue;
            if (p.isInvisible() || !p.isAlive()) continue;
            Vec3 pos = Render3D.lerpPos(p, partial);
            double y = pos.y + p.getBbHeight() + (p.isCrouching() ? -0.2 : 0) + 0.05;
            drawHat(ps, quads, lines, pos.x, y, pos.z);
        }
        Render3D.end(ctx);
    }

    private void drawHat(PoseStack ps, VertexConsumer quads, VertexConsumer lines, double cx, double cy, double cz) {
        int n = segments.getInt();
        double r = radius.get(), h = height.get();
        int base = color.color(), top = ColorUtil.withAlpha(tip.color(), ColorUtil.alpha(base));
        PoseStack.Pose pose = ps.last();
        for (int i = 0; i < n; i++) {
            double a1 = i / (double) n * Math.PI * 2, a2 = (i + 1) / (double) n * Math.PI * 2;
            double x1 = cx + Math.cos(a1) * r, z1 = cz + Math.sin(a1) * r, x2 = cx + Math.cos(a2) * r, z2 = cz + Math.sin(a2) * r;
            if (wire.on()) {
                Render3D.line(ps, lines, x1, cy, z1, x2, cy, z2, base);
                Render3D.line(ps, lines, x1, cy, z1, cx, cy + h, cz, base);
            } else {
                quads.addVertex(pose, (float) x1, (float) cy, (float) z1).setColor(base);
                quads.addVertex(pose, (float) x2, (float) cy, (float) z2).setColor(base);
                quads.addVertex(pose, (float) cx, (float) (cy + h), (float) cz).setColor(top);
                quads.addVertex(pose, (float) cx, (float) (cy + h), (float) cz).setColor(top);
            }
        }
    }
}
