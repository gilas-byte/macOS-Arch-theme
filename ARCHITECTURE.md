# Arquitetura

Um tema é uma paleta (`palette.toml`) mais alvos (`targets/`) que a aplicam em cada app.

## Camadas

| Camada | Arquivo | Papel |
|---|---|---|
| Entrada | `install.sh`, `uninstall.sh` | Checam pré-requisitos e chamam `python3 -m tooling` |
| Fonte da verdade | `palette.toml` | Cores, formas, vidro, fontes e nomes do KDE. Nenhum hex solto em template |
| Alvos | `targets/<alvo>/target.toml` + `templates/` | O que cada parte do sistema recebe |
| Lógica | `tooling/` (Python 3.11+, só stdlib) | render, backup, aplicação, contraste |
| Base de terceiros | `vendor/MacTahoe-*` (submodules fixados) | Plasma Style, Aurorae, Kvantum, ícones, GTK |

## Tokens

Cada chave `[secao] chave = valor` vira `${secao_chave}` nos templates. Cores `#RRGGBB` ganham
`_nohash`, `_rgb`, `_r`, `_g` e `_b`. Floats entre 0 e 1 ganham `_pct`. Valores `lighten()`, `darken()` e `mix()`
são calculados. `$$` vira `$` literal. Extras: `${theme_id}`, `${theme_name}`, `${lnf_id}`, `${color_scheme}`.

## target.toml

```toml
name = "exemplo"
description = "..."
order = 20                      # ordem de execução
packages = []                   # pacman
aur_packages = []               # paru/yay
detect = "command -v algo"      # sem isso, o alvo sempre roda

[[files]]                       # mode: symlink | copy | managed-block
src = "templates/x.conf"
dest = "~/.config/x/x.conf"
mode = "copy"

[[keys]]                        # kwriteconfig6 chave a chave, valor antigo vai para o backup
file = "kdeglobals"
group = "General"               # ou ["Grupo", "Aninhado"]
key = "ColorScheme"
value = "${color_scheme}"

[[states]]                      # estado lido/aplicado por comando; $$THEME_VALUE recebe o valor
name = "..."
get = "..."
set = "..."
value = "..."
default = "..."                 # usado no restore se antes não havia nada

[[post]]                        # roda só se algo mudou
cmd = "..."
```

Alvos que começam com `_` só rodam com `--only`.

## Contraste

`tooling/contrast.py` bloqueia o install se texto principal ou secundário ficar abaixo de 4.5:1 nos
fundos principais. Branco sobre o azul `#0A84FF` dá 3.65:1, igual ao macOS. Por isso esse par usa o
mínimo de texto grande (3.0).
