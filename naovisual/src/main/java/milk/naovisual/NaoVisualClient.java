package milk.naovisual;

import com.mojang.blaze3d.platform.InputConstants;
import milk.naovisual.core.config.ConfigManager;
import milk.naovisual.core.hud.HudManager;
import milk.naovisual.core.module.ModuleRegistry;
import milk.naovisual.core.particle.ParticleSystem;
import milk.naovisual.core.render.Projection;
import milk.naovisual.core.setting.KeybindSetting;
import milk.naovisual.core.util.Targets;
import milk.naovisual.menu.NaoMenuScreen;
import milk.naovisual.modules.client.*;
import milk.naovisual.modules.hud.*;
import milk.naovisual.modules.other.*;
import milk.naovisual.modules.particle.*;
import milk.naovisual.modules.visual.*;
import milk.naovisual.modules.world.*;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayConnectionEvents;
import net.fabricmc.fabric.api.client.rendering.v1.hud.HudElementRegistry;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderEvents;
import net.fabricmc.fabric.api.event.player.AttackEntityCallback;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.client.KeyMapping;
import net.minecraft.client.Minecraft;
import net.minecraft.world.InteractionResult;
import org.lwjgl.glfw.GLFW;

import java.util.HashSet;
import java.util.Set;

public final class NaoVisualClient implements ClientModInitializer {
    public static final KeyMapping.Category KEY_CATEGORY = new KeyMapping.Category(NaoVisual.id("naovisual"));
    public static KeyMapping menuKey;
    private static final Set<Integer> DOWN = new HashSet<>();

    @Override
    public void onInitializeClient() {
        registerModules();
        ConfigManager.init(FabricLoader.getInstance().getConfigDir());

        menuKey = KeyBindingHelper.registerKeyBinding(new KeyMapping("key.naovisual.menu", GLFW.GLFW_KEY_RIGHT_SHIFT, KEY_CATEGORY));

        HudElementRegistry.addLast(NaoVisual.id("hud"), HudManager::render);
        milk.naovisual.core.hud.HudReplacements.register();
        WorldRenderEvents.AFTER_ENTITIES.register(ctx -> {
            if (ctx.consumers() == null) return;
            ModuleRegistry.renderWorld(ctx);
            ParticleSystem.render(ctx);
        });
        WorldRenderEvents.END_MAIN.register(ctx -> {
            var mc = Minecraft.getInstance();
            var cam = mc.gameRenderer.getMainCamera();
            float fov = ((milk.naovisual.mixin.GameRendererAccessor) mc.gameRenderer).naovisual$getFov(cam, Projection.partial(), true);
            Projection.capture(cam.position(), new org.joml.Matrix4f().rotation(cam.rotation().conjugate(new org.joml.Quaternionf())), mc.gameRenderer.getProjectionMatrix(fov));
        });
        ClientTickEvents.END_CLIENT_TICK.register(NaoVisualClient::tick);
        AttackEntityCallback.EVENT.register((player, level, hand, entity, hit) -> {
            if (level.isClientSide() && player == Minecraft.getInstance().player) {
                Targets.onAttack(entity);
                if (milk.naovisual.core.util.Crits.isCrit(player)) milk.naovisual.core.util.Crits.mark(entity);
                ModuleRegistry.attack(entity);
            }
            return InteractionResult.PASS;
        });
        ClientPlayConnectionEvents.JOIN.register((handler, sender, client) -> ModuleRegistry.joinWorld());
        ClientPlayConnectionEvents.DISCONNECT.register((handler, client) -> {
            Targets.reset();
            ParticleSystem.clear();
            ModuleRegistry.disconnect();
        });
        ClientLifecycleEvents.CLIENT_STOPPING.register(client -> {
            ConfigManager.save();
            ModuleRegistry.get(DiscordModule.class).shutdown();
        });
        NaoVisual.LOGGER.info("NaoVisual {} загружен: {} модулей", NaoVisual.version(), ModuleRegistry.all().size());
    }

