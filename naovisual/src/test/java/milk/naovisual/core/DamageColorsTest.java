package milk.naovisual.core;

import milk.naovisual.core.util.DamageColors;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class DamageColorsTest {
    @Test
    void colors() {
        assertEquals(DamageColors.NORMAL, DamageColors.colorFor(-4, false));
        assertEquals(DamageColors.CRIT, DamageColors.colorFor(-6, true));
        assertEquals(DamageColors.HEAL, DamageColors.colorFor(2, false));
        assertEquals(DamageColors.HEAL, DamageColors.colorFor(2, true));
        assertNotEquals(DamageColors.NORMAL, DamageColors.CRIT);
    }

    @Test
    void format() {
        assertEquals("4", DamageColors.format(-4));
        assertEquals("+2", DamageColors.format(2));
        assertEquals("3.5", DamageColors.format(-3.5f).replace(',', '.'));
    }
}
