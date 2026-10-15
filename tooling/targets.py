import filecmp
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

from . import blocks, kde
from .backup import BackupSession, copy_path, remove_path, state_dir
from .render import RenderError, render_text, render_tree

MODES = ("symlink", "copy", "managed-block")


class TargetError(Exception):
    pass


class Target:
    def __init__(self, path):
        self.dir = Path(path)
        with open(self.dir / "target.toml", "rb") as f:
            self.meta = tomllib.load(f)
        self.name = self.meta.get("name", self.dir.name)
        self.order = self.meta.get("order", 50)
        self.hidden = self.dir.name.startswith("_")

    @property
    def description(self):
        return self.meta.get("description", "")

    def packages(self):
        return list(self.meta.get("packages", [])), list(self.meta.get("aur_packages", []))


def load_targets(root):
    targets = [Target(p) for p in sorted((Path(root) / "targets").iterdir()) if (p / "target.toml").is_file()]
    return sorted(targets, key=lambda t: (t.order, t.name))


def select(targets, only):
    if not only:
        return [t for t in targets if not t.hidden]
    by_name = {t.name: t for t in targets}
    unknown = [n for n in only if n not in by_name]
    if unknown:
        raise TargetError(f"alvo(s) desconhecido(s): {', '.join(unknown)}")
    return [t for t in targets if t.name in only]


def missing_packages(names):
    if not names:
        return []
    result = subprocess.run(["pacman", "-T", *names], capture_output=True, text=True)
    return result.stdout.split()


def aur_helper():
    return next((h for h in ("paru", "yay") if shutil.which(h)), None)


def _same(a, b, ignore=()):
    """Conteúdo igual? `ignore`: nomes que o app cria no destino e não contam."""
    a, b = Path(a), Path(b)
    if b.is_symlink() or not b.exists():
        return False
    if a.is_file():
        return b.is_file() and filecmp.cmp(a, b, shallow=False)
    cmp = filecmp.dircmp(a, b, ignore=filecmp.DEFAULT_IGNORES + list(ignore))

    def equal(c):
        if c.left_only or c.right_only or c.funny_files:
            return False
        _, mismatch, errors = filecmp.cmpfiles(c.left, c.right, c.common_files, shallow=False)
        return not mismatch and not errors and all(equal(s) for s in c.subdirs.values())

    return equal(cmp)


def _missing_dirs(path):
    missing = []
    parent = Path(path).parent
    while not parent.exists():
        missing.append(str(parent))
        parent = parent.parent
    return missing


def replace_font_family(current, family):
    if not current:
        return f"{family},10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"
    parts = current.split(",")
    parts[0] = family
    return ",".join(parts)


