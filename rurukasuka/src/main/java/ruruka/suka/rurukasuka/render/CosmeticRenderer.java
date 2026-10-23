package ruruka.suka.rurukasuka.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Vector3f;

/**
 * Рисует .bbmodel своими квадами (per-face UV + поворот каждого куба).
 * ВСЯ математика — в подгонке: глобальный Y-flip, порядок вершин/UV, знаки поворотов, высота посадки.
 * Крутим константы тут по скриншотам.
 */
public final class CosmeticRenderer {

    // ── глобальные ручки подгонки ──
    private static final float SCALE = 0.0625f; // 1/16: пиксели Blockbench -> блоки

    public static void emit(BbModel model, PoseStack.Pose basePose, VertexConsumer vc, int light, int overlay,
                            float scale, float offX, float offY, float offZ) {
        Matrix4f m = new Matrix4f(basePose.pose());
        Matrix3f n = new Matrix3f(basePose.normal());
        // Blockbench Y-up -> MC Y-down (один раз глобально), плюс масштаб/сдвиг
        float s = SCALE * scale;               // 1/16 * пер-модельный масштаб (с сайта)
        m.scale(s, -s, s);
        m.translate(offX, offY, offZ);         // смещение (пиксели): X=вбок, Y=ВВЕРХ+, Z=глубина
        n.scale(1f, -1f, 1f);

        BbAnimation anim = model.animations.isEmpty() ? null : model.animations.get(0);
        float time = 0f;
        if (anim != null && anim.length > 0f) {
            double sec = System.nanoTime() / 1_000_000_000.0;
            time = anim.loop ? (float) (sec % anim.length) : (float) Math.min(sec % (anim.length * 2.0), anim.length);
        }
        for (BbModel.Bone b : model.roots) emitBone(b, m, n, vc, light, overlay, model, anim, time);
    }

    private static void emitBone(BbModel.Bone b, Matrix4f m, Matrix3f n, VertexConsumer vc,
                                 int light, int overlay, BbModel model, BbAnimation anim, float time) {
        Matrix4f bm = new Matrix4f(m);
        Matrix3f bn = new Matrix3f(n);

        float[] pos = {0, 0, 0}, rot = {0, 0, 0}, scl = {1, 1, 1};
        if (anim != null && !b.uuid.isEmpty()) {
            BbAnimation.BoneAnim ba = anim.bones.get(b.uuid);
            if (ba != null) {
                sample(ba.position, time, pos, 0f);
                sample(ba.rotation, time, rot, 0f);
                sample(ba.scale, time, scl, 1f);
            }
        }

        // позиция(аним) -> пивот -> поворот(база+аним) -> скейл(аним) -> обратно
        bm.translate(pos[0], pos[1], pos[2]);
        bm.translate(b.origin[0], b.origin[1], b.origin[2]);
        // база (rest) поворот, затем анимация поверх — раздельно, а не сложением углов
        bm.rotateZ((float) Math.toRadians(b.rotation[2]));
        bm.rotateY((float) Math.toRadians(b.rotation[1]));
        bm.rotateX((float) Math.toRadians(b.rotation[0]));
        bm.rotateZ((float) Math.toRadians(rot[2]));
        bm.rotateY((float) Math.toRadians(rot[1]));
        bm.rotateX((float) Math.toRadians(rot[0]));
        bm.scale(scl[0], scl[1], scl[2]);
        bm.translate(-b.origin[0], -b.origin[1], -b.origin[2]);

        bn.rotateZ((float) Math.toRadians(b.rotation[2]));
        bn.rotateY((float) Math.toRadians(b.rotation[1]));
        bn.rotateX((float) Math.toRadians(b.rotation[0]));
        bn.rotateZ((float) Math.toRadians(rot[2]));
        bn.rotateY((float) Math.toRadians(rot[1]));
        bn.rotateX((float) Math.toRadians(rot[0]));

        for (BbModel.Cube c : b.cubes) emitCube(c, bm, bn, vc, light, overlay, model);
        for (BbModel.Bone ch : b.children) emitBone(ch, bm, bn, vc, light, overlay, model, anim, time);
    }

    private static void sample(java.util.List<BbAnimation.Keyframe> kfs, float time, float[] out, float def) {
        if (kfs.isEmpty()) { out[0] = def; out[1] = def; out[2] = def; return; }
        if (time <= kfs.get(0).time) { set(out, kfs.get(0)); return; }
        BbAnimation.Keyframe last = kfs.get(kfs.size() - 1);
        if (time >= last.time) { set(out, last); return; }
        for (int i = 0; i < kfs.size() - 1; i++) {
            BbAnimation.Keyframe a = kfs.get(i), b = kfs.get(i + 1);
            if (time >= a.time && time <= b.time) {
                if ("step".equals(a.interp) || b.time == a.time) { set(out, a); return; }
                float f = (time - a.time) / (b.time - a.time);
                out[0] = a.x + (b.x - a.x) * f;
                out[1] = a.y + (b.y - a.y) * f;
                out[2] = a.z + (b.z - a.z) * f;
                return;
            }
        }
        set(out, last);
    }

