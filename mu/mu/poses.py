"""Ready-made poses and expressions (standard Cubism parameter ids). Arm / leg values are degrees: the rest
pose has the arms hanging; for the character's left arm (viewer's right) negative shoulder values raise it,
for the right arm positive values do."""

POSES = [
    ("Стоит", "Поза", {}),
    ("Привет!", "Поза", {"ParamArmRA": 97, "ParamArmRB": 118, "ParamHandR": 10, "ParamMouthForm": 1,
                         "ParamMouthOpenY": 0.5, "ParamAngleZ": -8, "ParamBodyAngleZ": -3, "ParamEyeBallX": 0.2,
                         "ParamCheek": 0.4}),
    ("Ура!", "Поза", {"ParamArmLA": -160, "ParamArmLB": -12, "ParamArmRA": 160, "ParamArmRB": 12,
                      "ParamMouthOpenY": 1, "ParamMouthForm": 1, "ParamEyeLSmile": 1, "ParamEyeRSmile": 1,
                      "ParamEyeLOpen": 0, "ParamEyeROpen": 0, "ParamBrowLY": 0.6, "ParamBrowRY": 0.6,
                      "ParamAngleY": 12}),
    ("Руки на поясе", "Поза", {"ParamArmLA": -32, "ParamArmLB": 101, "ParamArmRA": 32, "ParamArmRB": -101,
                               "ParamMouthForm": 0.6, "ParamBrowLAngle": 0.3, "ParamBrowRAngle": 0.3,
                               "ParamAngleZ": 6}),
    ("Задумалась", "Поза", {"ParamArmRA": -81, "ParamArmRB": -153, "ParamHandR": -10, "ParamAngleZ": 12,
                            "ParamAngleY": 10, "ParamEyeBallX": 0.6, "ParamEyeBallY": 0.7, "ParamMouthForm": -0.2,
                            "ParamBrowLY": 0.3}),
    ("Указывает", "Поза", {"ParamArmLA": -100, "ParamArmLB": -6, "ParamHandL": -8, "ParamAngleX": 18,
                           "ParamEyeBallX": 0.8, "ParamMouthOpenY": 0.4, "ParamMouthForm": 0.6,
                           "ParamBodyAngleX": 4}),
    ("Шаг вперёд", "Поза", {"ParamLegL": -14, "ParamKneeL": 18, "ParamLegR": 8, "ParamArmLA": 14,
                            "ParamArmRA": 14, "ParamBodyAngleZ": 2, "ParamMouthForm": 0.5}),
    ("Пис ✌", "Поза", {"ParamArmLA": -106, "ParamArmLB": -143, "ParamHandL": 10, "ParamEyeLOpen": 0,
                         "ParamEyeLSmile": 1, "ParamMouthForm": 1, "ParamMouthOpenY": 0.3, "ParamAngleZ": 10,
                         "ParamCheek": 0.5}),
    ("Улыбка", "Эмоция", {"ParamMouthForm": 1, "ParamEyeLSmile": 0.5, "ParamEyeRSmile": 0.5, "ParamCheek": 0.3}),
    ("Счастье ^^", "Эмоция", {"ParamEyeLOpen": 0, "ParamEyeROpen": 0, "ParamEyeLSmile": 1, "ParamEyeRSmile": 1,
                              "ParamMouthForm": 1, "ParamMouthOpenY": 0.7, "ParamCheek": 0.7, "ParamBrowLY": 0.5,
                              "ParamBrowRY": 0.5}),
    ("Подмигивание", "Эмоция", {"ParamEyeROpen": 0, "ParamEyeRSmile": 1, "ParamMouthForm": 1,
                                "ParamMouthOpenY": 0.2, "ParamAngleZ": -6, "ParamCheek": 0.3}),
    ("Удивление", "Эмоция", {"ParamEyeLOpen": 1.2, "ParamEyeROpen": 1.2, "ParamMouthOpenY": 0.9,
                             "ParamMouthForm": -0.6, "ParamBrowLY": 1, "ParamBrowRY": 1, "ParamAngleY": 6}),
    ("Сердится", "Эмоция", {"ParamBrowLAngle": 1, "ParamBrowRAngle": 1, "ParamBrowLY": -0.6, "ParamBrowRY": -0.6,
                            "ParamMouthForm": -1, "ParamMouthOpenY": 0.25, "ParamEyeLOpen": 0.8,
                            "ParamEyeROpen": 0.8, "ParamAngleY": -8}),
    ("Смущение", "Эмоция", {"ParamCheek": 1, "ParamEyeBallY": -0.8, "ParamEyeBallX": -0.4, "ParamMouthForm": 0.3,
                            "ParamAngleY": -12, "ParamAngleZ": 8, "ParamBrowLAngle": -0.6, "ParamBrowRAngle": -0.6}),
    ("Грусть", "Эмоция", {"ParamBrowLAngle": -1, "ParamBrowRAngle": -1, "ParamBrowLY": 0.3, "ParamBrowRY": 0.3,
                          "ParamMouthForm": -1, "ParamEyeLOpen": 0.7, "ParamEyeROpen": 0.7, "ParamAngleY": -14,
                          "ParamEyeBallY": -0.6}),
    ("Сонная", "Эмоция", {"ParamEyeLOpen": 0.35, "ParamEyeROpen": 0.35, "ParamAngleZ": 14, "ParamMouthOpenY": 0.3,
                          "ParamMouthForm": 0.2, "ParamBrowLY": -0.3, "ParamBrowRY": -0.3}),
]


def preset_names():
    return [n for n, _, _ in POSES]


def preset_values(name):
    for n, _, v in POSES:
        if n == name:
            return dict(v)
    return {}


def apply_pose(model, values, reset=True, blend=1.0):
    """Set the model's parameter values to a pose (unknown ids are ignored)."""
    base = {p.id: p.default for p in model.params} if reset else dict(model.values)
    for pid, v in values.items():
        p = model.param(pid)
        if p is not None:
            base[pid] = p.clamp(base[pid] + (v - base[pid]) * blend)
    model.values.update(base)


def add_default_poses(model):
    """Store the presets inside the model as editable poses."""
    if not model.poses:
        model.poses = [{"name": n, "kind": k, "values": dict(v)} for n, k, v in POSES]
