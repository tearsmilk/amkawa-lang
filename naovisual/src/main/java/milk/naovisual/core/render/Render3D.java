package milk.naovisual.core.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import milk.naovisual.core.util.ColorUtil;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderContext;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.rendertype.RenderTypes;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Отрисовка в мире: рамки, заливки, линии, круги. Все координаты — абсолютные; сдвиг камеры делается здесь. */
public final class Render3D {
    private Render3D() {}

    /** Переводит матрицу в систему координат мира (вычитает позицию камеры). Обязательно pop после. */
    public static void begin(WorldRenderContext ctx) {
        PoseStack ps = ctx.matrices();
        ps.pushPose();
        Vec3 cam = Render3D.cameraPos(ctx);
        ps.translate(-cam.x, -cam.y, -cam.z);
    }

    public static void end(WorldRenderContext ctx) {
        ctx.matrices().popPose();
    }

    public static Vec3 cameraPos(WorldRenderContext ctx) { return ctx.worldState().cameraRenderState.pos; }

    public static org.joml.Vector3f left(WorldRenderContext ctx) {
        return new org.joml.Vector3f(1, 0, 0).rotate(ctx.worldState().cameraRenderState.orientation);
    }

    public static org.joml.Vector3f up(WorldRenderContext ctx) {
        return new org.joml.Vector3f(0, 1, 0).rotate(ctx.worldState().cameraRenderState.orientation);
    }

    /** Доля тика текущего кадра. */
    public static float partial() {
        return net.minecraft.client.Minecraft.getInstance().getDeltaTracker().getGameTimeDeltaPartialTick(false);
    }

    public static VertexConsumer lines(WorldRenderContext ctx) {
        return ctx.consumers().getBuffer(RenderTypes.lines());
    }

    public static VertexConsumer quads(WorldRenderContext ctx) {
        return ctx.consumers().getBuffer(RenderTypes.debugQuads());
    }

    public static VertexConsumer lines(MultiBufferSource src) { return src.getBuffer(RenderTypes.lines()); }
    public static VertexConsumer quads(MultiBufferSource src) { return src.getBuffer(RenderTypes.debugQuads()); }

    public static final float LINE_WIDTH = 2.0f;

    public static void line(PoseStack ps, VertexConsumer vc, double x1, double y1, double z1, double x2, double y2, double z2, int color) {
        PoseStack.Pose pose = ps.last();
        float dx = (float) (x2 - x1), dy = (float) (y2 - y1), dz = (float) (z2 - z1);
        float len = (float) Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (len < 1e-6f) return;
        dx /= len; dy /= len; dz /= len;
        // формат линий 1.21.11 содержит LineWidth; без него ImmediatelyFast падает («Missing elements in vertex»)
        vc.addVertex(pose, (float) x1, (float) y1, (float) z1).setColor(color).setNormal(pose, dx, dy, dz).setLineWidth(LINE_WIDTH);
        vc.addVertex(pose, (float) x2, (float) y2, (float) z2).setColor(color).setNormal(pose, dx, dy, dz).setLineWidth(LINE_WIDTH);
    }

    public static void lineBox(PoseStack ps, VertexConsumer vc, AABB box, int color) {
        double x1 = box.minX, y1 = box.minY, z1 = box.minZ, x2 = box.maxX, y2 = box.maxY, z2 = box.maxZ;
        line(ps, vc, x1, y1, z1, x2, y1, z1, color); line(ps, vc, x2, y1, z1, x2, y1, z2, color);
        line(ps, vc, x2, y1, z2, x1, y1, z2, color); line(ps, vc, x1, y1, z2, x1, y1, z1, color);
        line(ps, vc, x1, y2, z1, x2, y2, z1, color); line(ps, vc, x2, y2, z1, x2, y2, z2, color);
        line(ps, vc, x2, y2, z2, x1, y2, z2, color); line(ps, vc, x1, y2, z2, x1, y2, z1, color);
        line(ps, vc, x1, y1, z1, x1, y2, z1, color); line(ps, vc, x2, y1, z1, x2, y2, z1, color);
        line(ps, vc, x2, y1, z2, x2, y2, z2, color); line(ps, vc, x1, y1, z2, x1, y2, z2, color);
    }

    private static void quad(PoseStack.Pose pose, VertexConsumer vc, int color,
                             double ax, double ay, double az, double bx, double by, double bz,
                             double cx, double cy, double cz, double dx, double dy, double dz) {
        vc.addVertex(pose, (float) ax, (float) ay, (float) az).setColor(color);
        vc.addVertex(pose, (float) bx, (float) by, (float) bz).setColor(color);
        vc.addVertex(pose, (float) cx, (float) cy, (float) cz).setColor(color);
        vc.addVertex(pose, (float) dx, (float) dy, (float) dz).setColor(color);
    }

    public static void quad(PoseStack ps, VertexConsumer vc, int color, Vec3 a, Vec3 b, Vec3 c, Vec3 d) {
        quad(ps.last(), vc, color, a.x, a.y, a.z, b.x, b.y, b.z, c.x, c.y, c.z, d.x, d.y, d.z);
    }

