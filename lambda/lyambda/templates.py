"""Built-in content: frame presets, design / board / presentation / site templates, slide themes and layouts,
website blocks, FigJam palettes."""
import copy

from . import text as textlib
from .model import SLIDE_H, SLIDE_W, Document, Node, make_instance, solid

INK, MUTED, ACCENT, IVORY, SAND = "#141413", "#6F6E69", "#D97757", "#FAF9F5", "#F0EEE6"
SERIF = textlib.SERIF_FONT

FRAME_PRESETS = [
    ("Телефон", [("iPhone 16", 393, 852), ("iPhone 16 Pro Max", 440, 956), ("iPhone SE", 375, 667),
                 ("Android", 412, 917)]),
    ("Планшет", [("iPad mini", 744, 1133), ("iPad Pro 11″", 834, 1194), ("iPad Pro 13″", 1032, 1376)]),
    ("Компьютер", [("MacBook Air", 1280, 832), ("Компьютер", 1440, 1024), ("Full HD", 1920, 1080)]),
    ("Презентация", [("Слайд 16:9", 1920, 1080), ("Слайд 4:3", 1024, 768)]),
    ("Соцсети", [("Пост 4:5", 1080, 1350), ("Сторис", 1080, 1920), ("Обложка видео", 1280, 720)]),
    ("Бумага", [("A4", 595, 842), ("A5", 420, 595), ("Визитка", 255, 155)]),
]
STICKY_COLORS = [("Жёлтый", "#FFE29A"), ("Оранжевый", "#FFC7A1"), ("Розовый", "#FFC2D6"), ("Фиолетовый", "#D9C9FF"),
                 ("Синий", "#B8DBFF"), ("Бирюзовый", "#B5ECEB"), ("Зелёный", "#C5EBB4"), ("Серый", "#E3E1DA"),
                 ("Белый", "#FFFFFF")]
BOARD_COLORS = ["#141413", "#6F6E69", "#D97757", "#E5534B", "#F2A93B", "#4E8A5A", "#2E7DD7", "#8E5BD6", "#FFFFFF"]
STAMPS = ["👍", "❤️", "⭐", "✅", "❓", "🔥", "😂", "🎉", "👀", "➕", "💡", "🚀"]


# ====================================================================== helpers
def T(text, size=16, weight=400, color=INK, font="", **kw):
    n = Node("text", name=kw.pop("name", text.split("\n")[0][:32]), text=text, size=size, weight=weight,
             fills=[solid(color)], font=font, **kw)
    return n


def stack(direction, children=(), gap=16, pad=0, name="Стек", fill=None, **kw):
    pad = [pad] * 4 if isinstance(pad, (int, float)) else list(pad)
    kw.setdefault("hug_w", True)
    kw.setdefault("hug_h", True)
    return Node("frame", name=name, layout=direction, gap=gap, pad=pad, fills=[solid(fill)] if fill else [],
                clip=False, children=list(children), **kw)


def R(w, h, color="#D9D9D9", radius=0, name="Прямоугольник", **kw):
    return Node("rect", name=name, w=w, h=h, radius=radius, fills=[solid(color)] if color else [], **kw)


def photo(w, h, name="Изображение", radius=12, **kw):
    """A warm gradient placeholder that stands in for a picture."""
    return Node("rect", name=name, w=w, h=h, radius=radius,
                fills=[{"type": "linear", "angle": 60, "opacity": 1.0,
                        "stops": [[0, "#F2C3AE"], [0.55, "#D97757"], [1, "#8C3F27"]]}], **kw)


def layout_all(doc):
    doc.relayout()
    return doc


# ====================================================================== design
def design_blank():
    return Document("design")


def _button_component(label="Кнопка", fill=ACCENT, color="#FFFFFF", name="Кнопка / Основная"):
    c = Node("component", name=name, layout="row", gap=8, pad=[14, 24, 14, 24], hug_w=True, hug_h=True,
             radius=10, fills=[solid(fill)], align="center", justify="center", clip=False)
    c.add(T(label, 16, 600, color, name="Подпись"))
    return c


