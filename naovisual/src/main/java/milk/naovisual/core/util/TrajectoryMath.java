package milk.naovisual.core.util;

/** Баллистика снарядов как в ванили: позиция += скорость, скорость *= сопротивление, вертикаль -= гравитация. */
public final class TrajectoryMath {
    private TrajectoryMath() {}

    /** state = {x, y, z, vx, vy, vz}; шаг одного тика (на месте). */
    public static void step(double[] s, double gravity, double drag) {
        s[0] += s[3]; s[1] += s[4]; s[2] += s[5];
        s[3] *= drag; s[4] *= drag; s[5] *= drag;
        s[4] -= gravity;
    }

    /** Вектор скорости по углам взгляда (градусы), как Projectile.shootFromRotation. */
    public static double[] velocity(float yawDeg, float pitchDeg, float pitchOffsetDeg, double speed) {
        double yaw = Math.toRadians(yawDeg), pitch = Math.toRadians(pitchDeg);
        double x = -Math.sin(yaw) * Math.cos(pitch);
        double y = -Math.sin(Math.toRadians(pitchDeg + pitchOffsetDeg));
        double z = Math.cos(yaw) * Math.cos(pitch);
        double len = Math.sqrt(x * x + y * y + z * z);
        return new double[]{x / len * speed, y / len * speed, z / len * speed};
    }
}
