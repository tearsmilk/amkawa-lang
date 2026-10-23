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
import com.mojang.math.Axis;
import ruruka.suka.rurukasuka.cosmetic.CosmeticCategory;
import ruruka.suka.rurukasuka.render.CosmeticRenderer;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.render.TextureSetup;
import net.minecraft.client.gui.render.pip.PictureInPictureRenderer;
import net.minecraft.client.gui.render.state.BlitRenderState;
import net.minecraft.client.gui.render.state.GuiRenderState;
import net.minecraft.client.model.geom.ModelPart;
import net.minecraft.client.model.player.PlayerModel;
import net.minecraft.client.renderer.CachedOrthoProjectionMatrixBuffer;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderPipelines;
import net.minecraft.client.renderer.rendertype.RenderType;
import net.minecraft.client.renderer.rendertype.RenderTypes;
import net.minecraft.client.renderer.texture.OverlayTexture;
import org.joml.Matrix4fStack;

import java.util.HashMap;
import java.util.Map;

/** Рисует модель игрока (скин) + надетую/примеряемую косметику в GUI-текстуру. */
public class PlayerCosmeticGuiRenderer extends PictureInPictureRenderer<PlayerCosmeticGuiRenderState> {

    private static final class Slot {
        GpuTexture color, depth;
        GpuTextureView colorView, depthView;
        int w, h;
        void close() {
            if (colorView != null) colorView.close();
            if (color != null) color.close();
            if (depthView != null) depthView.close();
            if (depth != null) depth.close();
            colorView = null; color = null; depthView = null; depth = null;
        }
    }

    private final Map<String, Slot> slots = new HashMap<>();
    private final CachedOrthoProjectionMatrixBuffer proj =
            new CachedOrthoProjectionMatrixBuffer("rurukasuka-player", -1000f, 1000f, true);

    public PlayerCosmeticGuiRenderer(MultiBufferSource.BufferSource bufferSource) { super(bufferSource); }

    @Override public Class<PlayerCosmeticGuiRenderState> getRenderStateClass() { return PlayerCosmeticGuiRenderState.class; }
    @Override protected String getTextureLabel() { return "rurukasuka player"; }

    @Override
    public void prepare(PlayerCosmeticGuiRenderState state, GuiRenderState guiRenderState, int guiScale) {
        int w = (state.x1() - state.x0()) * guiScale;
        int h = (state.y1() - state.y0()) * guiScale;
        if (w <= 0 || h <= 0) return;

        Slot slot = slots.get(state.key());
        boolean recreate = slot == null || slot.w != w || slot.h != h;
        if (slot == null) { slot = new Slot(); slots.put(state.key(), slot); }

        prepareTextures(slot, recreate, w, h);
        RenderSystem.outputColorTextureOverride = slot.colorView;
        RenderSystem.outputDepthTextureOverride = slot.depthView;

        PoseStack pose = new PoseStack();
        pose.translate(w / 2f, h, 0f);
        float scale = guiScale * state.scale();
        pose.scale(scale, scale, -scale);
        renderModel(state, pose, scale);

        RenderSystem.outputColorTextureOverride = null;
        RenderSystem.outputDepthTextureOverride = null;
        blit(slot, state, guiRenderState);
    }

    private void prepareTextures(Slot slot, boolean recreate, int w, int h) {
        GpuDevice device = RenderSystem.getDevice();
        if (recreate) {
            slot.close();
            slot.color = device.createTexture("rurukasuka player", 12, TextureFormat.RGBA8, w, h, 1, 1);
            slot.colorView = device.createTextureView(slot.color);
            slot.depth = device.createTexture("rurukasuka player depth", 8, TextureFormat.DEPTH32, w, h, 1, 1);
            slot.depthView = device.createTextureView(slot.depth);
            slot.w = w; slot.h = h;
        }
        CommandEncoder enc = device.createCommandEncoder();
        enc.clearColorAndDepthTextures(slot.color, 0, slot.depth, 1.0);
        RenderSystem.setProjectionMatrix(proj.getBuffer(w, h), ProjectionType.ORTHOGRAPHIC);
    }

    private void renderModel(PlayerCosmeticGuiRenderState state, PoseStack pose, float scale) {
        Minecraft.getInstance().gameRenderer.getLighting().setupFor(Lighting.Entry.PLAYER_SKIN);
        Matrix4fStack mv = RenderSystem.getModelViewStack();
        mv.pushMatrix();
        mv.rotateAround(Axis.XP.rotationDegrees(state.rotationX()), 0f, scale * 1.0625f, 0f);
        pose.mulPose(Axis.YP.rotationDegrees(-state.rotationY()));
        pose.translate(0f, -1.6010001f, 0f);

        PlayerModel pm = state.playerModel();
        RenderType skinRT = pm.renderType(state.skin());
        pm.renderToBuffer(pose, bufferSource.getBuffer(skinRT), 15728880, OverlayTexture.NO_OVERLAY);

        for (PlayerCosmeticGuiRenderState.Piece pc : state.pieces()) {
            pose.pushPose();
            attach(pose, pm, pc.category());
            RenderType rt = RenderTypes.entityCutoutNoCull(pc.texture());
            CosmeticRenderer.emit(pc.model(), pose.last(), bufferSource.getBuffer(rt),
                    15728880, OverlayTexture.NO_OVERLAY, pc.scale(), pc.offX(), pc.offY(), pc.offZ());
            pose.popPose();
        }
        bufferSource.endBatch();   // важно: до popMatrix, чтобы modelView (rotX) был активен
        mv.popMatrix();
    }

    private void attach(PoseStack pose, PlayerModel m, CosmeticCategory cat) {
        if (cat == CosmeticCategory.AURAS) return;
        ModelPart part = switch (cat) {
            case HATS, PETS -> m.head;
            case WINGS, BACK, COSTUMES, AURAS -> m.body;
            case ARMS -> m.rightArm;
            case LEGS -> m.rightLeg;
        };
        part.translateAndRotate(pose);
    }

    private void blit(Slot slot, PlayerCosmeticGuiRenderState state, GuiRenderState guiRenderState) {
        var sampler = RenderSystem.getSamplerCache().getRepeat(FilterMode.NEAREST);
        guiRenderState.submitBlitToCurrentLayer(new BlitRenderState(
                RenderPipelines.GUI_TEXTURED_PREMULTIPLIED_ALPHA,
                TextureSetup.singleTexture(slot.colorView, sampler),
                state.pose(), state.x0(), state.y0(), state.x1(), state.y1(),
                0f, 1f, 1f, 0f, -1, state.scissorArea(), null));
    }

    @Override
    protected void renderToTexture(PlayerCosmeticGuiRenderState state, PoseStack poseStack) { }

    @Override
    public void close() {
        for (Slot s : slots.values()) s.close();
        slots.clear();
        proj.close();
        super.close();
    }
}
