package ruruka.suka.rurukasuka.render.gui;

import com.mojang.blaze3d.ProjectionType;
import com.mojang.blaze3d.platform.Lighting;
import com.mojang.blaze3d.systems.CommandEncoder;
import com.mojang.blaze3d.systems.GpuDevice;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.textures.FilterMode;
import com.mojang.blaze3d.textures.GpuTexture;
import com.mojang.blaze3d.textures.GpuTextureView;
import com.mojang.blaze3d.textures.TextureFormat;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.math.Axis;
import ruruka.suka.rurukasuka.render.CosmeticRenderer;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.render.TextureSetup;
import net.minecraft.client.gui.render.pip.PictureInPictureRenderer;
import net.minecraft.client.gui.render.state.BlitRenderState;
import net.minecraft.client.gui.render.state.GuiRenderState;
import net.minecraft.client.renderer.CachedOrthoProjectionMatrixBuffer;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderPipelines;
import net.minecraft.client.renderer.rendertype.RenderType;
import net.minecraft.client.renderer.rendertype.RenderTypes;
import net.minecraft.client.renderer.texture.OverlayTexture;
import org.joml.Matrix4fStack;

import java.util.HashMap;
import java.util.Map;

/**
 * Рендерит .bbmodel-косметику в GUI. В отличие от ванильного одно-текстурного PIP,
 * держит КЭШ текстур по ключу (id+вариант) — поэтому все карточки показывают свои
 * модели одновременно (как в Essential). Поворот фиксированный, поэтому рендерим
 * каждую модель один раз и потом просто блитим кэш.
 */
public class CosmeticGuiRenderer extends PictureInPictureRenderer<CosmeticGuiRenderState> {

    private static final class Slot {
        GpuTexture color, depth;
        GpuTextureView colorView, depthView;
        int w, h;
        boolean rendered;

        void close() {
            if (colorView != null) colorView.close();
            if (color != null) color.close();
            if (depthView != null) depthView.close();
            if (depth != null) depth.close();
            colorView = null; color = null; depthView = null; depth = null; rendered = false;
        }
    }

    private final Map<String, Slot> slots = new HashMap<>();
    private final CachedOrthoProjectionMatrixBuffer proj =
            new CachedOrthoProjectionMatrixBuffer("rurukasuka-cosmetic", -1000f, 1000f, true);

    public CosmeticGuiRenderer(MultiBufferSource.BufferSource bufferSource) {
        super(bufferSource);
    }

    @Override
    public Class<CosmeticGuiRenderState> getRenderStateClass() {
        return CosmeticGuiRenderState.class;
    }

    @Override
    protected String getTextureLabel() {
        return "rurukasuka cosmetic";
    }

    @Override
    public void prepare(CosmeticGuiRenderState state, GuiRenderState guiRenderState, int guiScale) {
        int w = (state.x1() - state.x0()) * guiScale;
        int h = (state.y1() - state.y0()) * guiScale;
        if (w <= 0 || h <= 0) return;

        Slot slot = slots.get(state.key());
        boolean recreate = slot == null || slot.w != w || slot.h != h;
        if (slot == null) { slot = new Slot(); slots.put(state.key(), slot); }

        prepareTextures(slot, recreate, w, h);   // рендерим каждый кадр — анимация играет
        RenderSystem.outputColorTextureOverride = slot.colorView;
        RenderSystem.outputDepthTextureOverride = slot.depthView;

        PoseStack pose = new PoseStack();
        pose.translate(w / 2f, h, 0f);
        float scale = guiScale * state.scale();
        pose.scale(scale, scale, -scale);
        renderModel(state, pose, scale);
        bufferSource.endBatch();

        RenderSystem.outputColorTextureOverride = null;
        RenderSystem.outputDepthTextureOverride = null;
        blit(slot, state, guiRenderState);
    }

    private void prepareTextures(Slot slot, boolean recreate, int w, int h) {
        GpuDevice device = RenderSystem.getDevice();
        if (recreate) {
            slot.close();
            slot.color = device.createTexture("rurukasuka cosmetic", 12, TextureFormat.RGBA8, w, h, 1, 1);
            slot.colorView = device.createTextureView(slot.color);
            slot.depth = device.createTexture("rurukasuka cosmetic depth", 8, TextureFormat.DEPTH32, w, h, 1, 1);
            slot.depthView = device.createTextureView(slot.depth);
            slot.w = w; slot.h = h; slot.rendered = false;
        }
        CommandEncoder enc = device.createCommandEncoder();
        enc.clearColorAndDepthTextures(slot.color, 0, slot.depth, 1.0);
        RenderSystem.setProjectionMatrix(proj.getBuffer(w, h), ProjectionType.ORTHOGRAPHIC);
    }

    private void renderModel(CosmeticGuiRenderState state, PoseStack pose, float scale) {
        Minecraft.getInstance().gameRenderer.getLighting().setupFor(Lighting.Entry.PLAYER_SKIN);
        Matrix4fStack mv = RenderSystem.getModelViewStack();
        mv.pushMatrix();
        mv.rotateAround(Axis.XP.rotationDegrees(state.rotationX()), 0f, scale * -state.pivotY(), 0f);
        pose.mulPose(Axis.YP.rotationDegrees(-state.rotationY()));
        pose.translate(0f, -state.pivotY(), 0f);
        RenderType rt = RenderTypes.entityCutoutNoCull(state.texture());
        VertexConsumer vc = bufferSource.getBuffer(rt);
        CosmeticRenderer.emit(state.model(), pose.last(), vc,
                15728880, OverlayTexture.NO_OVERLAY, 1f, 0f, 0f, 0f);
        mv.popMatrix();
    }

    private void blit(Slot slot, CosmeticGuiRenderState state, GuiRenderState guiRenderState) {
        var sampler = RenderSystem.getSamplerCache().getRepeat(FilterMode.NEAREST);
        guiRenderState.submitBlitToCurrentLayer(new BlitRenderState(
                RenderPipelines.GUI_TEXTURED_PREMULTIPLIED_ALPHA,
                TextureSetup.singleTexture(slot.colorView, sampler),
                state.pose(), state.x0(), state.y0(), state.x1(), state.y1(),
                0f, 1f, 1f, 0f, -1, state.scissorArea(), null));
    }

    @Override
    protected void renderToTexture(CosmeticGuiRenderState state, PoseStack poseStack) {
        // не используется — prepare() переопределён полностью
    }

    @Override
    public void close() {
        for (Slot s : slots.values()) s.close();
        slots.clear();
        proj.close();
        super.close();
    }
}
