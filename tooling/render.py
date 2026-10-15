import shutil
from pathlib import Path
from string import Template


class RenderError(Exception):
    pass


def render_text(text, tokens, origin):
    try:
        return Template(text).substitute(tokens)
    except KeyError as e:
        raise RenderError(f"{origin}: placeholder desconhecido ${{{e.args[0]}}}") from None
    except ValueError as e:
        raise RenderError(f"{origin}: placeholder inválido ({e})") from None


def write_if_changed(path, content):
    path = Path(path)
    if path.is_file() and not path.is_symlink() and path.read_text() == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return True


def render_tree(src_root, out_root, tokens):
    src_root, out_root = Path(src_root), Path(out_root)
    expected = set()
    for src in sorted(p for p in src_root.rglob("*") if p.is_file()):
        rel = src.relative_to(src_root)
        expected.add(rel)
        try:
            text = src.read_text()
        except UnicodeDecodeError:
            raise RenderError(f"{src}: arquivo não é texto UTF-8") from None
        dest = out_root / rel
        write_if_changed(dest, render_text(text, tokens, src))
        shutil.copymode(src, dest)
    if out_root.exists():
        for stale in sorted(out_root.rglob("*"), reverse=True):
            rel = stale.relative_to(out_root)
            if stale.is_file() and rel not in expected:
                stale.unlink()
            elif stale.is_dir() and not any(stale.iterdir()):
                stale.rmdir()
