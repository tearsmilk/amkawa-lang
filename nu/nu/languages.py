"""Languages: file → language, Pygments lexer, comment tokens, icon badge, how to run.

Pygments knows ~500 languages; the table below adds what an editor needs on top of it for the common ones.
"""
import fnmatch
import shlex
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Language:
    id: str
    name: str
    lexer: str               # Pygments alias
    patterns: tuple          # file name globs
    comment: str = ""        # line comment
    block: tuple = ()        # (open, close) block comment
    badge: str = ""          # 1–3 letters for the file icon
    color: str = "#8A8780"
    run: str = ""            # shell command template: {file} {dir} {stem} {out}
    indent_after: str = ""   # line endings that open an indented block


L = Language
LANGUAGES = [
    L("python", "Python", "python", ("*.py", "*.pyw", "*.pyi", "SConstruct", "*.gyp"), "#", ('"""', '"""'), "py", "#3A76A8",
      "python3 {file}", ":"),
    L("javascript", "JavaScript", "javascript", ("*.js", "*.mjs", "*.cjs"), "//", ("/*", "*/"), "JS", "#C9A227", "node {file}", "{[("),
    L("jsx", "JavaScript JSX", "jsx", ("*.jsx",), "//", ("/*", "*/"), "JSX", "#3A97A8", "", "{[("),
    L("typescript", "TypeScript", "typescript", ("*.ts", "*.mts", "*.cts"), "//", ("/*", "*/"), "TS", "#3178C6",
      "npx --yes tsx {file}", "{[("),
    L("tsx", "TypeScript JSX", "typescript", ("*.tsx",), "//", ("/*", "*/"), "TSX", "#3178C6", "", "{[("),
    L("html", "HTML", "html", ("*.html", "*.htm", "*.xhtml"), "", ("<!--", "-->"), "<>", "#D9574F", "open {file}"),
    L("css", "CSS", "css", ("*.css",), "", ("/*", "*/"), "#", "#4A7BD0", "", "{"),
    L("scss", "SCSS", "scss", ("*.scss",), "//", ("/*", "*/"), "S", "#C2578F", "", "{"),
    L("less", "Less", "less", ("*.less",), "//", ("/*", "*/"), "L", "#4A6BA8", "", "{"),
    L("json", "JSON", "json", ("*.json", "*.jsonc", ".prettierrc", ".eslintrc", "*.webmanifest", "*.ipynb"), "//", (), "{}", "#B5862E", "", "{["),
    L("yaml", "YAML", "yaml", ("*.yml", "*.yaml"), "#", (), "yml", "#B5532F", "", ":"),
    L("toml", "TOML", "toml", ("*.toml", "Cargo.lock", "poetry.lock"), "#", (), "T", "#8A6A4A"),
    L("ini", "INI", "ini", ("*.ini", "*.cfg", "*.conf", ".editorconfig", "*.properties", ".gitconfig"), "#", (), "ini", "#8A8780"),
    L("xml", "XML", "xml", ("*.xml", "*.plist", "*.xsd", "*.xsl", "*.svg", "*.storyboard", "*.xib", "*.csproj"), "",
      ("<!--", "-->"), "<>", "#C27A2C"),
    L("markdown", "Markdown", "markdown", ("*.md", "*.markdown", "*.mdx"), "", ("<!--", "-->"), "M↓", "#4A7BD0"),
    L("rst", "reStructuredText", "rst", ("*.rst",), "..", (), "rst", "#8A8780"),
    L("text", "Обычный текст", "text", ("*.txt", "*.log", "LICENSE", "*.csv", "*.tsv"), "", (), "txt", "#8A8780"),
    L("shell", "Shell", "bash", ("*.sh", "*.bash", "*.zsh", ".zshrc", ".bashrc", ".bash_profile", ".zprofile", ".profile",
                                 "*.command", ".env", "*.env"), "#", (), "$_", "#4E8A5A", "bash {file}", ""),
    L("fish", "Fish", "fish", ("*.fish",), "#", (), "fish", "#4E8A5A", "fish {file}"),
    L("powershell", "PowerShell", "powershell", ("*.ps1", "*.psm1"), "#", ("<#", "#>"), "PS", "#3A76A8", "pwsh {file}", "{"),
    L("bat", "Batch", "batch", ("*.bat", "*.cmd"), "REM ", (), "bat", "#8A8780"),
    L("c", "C", "c", ("*.c", "*.h"), "//", ("/*", "*/"), "C", "#5C6BC0",
      'cc {file} -o {out} && {out}', "{"),
    L("cpp", "C++", "cpp", ("*.cpp", "*.cc", "*.cxx", "*.hpp", "*.hh", "*.hxx", "*.ino"), "//", ("/*", "*/"), "C++", "#3A6EA8",
      'c++ -std=c++17 {file} -o {out} && {out}', "{"),
    L("objc", "Objective-C", "objective-c", ("*.m", "*.mm"), "//", ("/*", "*/"), "OC", "#3A76A8",
      "clang -framework Foundation {file} -o {out} && {out}", "{"),
    L("csharp", "C#", "csharp", ("*.cs", "*.csx"), "//", ("/*", "*/"), "C#", "#7B4FA8", "dotnet run", "{"),
    L("java", "Java", "java", ("*.java",), "//", ("/*", "*/"), "J", "#B5532F", "java {file}", "{"),
    L("kotlin", "Kotlin", "kotlin", ("*.kt", "*.kts"), "//", ("/*", "*/"), "K", "#8A4FC2",
      "kotlinc {file} -include-runtime -d {out}.jar && java -jar {out}.jar", "{"),
    L("scala", "Scala", "scala", ("*.scala", "*.sc"), "//", ("/*", "*/"), "sc", "#C2453E", "scala {file}", "{"),
    L("groovy", "Groovy", "groovy", ("*.groovy", "*.gradle", "Jenkinsfile"), "//", ("/*", "*/"), "G", "#4A7B9C", "groovy {file}", "{"),
    L("go", "Go", "go", ("*.go",), "//", ("/*", "*/"), "go", "#2B9CB8", "go run {file}", "{"),
    L("rust", "Rust", "rust", ("*.rs",), "//", ("/*", "*/"), "rs", "#B5532F", "rustc {file} -o {out} && {out}", "{"),
    L("swift", "Swift", "swift", ("*.swift",), "//", ("/*", "*/"), "sw", "#E0663F", "swift {file}", "{"),
    L("dart", "Dart", "dart", ("*.dart",), "//", ("/*", "*/"), "D", "#2B8CB8", "dart run {file}", "{"),
    L("php", "PHP", "php", ("*.php", "*.phtml"), "//", ("/*", "*/"), "php", "#6E6FA8", "php {file}", "{"),
    L("ruby", "Ruby", "ruby", ("*.rb", "Gemfile", "Rakefile", "*.gemspec", "*.erb"), "#", ("=begin", "=end"), "rb", "#C2453E",
      "ruby {file}"),
    L("perl", "Perl", "perl", ("*.pl", "*.pm"), "#", (), "pl", "#3A76A8", "perl {file}", "{"),
    L("lua", "Lua", "lua", ("*.lua",), "--", ("--[[", "]]"), "lua", "#2E4E9E", "lua {file}"),
    L("r", "R", "r", ("*.r", "*.R", "*.Rmd"), "#", (), "R", "#3A76A8", "Rscript {file}", "{"),
    L("julia", "Julia", "julia", ("*.jl",), "#", ("#=", "=#"), "jl", "#8A4FC2", "julia {file}"),
    L("haskell", "Haskell", "haskell", ("*.hs", "*.lhs"), "--", ("{-", "-}"), "hs", "#6E5BA8", "runghc {file}"),
    L("elixir", "Elixir", "elixir", ("*.ex", "*.exs"), "#", (), "ex", "#7B4FA8", "elixir {file}"),
    L("erlang", "Erlang", "erlang", ("*.erl", "*.hrl"), "%", (), "erl", "#A8324E", "escript {file}"),
    L("clojure", "Clojure", "clojure", ("*.clj", "*.cljs", "*.cljc", "*.edn"), ";", (), "clj", "#5881D8", "clojure {file}"),
    L("lisp", "Lisp", "common-lisp", ("*.lisp", "*.lsp", "*.cl"), ";", ("#|", "|#"), "λ", "#8A8780", "sbcl --script {file}"),
    L("scheme", "Scheme", "scheme", ("*.scm", "*.ss", "*.rkt"), ";", ("#|", "|#"), "λ", "#8A8780", "racket {file}"),
    L("fsharp", "F#", "fsharp", ("*.fs", "*.fsx", "*.fsi"), "//", ("(*", "*)"), "F#", "#3A97A8", "dotnet fsi {file}"),
    L("ocaml", "OCaml", "ocaml", ("*.ml", "*.mli"), "", ("(*", "*)"), "ml", "#E0663F", "ocaml {file}"),
    L("zig", "Zig", "zig", ("*.zig",), "//", (), "zig", "#E0A23F", "zig run {file}", "{"),
    L("nim", "Nim", "nim", ("*.nim",), "#", ("#[", "]#"), "nim", "#C9A227", "nim r {file}", ":"),
    L("crystal", "Crystal", "crystal", ("*.cr",), "#", (), "cr", "#141413", "crystal run {file}"),
    L("vlang", "V", "v", ("*.v",), "//", ("/*", "*/"), "V", "#4A7BD0", "v run {file}", "{"),
    L("d", "D", "d", ("*.d",), "//", ("/*", "*/"), "D", "#C2453E", "rdmd {file}", "{"),
    L("fortran", "Fortran", "fortran", ("*.f90", "*.f95", "*.f03", "*.f", "*.for"), "!", (), "F", "#734F96",
      "gfortran {file} -o {out} && {out}"),
    L("pascal", "Pascal", "delphi", ("*.pas", "*.pp", "*.dpr"), "//", ("{", "}"), "pas", "#C27A2C", "fpc {file} && {out}"),
    L("asm", "Assembly", "nasm", ("*.asm", "*.s", "*.S"), ";", (), "asm", "#8A8780"),
    L("sql", "SQL", "sql", ("*.sql", "*.ddl"), "--", ("/*", "*/"), "sql", "#B5862E", "sqlite3 < {file}"),
    L("graphql", "GraphQL", "graphql", ("*.graphql", "*.gql"), "#", (), "gql", "#C2578F"),
    L("proto", "Protocol Buffers", "protobuf", ("*.proto",), "//", ("/*", "*/"), "pb", "#3A76A8", "", "{"),
    L("dockerfile", "Dockerfile", "docker", ("Dockerfile", "*.dockerfile", "Containerfile"), "#", (), "🐳", "#2B8CB8"),
    L("make", "Makefile", "make", ("Makefile", "makefile", "GNUmakefile", "*.mk"), "#", (), "mk", "#8A6A4A", "make"),
    L("cmake", "CMake", "cmake", ("CMakeLists.txt", "*.cmake"), "#", (), "cm", "#3A97A8"),
    L("nginx", "Nginx", "nginx", ("nginx.conf", "*.nginx"), "#", (), "ngx", "#3E8E63", "", "{"),
    L("terraform", "Terraform", "terraform", ("*.tf", "*.tfvars", "*.hcl"), "#", ("/*", "*/"), "tf", "#7B4FA8", "", "{"),
    L("vue", "Vue", "html", ("*.vue",), "", ("<!--", "-->"), "V", "#3E8E63"),
    L("svelte", "Svelte", "html", ("*.svelte",), "", ("<!--", "-->"), "S", "#E0663F"),
    L("latex", "LaTeX", "tex", ("*.tex", "*.sty", "*.cls", "*.bib"), "%", (), "TeX", "#3E8E63", "pdflatex {file}"),
    L("diff", "Diff", "diff", ("*.diff", "*.patch"), "", (), "±", "#8A8780"),
    L("gitignore", "Ignore", "text", (".gitignore", ".dockerignore", ".npmignore", ".gitattributes"), "#", (), "git", "#C2453E"),
    L("verilog", "Verilog", "verilog", ("*.sv", "*.svh", "*.vh"), "//", ("/*", "*/"), "sv", "#8A6A4A"),
    L("vhdl", "VHDL", "vhdl", ("*.vhd", "*.vhdl"), "--", (), "vhd", "#8A6A4A"),
    L("solidity", "Solidity", "solidity", ("*.sol",), "//", ("/*", "*/"), "sol", "#6E6FA8", "", "{"),
    L("matlab", "MATLAB", "matlab", (), "%", ("%{", "%}"), "M", "#E0663F"),
    L("prolog", "Prolog", "prolog", ("*.pro", "*.P"), "%", ("/*", "*/"), "pl", "#C2453E", "swipl {file}"),
    L("amkawa", "Amkawa", "python", ("*.amkawa", "*.amk"), "#", (), "am", "#D97757", "python3 amkawa.py {file}", ":"),
]
PLAIN = Language("text", "Обычный текст", "text", (), "", (), "txt", "#8A8780")
BY_ID = {lang.id: lang for lang in LANGUAGES}


