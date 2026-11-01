package milk.naovisual.core;

import milk.naovisual.core.util.TrajectoryMath;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class TrajectoryMathTest {
    @Test
    void stepMovesThenAppliesDragAndGravity() {
        double[] s = {0, 10, 0, 1, 0, 0};
        TrajectoryMath.step(s, 0.05, 0.99);
        assertEquals(1.0, s[0], 1e-9);
        assertEquals(10.0, s[1], 1e-9);
        assertEquals(0.99, s[3], 1e-9);
        assertEquals(-0.05, s[4], 1e-9);
        TrajectoryMath.step(s, 0.05, 0.99);
        assertEquals(1.99, s[0], 1e-9);
        assertEquals(9.95, s[1], 1e-9);
    }

    @Test
    void velocityFollowsLookDirection() {
        double[] south = TrajectoryMath.velocity(0, 0, 0, 3);
        assertEquals(0, south[0], 1e-9);
        assertEquals(0, south[1], 1e-9);
        assertEquals(3, south[2], 1e-9);
        double[] up = TrajectoryMath.velocity(90, -90, 0, 1.5);
        assertEquals(1.5, up[1], 1e-9);
        double[] west = TrajectoryMath.velocity(90, 0, 0, 2);
        assertEquals(-2, west[0], 1e-9);
        double[] any = TrajectoryMath.velocity(37, -12, -20, 0.5);
        assertEquals(0.5, Math.sqrt(any[0] * any[0] + any[1] * any[1] + any[2] * any[2]), 1e-9);
    }

    @Test
    void arrowFallsUnderGravity() {
        double[] s = {0, 0, 0, 0, 0, 3};
        double minY = 0;
        for (int i = 0; i < 40; i++) { TrajectoryMath.step(s, 0.05, 0.99); minY = Math.min(minY, s[1]); }
        assertTrue(minY < -10);
        assertTrue(s[2] > 80 && s[2] < 120);
    }
}