def design_mobile():
    doc = Document("design")
    page = doc.pages[0]
    page.name = "Приложение"
    btn = _button_component("Продолжить")
    btn.x, btn.y = 480, 0
    page.add(btn)
    phone = Node("frame", name="Главная", x=0, y=0, w=393, h=852, fills=[solid(IVORY)])
    col = stack("column", gap=20, pad=[64, 20, 24, 20], name="Контент", hug_h=False, hug_w=False, w=393, h=852)
    col.add(T("Доброе утро", 14, 500, MUTED))
    col.add(T("Ваши заметки", 32, 500, INK, font=SERIF))
    for title, sub in (("Идеи для поездки", "Обновлено 2 ч назад"), ("Список чтения", "12 книг"),
                       ("Рецепты", "Паста, суп, пирог")):
        card = stack("row", gap=14, pad=16, name="Карточка", fill="#FFFFFF", radius=16, hug_w=False, w=353,
                     stretch=True, align="center",
                     effects=[{"type": "shadow", "x": 0, "y": 4, "blur": 16, "color": "#141413", "opacity": 0.06}])
        card.add(photo(56, 56, radius=12))
        card.add(stack("column", [T(title, 17, 600), T(sub, 13, 400, MUTED)], gap=4, name="Текст"))
        col.add(card)
    inst = make_instance(btn)
    inst.stretch = True
    col.add(inst)
    phone.add(col)
    tab = stack("row", gap=0, pad=[10, 24, 26, 24], name="Таб-бар", fill="#FFFFFF", hug_w=False, w=393, justify="between",
                x=0, y=852 - 76, absolute=True)
    for label in ("Главная", "Поиск", "Профиль"):
        tab.add(T(label, 12, 500, ACCENT if label == "Главная" else MUTED))
    phone.add(tab)
    page.add(phone)
    second = Node("frame", name="Профиль", x=0, y=0, w=393, h=852, fills=[solid(IVORY)])
    second.x = 393 + 80
    second.y = 120
    btn.y = 0
    btn.x = 393 * 2 + 160
    av = Node("ellipse", name="Аватар", w=96, h=96, x=148, y=96, fills=[solid(ACCENT)])
    second.add(av)
    second.add(T("Анна", 28, 500, INK, font=SERIF, x=160, y=210))
    page.add(second)
    second.y = 0
    # prototype: card → profile
    col.children[2].link = {"target": second.id, "transition": "slide_left"}
    return layout_all(doc)


def design_system():
    doc = Document("design")
    page = doc.pages[0]
    page.name = "Дизайн-система"
    board = Node("frame", name="Основы", w=1200, h=900, fills=[solid("#FFFFFF")])
    board.add(T("Цвета", 28, 500, INK, font=SERIF, x=48, y=48))
    for i, (name, hexv) in enumerate((("Слоновая кость", IVORY), ("Песок", SAND), ("Терракота", ACCENT),
                                      ("Уголь", INK), ("Серый", MUTED), ("Шалфей", "#4E8A5A"))):
        board.add(R(160, 120, hexv, 16, name, x=48 + i * 184, y=104,
                    strokes=[solid("#E3DFD3")] if hexv in (IVORY, "#FFFFFF") else []))
        board.add(T(f"{name}\n{hexv}", 13, 400, MUTED, x=48 + i * 184, y=236))
    board.add(T("Типографика", 28, 500, INK, font=SERIF, x=48, y=320))
    y = 376
    for label, size, weight, font in (("Заголовок 1", 48, 500, SERIF), ("Заголовок 2", 32, 500, SERIF),
                                      ("Подзаголовок", 20, 600, ""), ("Основной текст", 16, 400, ""),
                                      ("Подпись", 13, 400, "")):
        board.add(T(f"{label} — {size}", size, weight, INK, font=font, x=48, y=y))
        y += size * 1.6 + 8
    page.add(board)
    btn = _button_component()
    btn.x, btn.y = 1280, 0
    sec = _button_component("Отмена", "#FFFFFF", INK, "Кнопка / Вторичная")
    sec.strokes = [solid("#E3DFD3")]
    sec.x, sec.y = 1280, 90
    page.add(btn)
    page.add(sec)
    card = Node("component", name="Карточка", layout="column", gap=10, pad=[20, 20, 20, 20], w=320, hug_h=True,
                radius=16, fills=[solid("#FFFFFF")], strokes=[solid("#E3DFD3")], clip=True, x=1280, y=180)
    card.add(photo(280, 160, stretch=True))
    card.add(T("Заголовок карточки", 18, 600, stretch=True, sizing="auto_h"))
    card.add(T("Короткое описание в две строки, чтобы показать перенос текста.", 14, 400, MUTED, stretch=True,
               sizing="auto_h"))
    page.add(card)
    return layout_all(doc)


