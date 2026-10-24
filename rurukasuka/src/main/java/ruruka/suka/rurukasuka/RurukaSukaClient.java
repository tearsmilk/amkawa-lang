package ruruka.suka.rurukasuka;

import ruruka.suka.rurukasuka.account.RurukaAccount;
import ruruka.suka.rurukasuka.account.SessionStore;
import ruruka.suka.rurukasuka.net.SiteApi;
import ruruka.suka.rurukasuka.render.CosmeticLayer;
import ruruka.suka.rurukasuka.render.CosmeticManager;
import ruruka.suka.rurukasuka.render.SkinLoader;
import net.fabricmc.fabric.api.client.rendering.v1.LivingEntityFeatureRendererRegistrationCallback;
import net.minecraft.client.model.player.PlayerModel;
import net.minecraft.client.renderer.entity.RenderLayerParent;
import net.minecraft.client.renderer.entity.player.AvatarRenderer;
import net.minecraft.client.renderer.entity.state.AvatarRenderState;
import ruruka.suka.rurukasuka.ui.AccountScreen;
import ruruka.suka.rurukasuka.ui.PlayerPreview;
import ruruka.suka.rurukasuka.ui.WardrobeScreen;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.screen.v1.ScreenEvents;
import net.fabricmc.fabric.api.client.screen.v1.Screens;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.PauseScreen;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.network.chat.Component;

/**
 * Клиентская точка входа. Через Fabric ScreenEvents (без миксинов) добавляет в главное меню
 * правый столбик кнопок и рендерит превью игрока слева. Имена — официальные Mojang mappings.
 */
public class RurukaSukaClient implements ClientModInitializer {

    @Override
    public void onInitializeClient() {
        RurukaSuka.LOGGER.info("RurukaSuka starting up — meow");

        restoreSession();
        CosmeticManager.startPoller();
        ruruka.suka.rurukasuka.discord.DiscordPresence.start();

        LivingEntityFeatureRendererRegistrationCallback.EVENT.register((entityType, renderer, helper, ctx) -> {
            if (renderer instanceof AvatarRenderer) {
                @SuppressWarnings("unchecked")
                RenderLayerParent<AvatarRenderState, PlayerModel> parent =
                        (RenderLayerParent<AvatarRenderState, PlayerModel>) renderer;
                helper.register(new CosmeticLayer(parent));
            }
        });

        ScreenEvents.AFTER_INIT.register((client, screen, scaledWidth, scaledHeight) -> {
            if (screen instanceof TitleScreen) {
                // якорь — верхняя ванильная кнопка (ширина >=200); привязываемся к ней, чтобы
                // при смене размера интерфейса наши кнопки/модель двигались вместе с ванильными
                AbstractWidget anchor = null;
                for (AbstractWidget w : Screens.getButtons(screen))
                    if (w.getWidth() >= 200 && (anchor == null || w.getY() < anchor.getY())) anchor = w;
                int baseX = anchor != null ? anchor.getX() : scaledWidth / 2 - 100;
                int baseY = anchor != null ? anchor.getY() : scaledHeight / 4 + 48;
                int rowH = 24;

                addTitleButtons(client, screen, baseX + 236, baseY, rowH);

                // 3D-моделька симметрично слева (правый край ~ зеркало левого края кнопок)
                int mw = Math.round(90 / 1.7f), mh = Math.round(180 / 1.7f);
                var model = PlayerPreview.widget(mw, mh);
                model.setPosition(Math.max(8, baseX - 36 - mw), baseY + 34 - mh / 2);
                Screens.getButtons(screen).add(model);
            } else if (screen instanceof PauseScreen) {
                // убрать кнопки «Хост» и «Скриншоты» из меню паузы
                Screens.getButtons(screen).removeIf(w -> {
                    String t = w.getMessage().getString().toLowerCase();
                    return t.contains("lan") || t.contains("host") || t.contains("хост")
                            || t.contains("screenshot") || t.contains("скриншот") || t.contains("снимок");
                });
                // кнопка «Гардероб» в меню ESC (правый верхний угол)
                Button wardrobe = Button.builder(Component.translatable("rurukasuka.button.wardrobe"),
                        b -> client.setScreen(new WardrobeScreen(screen)))
                        .bounds(scaledWidth - 124, 8, 116, 20).build();
                Screens.getButtons(screen).add(wardrobe);
            }
        });
    }

    private void restoreSession() {
        String token = SessionStore.load();
        if (token == null) return;
        new Thread(() -> {
            try {
                SiteApi.Session s = SiteApi.me(token);
                Minecraft.getInstance().execute(() -> {
                    RurukaAccount.LOCAL.applyLogin(s.token(), s.uuid(), s.nick(), s.balance(), s.owned(), s.equipped(), s.variants());
                    SkinLoader.loadFrom(s.skin() == null ? null : RurukaSuka.abs(s.skin()), s.skinModel());
                });
            } catch (Exception e) {
                SessionStore.clear();
            }
        }, "RurukaSuka-restore").start();
    }

    private void addTitleButtons(Minecraft client, Screen screen, int x, int y, int rowH) {
        final int w = 100, h = 20;
        String[][] items = {
                {"rurukasuka.button.social", "social"},
                {"rurukasuka.button.wardrobe", "wardrobe"},
                {"rurukasuka.button.account", "account"},
        };
        for (String[] item : items) {
            final String action = item[1];
            Button b = Button.builder(Component.translatable(item[0]), btn -> onAction(client, screen, action))
                    .bounds(x, y, w, h)
                    .build();
            Screens.getButtons(screen).add(b);
            y += rowH;
        }
    }

    private void onAction(Minecraft client, Screen parent, String action) {
        switch (action) {
            case "wardrobe" -> client.setScreen(new WardrobeScreen(parent));
            case "account" -> client.setScreen(new AccountScreen(parent));
            case "social" -> client.setScreen(new ruruka.suka.rurukasuka.ui.FriendsScreen(parent));
            // TODO: host / pictures / settings
            default -> RurukaSuka.LOGGER.info("RurukaSuka: action '{}' ещё не реализован", action);
        }
    }
}