def detect(path):
    """Language for a file name (exact names first, then extensions, then Pygments)."""
    name = Path(path).name
    for lang in LANGUAGES:
        if name in lang.patterns:
            return lang
    for lang in LANGUAGES:
        for pat in lang.patterns:
            if "*" in pat and fnmatch.fnmatchcase(name, pat):
                return lang
    lower = name.lower()
    for lang in LANGUAGES:
        for pat in lang.patterns:
            if "*" in pat and fnmatch.fnmatchcase(lower, pat.lower()):
                return lang
    try:
        from pygments.lexers import get_lexer_for_filename

        lexer = get_lexer_for_filename(name)
        alias = lexer.aliases[0] if lexer.aliases else "text"
        return Language(alias, lexer.name, alias, (), "#", (), alias[:3], "#8A8780")
    except Exception:
        return PLAIN


def from_shebang(first_line):
    if not first_line.startswith("#!"):
        return None
    for key, lid in (("python", "python"), ("node", "javascript"), ("bash", "shell"), ("zsh", "shell"), ("/sh", "shell"),
                     ("ruby", "ruby"), ("perl", "perl"), ("php", "php"), ("lua", "lua")):
        if key in first_line:
            return BY_ID[lid]
    return None


def all_languages():
    """Every language for the «Выбрать язык» picker: the table + everything Pygments knows."""
    seen = {lang.lexer for lang in LANGUAGES}
    out = list(LANGUAGES)
    try:
        from pygments.lexers import get_all_lexers

        for name, aliases, _patterns, _mimes in get_all_lexers():
            if aliases and aliases[0] not in seen:
                seen.add(aliases[0])
                out.append(Language(aliases[0], name, aliases[0], (), "#", (), aliases[0][:3], "#8A8780"))
    except Exception:
        pass
    return sorted(out, key=lambda l: l.name.lower())


def run_command(lang, path, out_dir):
    """Shell command to run a file, or None."""
    if not lang.run:
        return None
    path = Path(path)
    out = Path(out_dir) / path.stem
    q = shlex.quote
    return lang.run.format(file=q(str(path)), dir=q(str(path.parent)), stem=q(path.stem), out=q(str(out)))
