"""Recognise pasted code and guess its language (pygments lexer alias)."""
import json
import re

# (language, pattern, weight) — cheap, predictable signals that beat pygments' guesser on snippets
_RULES = [
    ("python", r"^\s*(def|class)\s+\w+.*:\s*$", 3), ("python", r"^\s*(from\s+[\w.]+\s+)?import\s+[\w.]+", 2),
    ("python", r"\bself\b|\belif\b|\bNone\b|print\(|__name__", 1), ("python", r"^\s*@\w+", 1),
    ("javascript", r"\b(const|let|var)\s+\w+\s*=", 2), ("javascript", r"=>|console\.log|function\s*\w*\(", 2),
    ("javascript", r"\b(require\(|module\.exports|document\.|window\.)", 2),
    ("typescript", r":\s*(string|number|boolean|any)\b|interface\s+\w+\s*\{|\bimport\s+type\b", 3),
    ("html", r"<!doctype html|<html|<div[\s>]|<span[\s>]|<body|</\w+>", 3),
    ("css", r"^[\w.#:\-\s,>*\[\]=\"']+\{\s*$|^\s*[\w-]+\s*:\s*[^;]+;\s*$", 2),
    ("json", r"^\s*[\[{]", 0),
    ("sql", r"\b(SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|CREATE\s+TABLE)\b", 3), ("sql", r"\bFROM\b|\bWHERE\b", 1),
    ("bash", r"^#!.*\b(ba|z)?sh\b|^\s*\$ |\b(sudo|apt|brew|echo|grep|chmod|export)\s", 2), ("bash", r"\bfi\b|\bdone\b|\$\{?\w+", 1),
    ("c", r"#include\s*<\w+\.h>|\bprintf\(|\bmalloc\(", 3),
    ("cpp", r"#include\s*<(iostream|vector|string)>|std::|\bcout\b|template\s*<", 4),
    ("java", r"\bpublic\s+(static\s+)?(class|void)\b|System\.out\.println", 4),
    ("csharp", r"\busing\s+System\b|\bnamespace\s+\w+|Console\.WriteLine", 4),
    ("go", r"^package\s+\w+|\bfunc\s+\w+\(|fmt\.Print", 4),
    ("rust", r"\bfn\s+\w+\(|\blet\s+mut\b|println!\(|impl\s+\w+", 4),
    ("swift", r"\bimport\s+(SwiftUI|UIKit|Foundation)\b|\bfunc\s+\w+\(.*\)\s*->|\bguard\s+let\b", 4),
    ("kotlin", r"\bfun\s+\w+\(|\bval\s+\w+\s*=", 3),
    ("php", r"<\?php|\$\w+\s*=|->\w+\(", 3),
    ("ruby", r"^\s*def\s+\w+[^:]*$|^\s*end\s*$|\bputs\b|\.each\s+do\b", 2),
    ("lua", r"\blocal\s+\w+\s*=|\bfunction\s+\w+[.:]?\w*\(|\bthen\b|\bend\b", 2),
    ("yaml", r"^[\w-]+:\s+\S.*$|^\s+- \w+", 1),
    ("dockerfile", r"^(FROM|RUN|COPY|CMD|ENTRYPOINT|WORKDIR)\s", 4),
]
_COMPILED = [(lang, re.compile(p, re.M | (re.I if lang == "sql" else 0)), w) for lang, p, w in _RULES]

_CODE_SIGNS = re.compile(r"[{};]\s*$|^\s{2,}\S|^\s*(def|class|function|import|from|#include|const|let|var|return|if\s*\(|for\s*\(|<\w+)|=>|::|\(\)|==|!=|\w+\(.*\)\s*;?\s*$", re.M)


def looks_like_code(text: str) -> bool:
    lines = [l for l in text.strip("\n").splitlines() if l.strip()]
    if not lines:
        return False
    if text.lstrip().startswith("```"):
        return False
    if len(lines) == 1:
        line = lines[0]
        return bool(re.search(r"[;{}]\s*$|=>|^\s*(def|class|import|SELECT|#include)\b", line)) and len(line) < 200
    if lines[0].startswith("#!") or any(w >= 3 and rx.search(text) for _, rx, w in _COMPILED):
        return True
    hits = sum(1 for l in lines if _CODE_SIGNS.search(l))
    prose = sum(1 for l in lines if re.search(r"[а-яa-z]{3,}[,.!?]\s+[А-ЯA-Zа-яa-z]", l) and not _CODE_SIGNS.search(l))
    return hits >= max(2, len(lines) * 0.4) and prose < len(lines) * 0.5


def detect_language(text: str) -> str:
    stripped = text.strip()
    if stripped[:1] in "[{":
        try:
            json.loads(stripped)
            return "json"
        except Exception:
            pass
    scores = {}
    for lang, rx, weight in _COMPILED:
        if weight:
            n = len(rx.findall(text))
            if n:
                scores[lang] = scores.get(lang, 0) + weight * min(n, 5)
    if scores.get("typescript") and scores.get("javascript"):
        scores["typescript"] += scores["javascript"]
    if scores.get("cpp"):
        scores["cpp"] += scores.get("c", 0)
    if scores:
        best = max(scores, key=scores.get)
        if scores[best] >= 2:
            return best
    try:
        from pygments.lexers import guess_lexer

        lexer = guess_lexer(text)
        if lexer.aliases and lexer.name not in ("Text only", "Text output"):
            return lexer.aliases[0]
    except Exception:
        pass
    return "text"


LANG_NAMES = {
    "python": "Python", "javascript": "JavaScript", "typescript": "TypeScript", "html": "HTML", "css": "CSS",
    "json": "JSON", "sql": "SQL", "bash": "Bash", "c": "C", "cpp": "C++", "java": "Java", "csharp": "C#",
    "go": "Go", "rust": "Rust", "swift": "Swift", "kotlin": "Kotlin", "php": "PHP", "ruby": "Ruby",
    "lua": "Lua", "yaml": "YAML", "dockerfile": "Dockerfile", "markdown": "Markdown", "text": "Текст",
}


def pretty_name(lang: str) -> str:
    return LANG_NAMES.get((lang or "").lower(), (lang or "code").capitalize())