# ====================================================================== board (FigJam)
def sticky(text, color="#FFE29A", x=0, y=0, size=22, w=240, h=240):
    return Node("sticky", text=text, fills=[solid(color)], x=x, y=y, size=size, w=w, h=h)


def section(name, x, y, w, h, color="#F0EEE6"):
    return Node("section", name=name, x=x, y=y, w=w, h=h, fills=[solid(color)])


def connector(a, b, route="elbow", label="", arrow="arrow"):
    return Node("connector", start={"id": a.id}, end={"id": b.id}, route=route, text=label, arrow_end=arrow)


def board_blank():
    return Document("board")


def board_brainstorm():
    doc = Document("board")
    page = doc.pages[0]
    page.name = "Мозговой штурм"
    topic = Node("shape", shape="ellipse", text="Главная тема", w=300, h=160, x=650, y=420, size=26,
                 fills=[solid(ACCENT)], strokes=[], text_color="#FFFFFF", weight=600)
    page.add(topic)
    ideas = [("Идея 1", "#FFE29A", 200, 120), ("Идея 2", "#B8DBFF", 1160, 120), ("Идея 3", "#C5EBB4", 200, 740),
             ("Идея 4", "#FFC2D6", 1160, 740), ("Вопрос?", "#D9C9FF", 680, 60)]
    for t, c, x, y in ideas:
        s = sticky(t, c, x, y)
        page.add(s)
        page.add(connector(topic, s, "curved", arrow="none"))
    page.add(T("Пишите идеи на стикерах — S, соединяйте — X", 18, 400, MUTED, x=520, y=1060))
    return layout_all(doc)


