package milk.naovisual.core.util;

/** Доп. поля состояния рендера предмета-сущности (добавляются миксином): лежит ли на земле и стабильный поворот. */
public interface ItemPhysicsState {
    boolean naovisual$onGround();
    void naovisual$setOnGround(boolean v);
    float naovisual$yaw();
    void naovisual$setYaw(float v);
}