    public static void filledBox(PoseStack ps, VertexConsumer vc, AABB b, int color) {
        PoseStack.Pose p = ps.last();
        double x1 = b.minX, y1 = b.minY, z1 = b.minZ, x2 = b.maxX, y2 = b.maxY, z2 = b.maxZ;
        quad(p, vc, color, x1, y1, z1, x2, y1, z1, x2, y1, z2, x1, y1, z2); // низ
        quad(p, vc, color, x1, y2, z1, x1, y2, z2, x2, y2, z2, x2, y2, z1); // верх
        quad(p, vc, color, x1, y1, z1, x1, y2, z1, x2, y2, z1, x2, y1, z1); // север
        quad(p, vc, color, x1, y1, z2, x2, y1, z2, x2, y2, z2, x1, y2, z2); // юг
        quad(p, vc, color, x1, y1, z1, x1, y1, z2, x1, y2, z2, x1, y2, z1); // запад
        quad(p, vc, color, x2, y1, z1, x2, y2, z1, x2, y2, z2, x2, y1, z2); // восток
    }

    /** Заливка с вертикальным градиентом (цвет внизу → цвет вверху). */
    public static void gradientBox(PoseStack ps, VertexConsumer vc, AABB b, int bottom, int top) {
        PoseStack.Pose p = ps.last();
        double x1 = b.minX, y1 = b.minY, z1 = b.minZ, x2 = b.maxX, y2 = b.maxY, z2 = b.maxZ;
        double[][] sides = {
                {x1, z1, x2, z1}, {x2, z1, x2, z2}, {x2, z2, x1, z2}, {x1, z2, x1, z1}
        };
        for (double[] s : sides) {
            vc.addVertex(p, (float) s[0], (float) y1, (float) s[1]).setColor(bottom);
            vc.addVertex(p, (float) s[2], (float) y1, (float) s[3]).setColor(bottom);
            vc.addVertex(p, (float) s[2], (float) y2, (float) s[3]).setColor(top);
            vc.addVertex(p, (float) s[0], (float) y2, (float) s[1]).setColor(top);
        }
        quad(p, vc, top, x1, y2, z1, x1, y2, z2, x2, y2, z2, x2, y2, z1);
        quad(p, vc, bottom, x1, y1, z1, x2, y1, z1, x2, y1, z2, x1, y1, z2);
    }

    /** Горизонтальный круг из отрезков. */
    public static void circle(PoseStack ps, VertexConsumer vc, double cx, double cy, double cz, double radius, int segments, int color) {
        double prevX = cx + radius, prevZ = cz;
        for (int i = 1; i <= segments; i++) {
            double a = i / (double) segments * Math.PI * 2;
            double x = cx + Math.cos(a) * radius, z = cz + Math.sin(a) * radius;
            line(ps, vc, prevX, cy, prevZ, x, cy, z, color);
            prevX = x; prevZ = z;
        }
    }

    /** Заполненное кольцо (между двумя радиусами) из квадов, горизонтальное. */
    public static void filledRing(PoseStack ps, VertexConsumer vc, double cx, double cy, double cz, double inner, double outer, int segments, int colorInner, int colorOuter) {
        PoseStack.Pose p = ps.last();
        for (int i = 0; i < segments; i++) {
            double a1 = i / (double) segments * Math.PI * 2, a2 = (i + 1) / (double) segments * Math.PI * 2;
            vc.addVertex(p, (float) (cx + Math.cos(a1) * inner), (float) cy, (float) (cz + Math.sin(a1) * inner)).setColor(colorInner);
            vc.addVertex(p, (float) (cx + Math.cos(a1) * outer), (float) cy, (float) (cz + Math.sin(a1) * outer)).setColor(colorOuter);
            vc.addVertex(p, (float) (cx + Math.cos(a2) * outer), (float) cy, (float) (cz + Math.sin(a2) * outer)).setColor(colorOuter);
            vc.addVertex(p, (float) (cx + Math.cos(a2) * inner), (float) cy, (float) (cz + Math.sin(a2) * inner)).setColor(colorInner);
        }
    }

    /** Квад, повёрнутый к камере (билборд) с центром в точке. */
    public static void billboard(PoseStack ps, VertexConsumer vc, WorldRenderContext ctx, double x, double y, double z, float size, int color) {
        org.joml.Vector3fc left = left(ctx);
        org.joml.Vector3fc up = up(ctx);
        float h = size / 2f;
        PoseStack.Pose p = ps.last();
        float lx = left.x() * h, ly = left.y() * h, lz = left.z() * h;
        float ux = up.x() * h, uy = up.y() * h, uz = up.z() * h;
        vc.addVertex(p, (float) (x - lx - ux), (float) (y - ly - uy), (float) (z - lz - uz)).setColor(color);
        vc.addVertex(p, (float) (x - lx + ux), (float) (y - ly + uy), (float) (z - lz + uz)).setColor(color);
        vc.addVertex(p, (float) (x + lx + ux), (float) (y + ly + uy), (float) (z + lz + uz)).setColor(color);
        vc.addVertex(p, (float) (x + lx - ux), (float) (y + ly - uy), (float) (z + lz - uz)).setColor(color);
    }

    /** Интерполированный бокс сущности для текущего кадра. */
    public static AABB lerpBox(Entity e, float partial) {
        double dx = e.getX() - e.xo, dy = e.getY() - e.yo, dz = e.getZ() - e.zo;
        double x = e.xo + dx * partial, y = e.yo + dy * partial, z = e.zo + dz * partial;
        AABB b = e.getBoundingBox();
        return b.move(x - e.getX(), y - e.getY(), z - e.getZ());
    }

    public static Vec3 lerpPos(Entity e, float partial) {
        return new Vec3(e.xo + (e.getX() - e.xo) * partial, e.yo + (e.getY() - e.yo) * partial, e.zo + (e.getZ() - e.zo) * partial);
    }

    public static int fade(int color, float alpha) { return ColorUtil.withAlpha(color, Math.round(ColorUtil.alpha(color) * alpha)); }
}
