#!/usr/bin/env bash
# Teste isolado: sobe um KWin virtual (config copiada, bus próprio; não toca na sua sessão) e confere se
# tahoecursor e better_blur_dx carregam. Sai com 1 se algum não carregar.
set -u
rc=0
T=$(mktemp -d "${TMPDIR:-/tmp}/kwin-nested.XXXXXX")
mkdir -p "$T/config" "$T/runtime"; chmod 700 "$T/runtime"
cp ~/.config/kwinrc "$T/config/kwinrc"
export XDG_CONFIG_HOME="$T/config" XDG_RUNTIME_DIR="$T/runtime"
export QT_PLUGIN_PATH="$HOME/.local/lib/qt6/plugins"
unset WAYLAND_DISPLAY DISPLAY
dbus-run-session -- bash -c '
  kwin_wayland --virtual --no-lockscreen --socket nested-test >"'"$T"'/kwin.log" 2>&1 &
  K=$!
  sleep 8
  fail=0
  for e in tahoecursor better_blur_dx; do
    v=$(qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.isEffectLoaded $e 2>&1)
    if [ "$v" = true ]; then echo "PASSOU: $e carregou no KWin virtual"; else echo "FALHOU: $e NÃO carregou ($v)" >&2; fail=1; fi
  done
  kill $K 2>/dev/null; sleep 1
  exit $fail
'; rc=$?
echo "--- log (filtrado)"; grep -iE "tahoecursor|different version|undefined|failed|better_blur" "$T/kwin.log" | head -10
rm -rf "$T"
exit $rc