    private static void set(float[] out, BbAnimation.Keyframe k) { out[0] = k.x; out[1] = k.y; out[2] = k.z; }

    private static void emitCube(BbModel.Cube c, Matrix4f m, Matrix3f n,
                                 VertexConsumer vc, int light, int overlay, BbModel model) {
        Matrix4f cm = new Matrix4f(m);
        Matrix3f cn = new Matrix3f(n);
        pivotRotate(cm, cn, c.origin, c.rotation);

        float x0 = c.from[0] - c.inflate, y0 = c.from[1] - c.inflate, z0 = c.from[2] - c.inflate;
        float x1 = c.to[0] + c.inflate,   y1 = c.to[1] + c.inflate,   z1 = c.to[2] + c.inflate;
        float tw = model.texWidth, th = model.texHeight;

        // грань: 4 угла (BB, Y-up) + нормаль; UV [u1,v1,u2,v2] в пикселях
        face(vc, cm, cn, light, overlay, c, "north", tw, th, 0, 0, -1,
                x1, y1, z0, x0, y1, z0, x0, y0, z0, x1, y0, z0);
        face(vc, cm, cn, light, overlay, c, "south", tw, th, 0, 0, 1,
                x0, y1, z1, x1, y1, z1, x1, y0, z1, x0, y0, z1);
        face(vc, cm, cn, light, overlay, c, "east", tw, th, 1, 0, 0,
                x1, y1, z1, x1, y1, z0, x1, y0, z0, x1, y0, z1);
        face(vc, cm, cn, light, overlay, c, "west", tw, th, -1, 0, 0,
                x0, y1, z0, x0, y1, z1, x0, y0, z1, x0, y0, z0);
        face(vc, cm, cn, light, overlay, c, "up", tw, th, 0, 1, 0,
                x0, y1, z0, x1, y1, z0, x1, y1, z1, x0, y1, z1);
        face(vc, cm, cn, light, overlay, c, "down", tw, th, 0, -1, 0,
                x0, y0, z1, x1, y0, z1, x1, y0, z0, x0, y0, z0);
    }

    private static void face(VertexConsumer vc, Matrix4f m, Matrix3f n, int light, int overlay,
                             BbModel.Cube c, String faceName, float tw, float th,
                             float nx, float ny, float nz,
                             float ax, float ay, float az, float bx, float by, float bz,
                             float dx, float dy, float dz, float ex, float ey, float ez) {
        BbModel.Face f = c.faces.get(faceName);
        if (f == null) return;
        float u1 = f.uv[0] / tw, v1 = f.uv[1] / th, u2 = f.uv[2] / tw, v2 = f.uv[3] / th;
        Vector3f nr = n.transform(new Vector3f(nx, ny, nz));
        vertex(vc, m, ax, ay, az, u1, v1, nr, light, overlay);
        vertex(vc, m, bx, by, bz, u2, v1, nr, light, overlay);
        vertex(vc, m, dx, dy, dz, u2, v2, nr, light, overlay);
        vertex(vc, m, ex, ey, ez, u1, v2, nr, light, overlay);
    }

    private static void vertex(VertexConsumer vc, Matrix4f m, float x, float y, float z,
                               float u, float v, Vector3f nr, int light, int overlay) {
        Vector3f p = m.transformPosition(new Vector3f(x, y, z));
        vc.addVertex(p.x, p.y, p.z).setColor(-1).setUv(u, v)
                .setOverlay(overlay).setLight(light).setNormal(nr.x, nr.y, nr.z);
    }

    private static void pivotRotate(Matrix4f m, Matrix3f n, float[] origin, float[] rot) {
        m.translate(origin[0], origin[1], origin[2]);
        m.rotateZ((float) Math.toRadians(rot[2]));
        m.rotateY((float) Math.toRadians(rot[1]));
        m.rotateX((float) Math.toRadians(rot[0]));
        m.translate(-origin[0], -origin[1], -origin[2]);
        n.rotateZ((float) Math.toRadians(rot[2]));
        n.rotateY((float) Math.toRadians(rot[1]));
        n.rotateX((float) Math.toRadians(rot[0]));
    }

    private CosmeticRenderer() {}
}
