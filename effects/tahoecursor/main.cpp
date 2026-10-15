/*
    SPDX-License-Identifier: GPL-2.0-or-later
*/

#include "tahoecursor.h"

namespace KWin
{

KWIN_EFFECT_FACTORY_SUPPORTED(TahoeCursorEffect,
                              "metadata.json",
                              return TahoeCursorEffect::supported();)

} // namespace KWin

#include "main.moc"
