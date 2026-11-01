package milk.naovisual.mixin;

import milk.naovisual.core.util.ItemPhysicsState;
import net.minecraft.client.renderer.entity.state.ItemEntityRenderState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;

@Mixin(ItemEntityRenderState.class)
public class ItemEntityRenderStateMixin implements ItemPhysicsState {
    @Unique private boolean naovisual$ground;
    @Unique private float naovisual$yawRad;

    @Override public boolean naovisual$onGround() { return naovisual$ground; }
    @Override public void naovisual$setOnGround(boolean v) { naovisual$ground = v; }
    @Override public float naovisual$yaw() { return naovisual$yawRad; }
    @Override public void naovisual$setYaw(float v) { naovisual$yawRad = v; }
}
