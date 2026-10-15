import subprocess

_SENTINEL = "__theme_absent__"


def _groups(group):
    groups = [group] if isinstance(group, str) else list(group)
    args = []
    for g in groups:
        args += ["--group", g]
    return args


def _base(tool, file, group, key):
    return [tool, "--file", file, *_groups(group), "--key", key]


def read(file, group, key):
    """Valor atual da chave, ou None se ela não existe."""
    out = subprocess.run(
        _base("kreadconfig6", file, group, key) + ["--default", _SENTINEL],
        capture_output=True, text=True, check=True,
    ).stdout.rstrip("\n")
    return None if out == _SENTINEL else out


def write(file, group, key, value):
    subprocess.run(_base("kwriteconfig6", file, group, key) + ["--notify", "--", value], check=True)


def delete(file, group, key):
    subprocess.run(_base("kwriteconfig6", file, group, key) + ["--notify", "--delete"], check=True)


def restore(file, group, key, old):
    if old is None:
        delete(file, group, key)
    else:
        write(file, group, key, old)
