/*
    Tahoe Cursor: cursor que estica no movimento, pula no clique
    e tela que afunda/ondula no ponto do clique.

    SPDX-License-Identifier: GPL-2.0-or-later
*/

#pragma once

#include "core/colorspace.h"
#include "core/rect.h"
#include "effect/effect.h"
#include "input_event_spy.h"

#include <QPointF>
#include <QTimer>

#include <chrono>
#include <map>
#include <memory>

namespace KWin
{

class Cursor;
class CursorItem;
class GLFramebuffer;
class GLShader;
class GLTexture;
class LogicalOutput;

// Mola amortecida simples: x'' = -k (x - alvo) - c x'
struct Spring
{
    double value = 0.0;
    double velocity = 0.0;
    double target = 0.0;
    double stiffness = 500.0;
    double damping = 22.0;

    void step(double dt);
    bool settled() const;
};

class TahoeCursorEffect : public Effect, public InputEventSpy
{
    Q_OBJECT

public:
    TahoeCursorEffect();
    ~TahoeCursorEffect() override;

    static bool supported();

    void reconfigure(ReconfigureFlags flags) override;
    bool isActive() const override;
    int requestedEffectChainPosition() const override;
    QString debug(const QString &parameter) const override;

    void prePaintScreen(ScreenPrePaintData &data) override;
    bool paintScreen(const RenderTarget &renderTarget, const RenderViewport &viewport, int mask, const Region &deviceRegion, LogicalOutput *screen) override;
    void postPaintScreen() override;

    void pointerMotion(PointerMotionEvent *event) override;
    void pointerButton(PointerButtonEvent *event) override;

private:
    struct OffscreenData
    {
        std::unique_ptr<GLTexture> texture;
        std::unique_ptr<GLFramebuffer> framebuffer;
        std::shared_ptr<ColorDescription> color = ColorDescription::sRGB;
    };

    void press(const QPointF &pos);
    void release(const QPointF &pos);
    void wake();
    void tick(std::chrono::steady_clock::time_point now);
    bool cursorAnimating() const;
    bool screenAnimating() const;
    bool windAnimating() const;
    void updateCursorItem();
    void takeCursor();
    void giveCursorBack();
    void recreateCursorItem();
    OffscreenData *ensureOffscreen(const RenderTarget &renderTarget, const RenderViewport &viewport, LogicalOutput *screen);
    GLShader *ensureShader();
    void paintWindCursor(const RenderTarget &renderTarget, const RenderViewport &viewport);
    bool drawsOwnCursor() const;
    bool mouseGone() const;
    RectF windCursorRect() const;

    // config
    bool m_stretchEnabled = true;
    double m_stretchAmount = 1.0;
    bool m_bounceEnabled = true;
    bool m_dentEnabled = false; // tela afundar: desligado por padrão (ScreenPress=true liga)
    bool m_rippleEnabled = false; // onda de rebote: desligada por padrão (Ripple=true liga)
    bool m_lensEnabled = false;
    double m_dentRadius = 140.0;
    double m_dentDepth = 1.0;
    bool m_dentFollow = true;
    double m_rippleStrength = 1.0;
    double m_rippleSize = 220.0;
    double m_stretchMax = 1.5;
    double m_stretchSpeed = 1400.0;
    bool m_windMode = true; // "Motion": wind (pontas dobram) ou stretch (estica, efeito antigo)
    double m_windStrength = 1.0;
    bool m_flipY = true;

    Cursor *m_cursor;
    std::unique_ptr<CursorItem> m_cursorItem;
    bool m_cursorHidden = false;

    // movimento
    QPointF m_lastPos;
    QPointF m_motionAccum; // px andados desde o último frame
    QPointF m_velocity;    // px/s
    QPointF m_axis{1.0, 0.0}; // (cos 2θ, sin 2θ): eixo do esticar, sem sentido
    Spring m_stretch;   // 0 = normal, 1 = esticado ao máximo
    double m_angle = 0.0;
    Spring m_windX; // vento: deslocamento das pontas, -1..1 em cada eixo (sentido do movimento)
    Spring m_windY;

    // clique
    Spring m_clickScale;
    Spring m_dent;
    QPointF m_dentCenter;
    QPointF m_rippleCenter;
    double m_rippleTime = -1.0; // segundos desde o soltar, <0 = sem onda
    int m_pressed = 0;

    std::chrono::steady_clock::time_point m_lastTick;
    bool m_ticking = false;
    QTimer m_giveBackTimer;

    std::map<LogicalOutput *, OffscreenData> m_offscreen;
    std::unique_ptr<GLShader> m_shader;
    bool m_shaderFailed = false;

    // vento: o próprio efeito desenha o cursor
    std::unique_ptr<GLShader> m_windShader;
    bool m_windShaderFailed = false;
    std::unique_ptr<GLTexture> m_cursorTexture; // o cursor desenhado fora da tela
    std::unique_ptr<GLFramebuffer> m_cursorFbo;
    RectF m_lastWindRect;
};

} // namespace KWin
