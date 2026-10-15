COMMENT_STYLES = {
    "#": ("# ", ""),
    "//": ("// ", ""),
    "/*": ("/* ", " */"),
    ";": ("; ", ""),
}


def markers(theme_id, comment="#"):
    try:
        start, end = COMMENT_STYLES[comment]
    except KeyError:
        raise ValueError(f"estilo de comentário desconhecido: {comment!r}") from None
    return f"{start}>>> {theme_id} >>>{end}", f"{start}<<< {theme_id} <<<{end}"


def _split(text, begin, end):
    lines = text.splitlines()
    try:
        i = lines.index(begin)
        j = lines.index(end, i)
    except ValueError:
        return lines, None
    return lines[:i] + lines[j + 1:], i


def remove(text, begin, end):
    lines, _ = _split(text, begin, end)
    return "\n".join(lines) + "\n" if lines else ""


def upsert(text, body, begin, end, position="bottom"):
    """Insere ou atualiza o bloco. position: top | bottom | after-imports."""
    block = [begin, *body.rstrip("\n").splitlines(), end]
    lines, at = _split(text, begin, end)
    if at is None:
        if position == "top":
            at = 0
        elif position == "after-imports":
            imports = [n for n, line in enumerate(lines) if line.lstrip().startswith("@import")]
            at = imports[-1] + 1 if imports else 0
        elif position == "bottom":
            at = len(lines)
        else:
            raise ValueError(f"posição desconhecida: {position!r}")
    return "\n".join(lines[:at] + block + lines[at:]) + "\n"