def board_retro():
    doc = Document("board")
    page = doc.pages[0]
    page.name = "Ретроспектива"
    cols = [("Что было хорошо", "#E3F2DC", "#C5EBB4"), ("Что можно улучшить", "#FCE8DF", "#FFC7A1"),
            ("Действия", "#E4ECFA", "#B8DBFF")]
    for i, (name, bg, st) in enumerate(cols):
        sec = section(name, i * 640, 0, 600, 860, bg)
        for k in range(3):
            sec.add(sticky("", st, 40 + (k % 2) * 280, 90 + (k // 2) * 270))
        page.add(sec)
    page.add(T("Ретро спринта", 40, 500, INK, font=SERIF, x=0, y=-110))
    return layout_all(doc)


def board_flowchart():
    doc = Document("board")
    page = doc.pages[0]
    page.name = "Блок-схема"
    start = Node("shape", shape="ellipse", text="Старт", x=0, y=200, w=180, h=100, fills=[solid("#C5EBB4")])
    step = Node("shape", shape="rounded", text="Заполнить форму", x=300, y=190, w=220, h=120)
    check = Node("shape", shape="diamond", text="Данные верны?", x=640, y=160, w=220, h=180, fills=[solid("#FFE29A")])
    ok = Node("shape", shape="rounded", text="Отправить", x=980, y=190, w=200, h=120)
    fix = Node("shape", shape="rounded", text="Исправить", x=640, y=460, w=220, h=110, fills=[solid("#FFC7A1")])
    end = Node("shape", shape="ellipse", text="Готово", x=1300, y=200, w=180, h=100, fills=[solid("#C5EBB4")])
    for n in (start, step, check, ok, fix, end):
        page.add(n)
    page.add(connector(start, step))
    page.add(connector(step, check))
    page.add(connector(check, ok, label="Да"))
    page.add(connector(check, fix, label="Нет"))
    c = connector(fix, step)
    c.end = {"id": step.id, "side": "bottom"}
    c.start = {"id": fix.id, "side": "left"}
    page.add(c)
    page.add(connector(ok, end))
    return layout_all(doc)


def board_kanban():
    doc = Document("board")
    page = doc.pages[0]
    page.name = "Канбан"
    cols = [("Идеи", "#FFE29A"), ("В работе", "#B8DBFF"), ("Проверка", "#D9C9FF"), ("Готово", "#C5EBB4")]
    tasks = [["Новый логотип", "Опрос пользователей"], ["Макет главной", "Тексты"], ["Прототип"], ["Исследование"]]
    for i, (name, color) in enumerate(cols):
        sec = section(name, i * 380, 0, 340, 900)
        for k, t in enumerate(tasks[i]):
            sec.add(sticky(t, color, 30, 90 + k * 200, w=280, h=170))
        page.add(sec)
    return layout_all(doc)


# ====================================================================== slides
THEMES = [
    {"name": "Слоновая кость", "bg": IVORY, "text": INK, "muted": MUTED, "accent": ACCENT, "on_accent": "#FFFFFF",
     "heading": SERIF, "body": ""},
    {"name": "Уголь", "bg": "#1F1E1D", "text": "#F4F2EC", "muted": "#A6A39A", "accent": ACCENT,
     "on_accent": "#FFFFFF", "heading": SERIF, "body": ""},
    {"name": "Терракота", "bg": ACCENT, "text": "#FFFFFF", "muted": "#FBE3D8", "accent": INK, "on_accent": "#FFFFFF",
     "heading": SERIF, "body": ""},
    {"name": "Шалфей", "bg": "#E8EDE4", "text": "#24321F", "muted": "#5E6B58", "accent": "#4E8A5A",
     "on_accent": "#FFFFFF", "heading": SERIF, "body": ""},
    {"name": "Ночь", "bg": "#14213D", "text": "#F5F5F5", "muted": "#AAB4C8", "accent": "#FCA311",
     "on_accent": "#14213D", "heading": "", "body": ""},
    {"name": "Бумага", "bg": "#FFFFFF", "text": "#111111", "muted": "#666666", "accent": "#2E5E9E",
     "on_accent": "#FFFFFF", "heading": "", "body": ""},
]


def apply_role(n, theme):
    r = n.role
    if r == "bg":
        n.fills = [solid(theme["bg"])]
    elif r in ("title", "kicker"):
        n.fills = [solid(theme["text"] if r == "title" else theme["accent"])]
        n.font = theme["heading"] if r == "title" else theme["body"]
    elif r == "body":
        n.fills = [solid(theme["text"])]
        n.font = theme["body"]
    elif r == "muted":
        n.fills = [solid(theme["muted"])]
        n.font = theme["body"]
    elif r == "accent":
        n.fills = [solid(theme["accent"])]
    elif r == "on_accent":
        n.fills = [solid(theme["on_accent"])]
        n.font = theme["heading"]


def apply_theme(doc, theme):
    doc.theme = dict(theme)
    for page in doc.pages:
        for slide in page.children:
            for n in slide.walk():
                apply_role(n, theme)


LAYOUTS = [("title", "Титульный"), ("title_body", "Заголовок и текст"), ("two_columns", "Две колонки"),
           ("section", "Раздел"), ("quote", "Цитата"), ("image", "Текст и картинка"), ("big_number", "Большое число"),
           ("blank", "Пустой")]


def make_slide(layout="title_body", theme=None, title=None, body=None):
    theme = theme or THEMES[0]
    s = Node("frame", name="Слайд", w=SLIDE_W, h=SLIDE_H, role="bg", clip=True)

    def tx(text, size, role, x, y, w=None, weight=400, align="left", **kw):
        n = T(text, size, weight, x=x, y=y, role=role, talign=align, **kw)
        if w:
            n.w = w
            n.sizing = "auto_h"
        s.add(n)
        return n
    if layout == "title":
        tx(title or "Название презентации", 120, "title", 160, 340, 1600, 500, line_height=110)
        tx(body or "Подзаголовок · имя автора · дата", 40, "muted", 160, 640, 1600)
        s.add(R(160, 8, None, 0, "Акцент", x=160, y=300, role="accent"))
    elif layout == "title_body":
        tx(title or "Заголовок слайда", 80, "title", 160, 140, 1600, 500)
        tx(body or "• Первый тезис — коротко и по делу\n• Второй тезис с важной цифрой\n• Третий тезис и вывод",
           44, "body", 160, 380, 1600, line_height=150)
    elif layout == "two_columns":
        tx(title or "Сравнение", 80, "title", 160, 140, 1600, 500)
        tx("Было", 36, "kicker", 160, 360, 740, 600)
        tx(body or "Ручная работа, долгие согласования, файлы по почте.", 40, "body", 160, 430, 740, line_height=140)
        tx("Стало", 36, "kicker", 1020, 360, 740, 600)
        tx("Один файл, понятный процесс, всё в одном месте.", 40, "body", 1020, 430, 740, line_height=140)
    elif layout == "section":
        s.add(R(SLIDE_W, SLIDE_H, None, 0, "Фон раздела", role="accent"))
        tx("01", 64, "on_accent", 160, 320, 1600, 500)
        tx(title or "Новый раздел", 140, "on_accent", 160, 420, 1600, 500)
    elif layout == "quote":
        tx("«", 240, "kicker", 140, 120, None, 500, font=SERIF)
        tx(body or "Хороший дизайн — это как можно меньше дизайна.", 84, "title", 240, 340, 1440, 500,
           line_height=120)
        tx("— Дитер Рамс", 40, "muted", 240, 700, 1440)
    elif layout == "image":
        tx(title or "Картинка и мысль", 80, "title", 160, 200, 760, 500, line_height=110)
        tx(body or "Расскажите, что на картинке и почему это важно.", 40, "body", 160, 480, 760, line_height=140)
        s.add(photo(800, 800, x=1000, y=140, radius=32))
    elif layout == "big_number":
        tx(title or "87%", 320, "kicker", 160, 220, 1600, 500)
        tx(body or "пользователей вернулись в первую неделю", 56, "body", 160, 640, 1600)
    for n in s.walk():
        apply_role(n, theme)
    s.name = dict(LAYOUTS).get(layout, "Слайд")
    return s


def slides_doc(slides, theme=None):
    doc = Document("slides")
    theme = theme or THEMES[0]
    doc.theme = dict(theme)
    page = doc.pages[0]
    page.name = "Слайды"
    for layout, title, body in slides:
        page.add(make_slide(layout, theme, title, body))
    return layout_all(doc)


def slides_blank():
    return slides_doc([("title", None, None)])


def slides_pitch():
    return slides_doc([
        ("title", "Лямбда", "Дизайн, доски, слайды и сайты — в одном приложении"),
        ("title_body", "Проблема", "• Инструменты разбросаны по разным сервисам\n• Нужен интернет и подписка\n"
                                   "• Файлы живут не у вас"),
        ("image", "Решение", "Одно приложение для Mac, которое работает без сети и хранит файлы у вас."),
        ("big_number", "4 в 1", "дизайн · доска · презентации · сайты"),
        ("two_columns", "До и после", None),
        ("quote", None, None),
        ("section", "Спасибо!", None),
    ], THEMES[1])


def slides_report():
    return slides_doc([
        ("title", "Итоги квартала", "Команда продукта · октябрь"),
        ("section", "Цифры", None),
        ("big_number", "+24%", "рост активных пользователей"),
        ("title_body", "Что сделали", "• Запустили новую главную\n• Ускорили загрузку в 2 раза\n• Провели 30 интервью"),
        ("title_body", "Планы", "• Мобильная версия\n• Экспорт в PDF\n• Командные шаблоны"),
    ], THEMES[3])


# ====================================================================== site
def button(label, href="#", primary=True, link_target=None):
    b = stack("row", [T(label, 16, 600, "#FFFFFF" if primary else INK, name="Подпись")], gap=8,
              pad=[14, 26, 14, 26], name="Кнопка", fill=ACCENT if primary else "#FFFFFF", radius=10,
              align="center", justify="center", href="" if link_target else href,
              hover={"opacity": 0.85})
    if not primary:
        b.strokes = [solid("#E3DFD3")]
    if link_target:
        b.link = {"target": link_target}
    return b


def site_section(name, children, fill="#FFFFFF", pad=(96, 80, 96, 80), gap=32, align="center"):
    sec = Node("frame", name=name, role="section", layout="column", gap=gap, pad=list(pad), stretch=True, hug_h=True,
               fills=[solid(fill)] if fill else [], align=align, clip=False, w=1440)
    for c in children:
        sec.add(c)
    return sec


def container(children, gap=24, direction="column", max_w=1120, align="start", stack_mobile=False, **kw):
    c = stack(direction, children, gap=gap, name="Контейнер", stretch=True, max_w=max_w, hug_w=False, align=align,
              stack=stack_mobile, **kw)
    c.w = max_w
    return c


def para(text, size=18, color=MUTED, **kw):
    return T(text, size, 400, color, stretch=True, sizing="auto_h", line_height=160, **kw)


def block_nav(pages=None):
    links = stack("row", gap=32, name="Ссылки", align="center", stack=False)
    for title, target in (pages or [("О нас", None), ("Работы", None), ("Контакты", None)]):
        t = T(title, 16, 500, INK, name=title, hover={"opacity": 0.6})
        if target:
            t.link = {"target": target}
        links.add(t)
    logo = T("λ Студия", 22, 500, INK, font=SERIF, name="Логотип")
    row = container([logo, links], gap=24, direction="row", align="center", justify="between")
    return site_section("Навигация", [row], fill=IVORY, pad=(24, 80, 24, 80))


def block_hero(title="Делаем понятные цифровые продукты",
               sub="Небольшая студия: исследуем, проектируем и запускаем сайты и приложения, которыми приятно пользоваться."):
    h1 = T(title, 64, 500, INK, font=SERIF, tag="h1", stretch=True, sizing="auto_h", talign="center", line_height=110)
    p = T(sub, 20, 400, MUTED, stretch=True, sizing="auto_h", talign="center", line_height=160)
    buttons = stack("row", [button("Начать проект"), button("Посмотреть работы", primary=False)], gap=16,
                    name="Кнопки", stack=True)
    inner = container([h1, p, buttons], gap=28, max_w=860, align="center")
    return site_section("Обложка", [inner, photo(1120, 520, radius=24, stretch=True, max_w=1120)], fill=IVORY,
                        pad=(80, 80, 112, 80), gap=56)


def block_features():
    cards = stack("row", gap=24, name="Карточки", stretch=True, hug_w=False, stack=True)
    for title, text in (("Исследование", "Говорим с людьми и находим, что им на самом деле нужно."),
                        ("Дизайн", "Собираем интерфейс из понятных и аккуратных компонентов."),
                        ("Запуск", "Доводим до релиза и смотрим на результат в цифрах.")):
        card = stack("column", [Node("ellipse", name="Значок", w=48, h=48, fills=[solid(ACCENT)]),
                                T(title, 22, 600, INK, stretch=True, sizing="auto_h", tag="h3"),
                                para(text, 16)], gap=14, pad=28, name="Карточка", fill="#FFFFFF", radius=20,
                     grow=True, hug_w=False, strokes=[solid("#E3DFD3")])
        cards.add(card)
    head = T("Что мы делаем", 44, 500, INK, font=SERIF, tag="h2", stretch=True, sizing="auto_h")
    return site_section("Преимущества", [container([head, cards], gap=40)], fill="#FFFFFF")


def block_text(title="О студии", body="Мы — команда дизайнеров и разработчиков. Работаем спокойно и внимательно: "
                                     "без лишних встреч, с понятными сроками и честной оценкой.\n\nКаждый проект "
                                     "начинаем с разговора — расскажите, что хотите сделать."):
    return site_section("Текст", [container([T(title, 44, 500, INK, font=SERIF, tag="h2", stretch=True,
                                                sizing="auto_h"), para(body, 19)], gap=20, max_w=760)])


def block_gallery():
    row = stack("row", [photo(360, 280, grow=True, name="Фото 1"), photo(360, 280, grow=True, name="Фото 2"),
                        photo(360, 280, grow=True, name="Фото 3")], gap=20, name="Галерея", stretch=True,
                hug_w=False, stack=True)
    head = T("Работы", 44, 500, INK, font=SERIF, tag="h2", stretch=True, sizing="auto_h")
    return site_section("Галерея", [container([head, row], gap=36)], fill=SAND)


def block_quote():
    q = T("«С ними легко: всё объяснили, сделали в срок и даже чуть раньше»", 36, 500, INK, font=SERIF,
          stretch=True, sizing="auto_h", talign="center", line_height=130)
    who = T("Мария, основатель кофейни «Зерно»", 16, 400, MUTED, stretch=True, sizing="auto_h", talign="center")
    return site_section("Отзыв", [container([q, who], gap=20, max_w=860, align="center")], fill=IVORY)


def block_pricing():
    row = stack("row", gap=24, name="Тарифы", stretch=True, hug_w=False, stack=True)
    for name, price, items, primary in (("Старт", "40 000 ₽", "Лендинг\nДо 5 блоков\n2 недели", False),
                                        ("Бизнес", "120 000 ₽", "Сайт до 10 страниц\nДизайн-система\n6 недель", True),
                                        ("Продукт", "по запросу", "Приложение\nИсследование\nПоддержка", False)):
        card = stack("column", [T(name, 20, 600, INK), T(price, 36, 500, INK, font=SERIF), para(items, 16),
                                button("Выбрать", primary=primary)], gap=16, pad=28, name=f"Тариф {name}",
                     fill="#FFFFFF", radius=20, grow=True, hug_w=False,
                     strokes=[solid(ACCENT if primary else "#E3DFD3")], stroke_width=2 if primary else 1)
        row.add(card)
    head = T("Цены", 44, 500, INK, font=SERIF, tag="h2", stretch=True, sizing="auto_h", talign="center")
    return site_section("Цены", [container([head, row], gap=40)], fill=SAND)


def block_cta():
    inner = container([T("Готовы начать?", 48, 500, "#FFFFFF", font=SERIF, tag="h2", stretch=True, sizing="auto_h",
                         talign="center"),
                       T("Напишите нам — ответим в течение дня.", 20, 400, "#FBE3D8", stretch=True, sizing="auto_h",
                         talign="center"),
                       button("hello@studio.ru", "mailto:hello@studio.ru", primary=False)], gap=24, max_w=760,
                      align="center")
    return site_section("Призыв", [inner], fill=ACCENT)


def block_footer():
    row = container([T("© 2026 λ Студия", 14, 400, "#A6A39A"),
                     stack("row", [T("Телеграм", 14, 400, "#F4F2EC", href="https://t.me/", hover={"opacity": 0.6}),
                                   T("Почта", 14, 400, "#F4F2EC", href="mailto:hello@studio.ru",
                                     hover={"opacity": 0.6})], gap=24, name="Ссылки")],
                    direction="row", align="center", justify="between", stack_mobile=True)
    return site_section("Подвал", [row], fill=INK, pad=(40, 80, 40, 80))


BLOCKS = [("nav", "Навигация", block_nav), ("hero", "Обложка", block_hero), ("features", "Преимущества", block_features),
          ("text", "Текст", block_text), ("gallery", "Галерея", block_gallery), ("quote", "Отзыв", block_quote),
          ("pricing", "Цены", block_pricing), ("cta", "Призыв к действию", block_cta), ("footer", "Подвал", block_footer)]


def webpage(name):
    return Node("frame", name=name, role="webpage", layout="column", hug_h=True, w=1440, h=900,
                fills=[solid("#FFFFFF")], clip=False)


def site_doc(pages):
    """pages: [(name, [block keys])]; navigation links point at the pages."""
    doc = Document("site")
    doc.pages = []
    for name, _ in pages:
        p = Node("page", name=name)
        p.add(webpage(name))
        doc.pages.append(p)
    nav_targets = [(p.name, p.id) for p in doc.pages[1:]] or None
    builders = {k: f for k, _, f in BLOCKS}
    for p, (_, keys) in zip(doc.pages, pages):
        root = p.children[0]
        for k in keys:
            root.add(block_nav(nav_targets) if k == "nav" else builders[k]())
        if keys and keys[0] == "nav" and len(doc.pages) > 1:  # the logo leads home
            logo = root.children[0].children[0].children[0]
            logo.link = {"target": doc.pages[0].id}
    doc.invalidate()
    return layout_all(doc)


def site_blank():
    return site_doc([("Главная", ["nav", "hero"])])


def site_landing():
    return site_doc([("Главная", ["nav", "hero", "features", "quote", "pricing", "cta", "footer"]),
                     ("О нас", ["nav", "text", "gallery", "footer"])])


def site_portfolio():
    return site_doc([("Главная", ["nav", "hero", "gallery", "text", "cta", "footer"])])


TEMPLATES = {
    "design": [("blank", "Пустой файл", design_blank), ("mobile", "Мобильное приложение", design_mobile),
               ("system", "Дизайн-система", design_system)],
    "board": [("blank", "Пустая доска", board_blank), ("brainstorm", "Мозговой штурм", board_brainstorm),
              ("retro", "Ретроспектива", board_retro), ("flowchart", "Блок-схема", board_flowchart),
              ("kanban", "Канбан", board_kanban)],
    "slides": [("blank", "Пустая презентация", slides_blank), ("pitch", "Питч", slides_pitch),
               ("report", "Отчёт", slides_report)],
    "site": [("blank", "Пустой сайт", site_blank), ("landing", "Лендинг", site_landing),
             ("portfolio", "Портфолио", site_portfolio)],
}


def new_document(kind, key="blank"):
    for k, _, f in TEMPLATES[kind]:
        if k == key:
            return f()
    return TEMPLATES[kind][0][2]()


def clone_block(key):
    for k, _, f in BLOCKS:
        if k == key:
            return f()
    return None


def theme_by_name(name):
    return copy.deepcopy(next((t for t in THEMES if t["name"] == name), THEMES[0]))
