package milk.naovisual.core.util;

/** Плавная анимация значения: экспоненциальное приближение к цели по реальному времени. */
public class Anim {
    private float value;
    private float target;
    private long last = System.nanoTime();
    private final float speed;

    public Anim(float initial, float speed) {
        this.value = initial;
        this.target = initial;
        this.speed = speed;
    }

    public Anim(float initial) { this(initial, 12f); }

    public float get() {
        long now = System.nanoTime();
        float dt = Math.min(0.1f, (now - last) / 1_000_000_000f);
        last = now;
        float k = 1f - (float) Math.exp(-speed * dt);
        value += (target - value) * k;
        if (Math.abs(target - value) < 0.0005f) value = target;
        return value;
    }

    public Anim to(float t) { this.target = t; return this; }
    public float target() { return target; }
    public void snap(float v) { value = v; target = v; }
    public boolean done() { return Math.abs(target - value) < 0.001f; }

    public static float lerp(float a, float b, float t) { return a + (b - a) * Math.max(0, Math.min(1, t)); }
    public static double lerp(double a, double b, double t) { return a + (b - a) * Math.max(0, Math.min(1, t)); }
    public static float easeOut(float t) { t = Math.max(0, Math.min(1, t)); return 1 - (1 - t) * (1 - t) * (1 - t); }
    public static float easeInOut(float t) { t = Math.max(0, Math.min(1, t)); return t < 0.5f ? 4 * t * t * t : 1 - (float) Math.pow(-2 * t + 2, 3) / 2; }
    public static float clamp01(float t) { return Math.max(0, Math.min(1, t)); }
}