class Runner:
    def __init__(self, root, palette, dry_run=False, out=print):
        self.root = Path(root)
        self.palette = palette
        self.tokens = palette.tokens()
        self.dry_run = dry_run
        self.out = out
        # O sistema lê build/ por symlink (Kvantum, Plasma Style...). No dry-run o render vai
        # para uma pasta temporária, para não mudar o que está aplicado; os symlinks continuam
        # sendo comparados com o caminho real.
        self.real_build = self.root / "build"
        self.build = Path(tempfile.mkdtemp(prefix="theme-dry-run-")) if dry_run else self.real_build
        self.session = BackupSession(palette.id)

    def cleanup(self):
        if self.build != self.real_build:
            shutil.rmtree(self.build, ignore_errors=True)

    def t(self, value, origin):
        if isinstance(value, bool):
            return "true" if value else "false"
        return render_text(str(value), self.tokens, origin)

    def sh(self, cmd, value=None, capture=False):
        env = dict(os.environ)
        if value is not None:
            env["THEME_VALUE"] = value
        result = subprocess.run(
            cmd, shell=True, cwd=self.root, env=env, text=True,
            capture_output=capture, check=not capture,
        )
        return result

    # --- render / detecção / dependências -------------------------------------------------

    def render(self, target):
        # "generate": script que (re)escreve templates/ a partir da paleta antes do render
        # (ex.: o SVG do Kvantum, cuja geometria depende de raios e profundidades).
        # Deve ser determinístico e só gravar o que mudou.
        generator = target.meta.get("generate")
        if generator:
            result = subprocess.run([sys.executable, str(target.dir / generator)], cwd=self.root,
                                    capture_output=True, text=True)
            if result.returncode != 0:
                raise TargetError(f"generate falhou: {result.stderr.strip()}")
        templates = target.dir / "templates"
        if templates.is_dir():
            render_tree(templates, self.build / target.name, self.tokens)

    def detect(self, target):
        cmd = target.meta.get("detect")
        if not cmd:
            return True
        return self.sh(cmd, capture=True).returncode == 0

    def ensure_packages(self, target):
        repo, aur = target.packages()
        missing = missing_packages(repo + aur)
        if not missing:
            return True
        repo_missing = [p for p in missing if p in repo]
        aur_missing = [p for p in missing if p not in repo]
        self.out(f"  pacotes faltando: {', '.join(missing)}")
        if self.dry_run:
            self.out("  (dry-run) instalaria os pacotes acima e seguiria")
            return True
        if not sys.stdin.isatty():
            self.out("  sem terminal interativo para confirmar a instalação")
            return False
        answer = input(f"  Instalar {', '.join(missing)}? [s/N] ").strip().lower()
        if answer not in ("s", "sim", "y", "yes"):
            return False
        if repo_missing:
            subprocess.run(["sudo", "pacman", "-S", "--needed", *repo_missing], check=True)
        if aur_missing:
            helper = aur_helper()
            if helper is None:
                self.out("  nenhum helper do AUR (paru/yay) encontrado")
                return False
            subprocess.run([helper, "-S", "--needed", *aur_missing], check=True)
        return not missing_packages(repo + aur)

    # --- aplicação ------------------------------------------------------------------------

    # --- conteúdo renderizado ------------------------------------------------------------
    # Um symlink para build/ não muda quando só o conteúdo renderizado muda (ex.: nova cor na
    # paleta). Para os posts e o reapply_on_change enxergarem isso, guardamos o hash do
    # build/<alvo> aplicado em ~/.local/state/<id>/rendered/.

    def _fingerprint_path(self, target):
        return state_dir(self.palette.id) / "rendered" / f"{target.name}.sha256"

    def _fingerprint(self, target):
        root = self.build / target.name
        if not root.is_dir():
            return None
        digest = hashlib.sha256()
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
        return digest.hexdigest()

    def _render_changed(self, target):
        """Hash atual se o conteúdo mudou desde o último apply de um alvo com symlink, senão None."""
        if not any(spec.get("mode", "symlink") == "symlink" for spec in target.meta.get("files", [])):
            return None
        current = self._fingerprint(target)
        path = self._fingerprint_path(target)
        stored = path.read_text().strip() if path.is_file() else None
        return current if current and current != stored else None

    def apply(self, target):
        """Aplica um alvo. Retorna a lista de mudanças (descrições)."""
        changes = []
        files_changed = False
        rendered = self._render_changed(target)
        for spec in target.meta.get("files", []):
            if self._file(target, spec, changes):
                files_changed = True
        if rendered and not files_changed:
            changes.append(f"conteúdo renderizado atualizado (build/{target.name})")
            files_changed = True
        for spec in target.meta.get("keys", []):
            self._key(target, spec, changes)
        for spec in target.meta.get("states", []):
            self._state(target, spec, changes, files_changed)
        if changes:
            for spec in target.meta.get("post", []):
                cmd = self.t(spec["cmd"], f"{target.name}: post")
                changes.append(f"executar: {cmd}")
                if not self.dry_run:
                    self.sh(cmd)
        if rendered and not self.dry_run:
            path = self._fingerprint_path(target)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered + "\n")
        return changes

    def _file(self, target, spec, changes):
        mode = spec.get("mode", "symlink")
        if mode not in MODES:
            raise TargetError(f"modo inválido: {mode}")
        src = Path(spec["src"])
        if src.parts[0] != "templates":
            raise TargetError(f"src deve ficar em templates/: {src}")
        built = self.build / target.name / Path(*src.parts[1:])
        if not built.exists():
            raise TargetError(f"arquivo renderizado não existe: {built}")
        dest = Path(os.path.expanduser(self.t(spec["dest"], f"{target.name}: dest")))
        exists = dest.exists() or dest.is_symlink()

        if mode == "symlink":
            built = self.real_build / target.name / Path(*src.parts[1:])
            if dest.is_symlink() and os.readlink(dest) == str(built):
                return False
            changes.append(f"symlink {dest} -> {built}")
            if not self.dry_run:
                self._record_file(target, dest, exists)
                remove_path(dest)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.symlink_to(built)
            return True

        if mode == "copy":
            if _same(built, dest, spec.get("ignore", [])):
                return False
            changes.append(f"copiar {built} -> {dest}")
            if not self.dry_run:
                self._record_file(target, dest, exists)
                remove_path(dest)
                copy_path(built, dest)
            return True

        begin, end = blocks.markers(self.palette.id, spec.get("comment", "#"))
        current = dest.read_text() if dest.is_file() else ""
        new = blocks.upsert(current, built.read_text(), begin, end, spec.get("position", "bottom"))
        # Só a quebra de linha final não conta: o gtkconfig do KDE reescreve o gtk.css sem
        # ela ao aplicar o Look-and-Feel, e o bloco continua intacto.
        if new.rstrip("\n") == current.rstrip("\n"):
            return False
        changes.append(f"bloco gerenciado em {dest}")
        if not self.dry_run:
            entry = {"kind": "block", "target": target.name, "path": str(dest), "markers": [begin, end],
                     "created_dirs": _missing_dirs(dest)}
            self.session.record(entry, save_path=dest if exists else None)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(new)
        return True

    def _record_file(self, target, dest, existed):
        entry = {"kind": "file", "target": target.name, "path": str(dest), "existed": existed,
                 "created_dirs": _missing_dirs(dest)}
        self.session.record(entry, save_path=dest if existed else None)

    def _key(self, target, spec, changes):
        origin = f"{target.name}: key {spec.get('key')}"
        file = self.t(spec["file"], origin)
        if file.startswith("~"):
            file = os.path.expanduser(file)
        group = spec["group"]
        group = [self.t(g, origin) for g in ([group] if isinstance(group, str) else group)]
        key = spec["key"]
        current = kde.read(file, group, key)
        if spec.get("delete"):
            desired = None
        elif spec.get("transform") == "font-family":
            desired = replace_font_family(current, self.t(spec["value"], origin))
        elif "transform" in spec:
            raise TargetError(f"transform desconhecido: {spec['transform']}")
        else:
            desired = self.t(spec["value"], origin)
        if current == desired:
            return
        shown = "(apagar)" if desired is None else repr(desired)
        changes.append(f"{file} [{']['.join(group)}] {key} = {shown}")
        if self.dry_run:
            return
        self.session.record({"kind": "key", "target": target.name, "file": file,
                             "group": group, "key": key, "old": current})
        kde.restore(file, group, key, desired)

    def _state(self, target, spec, changes, files_changed):
        origin = f"{target.name}: state {spec['name']}"
        value = self.t(spec["value"], origin)
        get = self.sh(self.t(spec["get"], origin), capture=True)
        if get.returncode != 0:
            raise TargetError(f"{origin}: comando get falhou: {get.stderr.strip()}")
        current = get.stdout.strip()
        reapply = spec.get("reapply_on_change", False) and files_changed
        if current == value and not reapply:
            return
        set_cmd = self.t(spec["set"], origin)
        changes.append(f"{spec['name']}: {current or '(vazio)'} -> {value}")
        if self.dry_run:
            return
        if current != value:
            self.session.record({
                "kind": "state", "target": target.name, "name": spec["name"], "old": current,
                "default": self.t(spec.get("default", ""), origin),
                "restore": self.t(spec.get("restore", spec["set"]), origin),
            })
        self.sh(set_cmd, value=value)


