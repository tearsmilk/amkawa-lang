package ruruka.suka.rurukasuka.mixin;

import ruruka.suka.rurukasuka.render.gui.CosmeticGuiRenderState;
import ruruka.suka.rurukasuka.render.gui.CosmeticGuiRenderer;
import ruruka.suka.rurukasuka.render.gui.PlayerCosmeticGuiRenderState;
import ruruka.suka.rurukasuka.render.gui.PlayerCosmeticGuiRenderer;
import net.minecraft.client.gui.render.GuiRenderer;
import net.minecraft.client.gui.render.pip.PictureInPictureRenderer;
import net.minecraft.client.gui.render.state.pip.PictureInPictureRenderState;
import net.minecraft.client.renderer.MultiBufferSource;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Mutable;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import java.util.HashMap;
import java.util.Map;

@Mixin(GuiRenderer.class)
public class GuiRendererMixin {

    @Shadow @Final @Mutable
    private Map<Class<? extends PictureInPictureRenderState>, PictureInPictureRenderer<?>> pictureInPictureRenderers;

    @Shadow @Final
    private MultiBufferSource.BufferSource bufferSource;

    @Inject(method = "<init>", at = @At("TAIL"))
    private void rurukasuka$registerCosmeticRenderer(CallbackInfo ci) {
        Map<Class<? extends PictureInPictureRenderState>, PictureInPictureRenderer<?>> m =
                new HashMap<>(this.pictureInPictureRenderers);
        m.put(CosmeticGuiRenderState.class, new CosmeticGuiRenderer(this.bufferSource));
        m.put(PlayerCosmeticGuiRenderState.class, new PlayerCosmeticGuiRenderer(this.bufferSource));
        this.pictureInPictureRenderers = m;
    }
}
