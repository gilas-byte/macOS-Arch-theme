#!/bin/sh
# Gerado pelo tema Tahoe: deixa o KWin achar plugins instalados na pasta do usuário (sem sudo).
export QT_PLUGIN_PATH="$$HOME/.local/lib/qt6/plugins$${QT_PLUGIN_PATH:+:$$QT_PLUGIN_PATH}"
