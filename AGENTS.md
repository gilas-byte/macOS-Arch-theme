# Tahoe — instruções para agentes de código

Vale para qualquer agente (Claude Code, Antigravity, Codex...). O `CLAUDE.md` só importa este arquivo.

Tema macOS Tahoe escuro para Arch/CachyOS com KDE Plasma 6 (só testado no Plasma 6.8/KWin 6.8; sem modo claro). Leia o
`README.md` (uso e alvos) e o `ARCHITECTURE.md` (paleta, alvos, `target.toml`, contraste) antes de alterar.

## Regras do projeto

- `palette.toml` é a única fonte de cor e forma: nenhum hex solto em template. Alvos em `targets/<alvo>/` (`target.toml` +
  `templates/`). O instalador é idempotente, tem `--dry-run` e faz backup antes de tocar em qualquer arquivo ou chave do KDE.
- **Sem sudo para o tema do usuário.** Exceções só à mão: `targets/plymouth` e `targets/login`. Nunca coloque `sudo` num
  fluxo automático. O plugin `tahoecursor` instala em `~/.local/lib/qt6/plugins` e o KWin o acha por `QT_PLUGIN_PATH`
  (arquivo em `~/.config/plasma-workspace/env/`).
- Fontes SF e arte da Apple nunca entram no repositório (baixadas na instalação). Respeite as licenças dos submodules em `vendor/`.
- Contraste WCAG é checado por `python3 -m tooling check`; ele bloqueia o install.

## Testes (rode antes de dizer que funciona)

- `tests/selftest.sh`: render, dry-run, idempotência, backup e restore em `/tmp`.
- `tests/kwin-check.sh [--compile]`: versão dos plugins C++ (blur e cursor) contra o KWin instalado, se carregaram, e se o
  `tahoecursor` compila contra os headers atuais. `KWIN_CHECK_ONLY=<id>` limita a um plugin.
- `tests/kwin-nested.sh`: sobe um KWin virtual e confere que os plugins carregam, sem tocar na sessão do usuário.
- `tests/stylus-check.py`: alvo stylus.

## Armadilha principal: update do KWin

Os efeitos C++ (`effects/tahoecursor` e o `kwin-effects-better-blur-dx` do AUR) só funcionam na **versão exata** do KWin em
que foram compilados, e a API interna muda entre versões menores (no 6.8, `paintScreen` passou a devolver `bool` e o
`renderer()` passou a ser por `RenderDevice`). Depois de atualizar o KWin: rode `tests/kwin-check.sh --compile`; se o
`tahoecursor` não compilar, o código precisa de port (veja `git log -p -- effects/tahoecursor`); depois
`./install.sh --only cursor-effects` e logout/login. O blur vem do AUR e reinstalar exige sudo. `deploy/kwin-watch/` tem um
vigia opcional (unidades de usuário) que faz o rebuild e avisa.
Instalar o `.so` sempre por rename (nunca sobrescrever no lugar): o KWin em execução tem o antigo mapeado.

## Como trabalhar

Commits pequenos e em português. Seu relato não é prova: cole a saída real dos testes. Não invente saída. Não faça push sem
o dono pedir.
