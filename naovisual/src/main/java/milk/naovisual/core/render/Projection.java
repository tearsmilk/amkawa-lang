package milk.naovisual.core.render;

import net.minecraft.client.Minecraft;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Matrix4fc;
import org.joml.Vector4f;

/** Проекция мировой точки в координаты HUD; матрицы запоминаются в конце рендера мира. */
public final class Projection {
    private static final Matrix4f PROJECTION = new Matrix4f();
    private static final Matrix4f VIEW = new Matrix4f();
    private static Vec3 camPos = Vec3.ZERO;
    private static boolean ready;

    private Projection() {}

    public static float partial() { return Minecraft.getInstance().getDeltaTracker().getGameTimeDeltaPartialTick(false); }

    public static void capture(Vec3 cameraPos, Matrix4fc view, Matrix4fc projection) {
        if (cameraPos == null || view == null || projection == null) return;
        PROJECTION.set(projection);
        VIEW.set(view);
        camPos = cameraPos;
        ready = true;
    }

    /** @return {x, y, глубина} в GUI-пикселях; null если матриц ещё нет или точка за камерой. */
    public static float[] toScreen(Vec3 world) {
        if (!ready) return null;
        Minecraft mc = Minecraft.getInstance();
        Vector4f v = new Vector4f((float) (world.x - camPos.x), (float) (world.y - camPos.y), (float) (world.z - camPos.z), 1f);
        VIEW.transform(v);
        PROJECTION.transform(v);
        if (v.w <= 1e-5f) return null;
        float nx = v.x / v.w, ny = v.y / v.w;
        int w = mc.getWindow().getGuiScaledWidth(), h = mc.getWindow().getGuiScaledHeight();
        return new float[]{(nx + 1f) / 2f * w, (1f - ny) / 2f * h, v.w};
    }
}