def run(root, palette, targets, dry_run=False, out=print):
    runner = Runner(root, palette, dry_run=dry_run, out=out)
    summary = []
    for target in targets:
        out(f"\n==> {target.name} — {target.description}")
        try:
            if not runner.detect(target):
                out("  não detectado, pulando")
                summary.append((target.name, "pulado (não detectado)"))
                continue
            if not runner.ensure_packages(target):
                summary.append((target.name, "pulado (dependências faltando)"))
                continue
            runner.render(target)
            changes = runner.apply(target)
        except (RenderError, TargetError, OSError, subprocess.CalledProcessError) as err:
            out(f"  erro: {err}")
            summary.append((target.name, f"erro: {err}"))
            continue
        for change in changes:
            out(f"  {'~' if dry_run else '+'} {change}")
        message = target.meta.get("message")
        if changes and message:
            out("")
            for line in runner.t(message, f"{target.name}: message").rstrip().splitlines():
                out(f"  {line}")
        if not changes:
            out("  sem mudanças")
        verb = "mudaria" if dry_run else "aplicado"
        summary.append((target.name, f"{verb} ({len(changes)} mudança(s))" if changes else "sem mudanças"))

    out("\nResumo:")
    width = max((len(n) for n, _ in summary), default=0)
    for name, status in summary:
        out(f"  {name:<{width}}  {status}")
    if runner.session.dir:
        out(f"\nBackup: {runner.session.dir}")
    runner.cleanup()
    return all(not s.startswith("erro") for _, s in summary)