    public static void registerModules() {
        ModuleRegistry.clear();
        // HUD
        ModuleRegistry.register(new WatermarkModule());
        ModuleRegistry.register(new ArmorModule());
        ModuleRegistry.register(new BossBarsModule());
        ModuleRegistry.register(new ConsumableModule());
        ModuleRegistry.register(new CoolDownsModule());
        ModuleRegistry.register(new CrossHairModule());
        ModuleRegistry.register(new HotBarModule());
        ModuleRegistry.register(new HotKeysModule());
        ModuleRegistry.register(new IconsModule());
        ModuleRegistry.register(new InventoryModule());
        ModuleRegistry.register(new ItemOverlayModule());
        ModuleRegistry.register(new ModulesListModule());
        ModuleRegistry.register(new NoFireModule());
        ModuleRegistry.register(new NotificationsModule());
        ModuleRegistry.register(new PlayerInfoModule());
        ModuleRegistry.register(new PotionsModule());
        ModuleRegistry.register(new ScoreBoardModule());
        ModuleRegistry.register(new TabListModule());
        ModuleRegistry.register(new TargetHudModule());
        ModuleRegistry.register(new TotemPopModule());
        // Визуалы
        ModuleRegistry.register(new BlockHighlightModule());
        ModuleRegistry.register(new ChinaHatModule());
        ModuleRegistry.register(new FriendsRenderModule());
        ModuleRegistry.register(new HandsGlowModule());
        ModuleRegistry.register(new HitboxesModule());
        ModuleRegistry.register(new JumpCirclesModule());
        ModuleRegistry.register(new DamageNumbersModule());
        ModuleRegistry.register(new CritEffectModule());
        ModuleRegistry.register(new TrajectoryModule());
        ModuleRegistry.register(new TargetRenderModule());
        ModuleRegistry.register(new TrailsModule());
        // Частицы
        ModuleRegistry.register(new AmbientParticlesModule());
        ModuleRegistry.register(new HitBubblesModule());
        ModuleRegistry.register(new HitParticlesModule());
        ModuleRegistry.register(new TotemParticlesModule());
        // Мир
        ModuleRegistry.register(new BrightModule());
        ModuleRegistry.register(new FogModule());
        ModuleRegistry.register(new ItemPhysicsModule());
        ModuleRegistry.register(new GpsModule());
        ModuleRegistry.register(new LightModule());
        ModuleRegistry.register(new TimeModule());
        // Прочее
        ModuleRegistry.register(new AspectRatioModule());
        ModuleRegistry.register(new EndCrystalModule());
        ModuleRegistry.register(new HandTweaksModule());
        ModuleRegistry.register(new HitSoundsModule());
        ModuleRegistry.register(new KillEffectModule());
        ModuleRegistry.register(new NameProtectModule());
        ModuleRegistry.register(new TrinketModule());
        // Клиент
        ModuleRegistry.register(new FakePlayerModule());
        ModuleRegistry.register(new KeyBindModule());
        ModuleRegistry.register(new LanguageModule());
        ModuleRegistry.register(new ThemeModule());
        ModuleRegistry.register(new DiscordModule());
    }

    private static void tick(Minecraft mc) {
        ConfigManager.tick();
        if (mc.level != null) {
            Targets.tick();
            ParticleSystem.tick();
            ModuleRegistry.tick();
        }
        handleKeys(mc);
    }

    private static void handleKeys(Minecraft mc) {
        if (mc.screen == null) {
            KeyBindModule keys = ModuleRegistry.get(KeyBindModule.class);
            while (menuKey.consumeClick()) mc.setScreen(new NaoMenuScreen());
            long window = mc.getWindow().handle();
            Set<Integer> interesting = new HashSet<>();
            for (var m : ModuleRegistry.all()) if (m.bind.isBound()) interesting.add(m.bind.get());
            interesting.addAll(keys.extraKeys());
            for (int key : interesting) {
                boolean down = key <= -100
                        ? GLFW.glfwGetMouseButton(window, -100 - key) == GLFW.GLFW_PRESS
                        : InputConstants.isKeyDown(mc.getWindow(), key);
                if (down && !DOWN.contains(key)) {
                    DOWN.add(key);
                    if (!keys.handle(key)) ModuleRegistry.key(key);
                } else if (!down) DOWN.remove(key);
            }
            DOWN.removeIf(k -> !interesting.contains(k));
        } else {
            DOWN.clear();
            // гасим накопившиеся нажатия клавиши меню, пока открыт экран
            while (menuKey.consumeClick()) { /* no-op */ }
        }
    }

    public static boolean isKeyDown(int key) {
        if (key == KeybindSetting.NONE) return false;
        Minecraft mc = Minecraft.getInstance();
        if (key <= -100) return GLFW.glfwGetMouseButton(mc.getWindow().handle(), -100 - key) == GLFW.GLFW_PRESS;
        return InputConstants.isKeyDown(mc.getWindow(), key);
    }
}
