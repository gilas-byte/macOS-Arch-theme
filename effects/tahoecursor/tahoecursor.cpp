/*
    SPDX-License-Identifier: GPL-2.0-or-later
*/

#include "tahoecursor.h"

#include "core/rendertarget.h"
#include "core/renderbackend.h"
#include "core/renderviewport.h"
#include "cursor.h"
#include "cursorsource.h"
#include "effect/effecthandler.h"
#include "input.h"
#include "input_event.h"
#include "opengl/glutils.h"
#include "scene/cursoritem.h"
#include "scene/itemrenderer.h"
#include "scene/workspacescene.h"
#include "wayland/surface.h"

#include <KConfigGroup>
#include <KSharedConfig>

#include <QTransform>
#include <QVector2D>

#include <algorithm>
#include <cmath>

namespace KWin
{

static constexpr double s_rippleDuration = 0.75; // s

void Spring::step(double dt)
{
    // passos pequenos pra mola não explodir com dt grande
    const int n = std::max(1, int(std::ceil(dt / 0.004)));
    const double h = dt / n;
    for (int i = 0; i < n; ++i) {
        const double a = -stiffness * (value - target) - damping * velocity;
        velocity += a * h;
        value += velocity * h;
    }
}

bool Spring::settled() const
{
    return std::abs(value - target) < 0.001 && std::abs(velocity) < 0.01;
}

TahoeCursorEffect::TahoeCursorEffect()
    : m_cursor(Cursors::self()->mouse())
{
    input()->installInputEventSpy(this);

    m_clickScale.value = m_clickScale.target = 1.0;
    m_stretch.stiffness = 900.0;
    m_stretch.damping = 56.0; // quase crítico: segue a velocidade sem ficar balançando
    // vento: mola meio frouxa, as pontas balançam um pouco quando o mouse para
    for (Spring *s : {&m_windX, &m_windY}) {
        s->stiffness = 260.0;
        s->damping = 19.0;
    }
    m_lastPos = m_cursor->pos();

    // parou de animar: espera um pouco antes de devolver o cursor de hardware, pra não
    // ficar trocando de cursor a cada pausinha do mouse (dá soluço na troca)
    m_giveBackTimer.setSingleShot(true);
    m_giveBackTimer.setInterval(600);
    connect(&m_giveBackTimer, &QTimer::timeout, this, [this]() {
        if (!m_ticking) {
            giveCursorBack();
        }
    });

    connect(m_cursor, &Cursor::cursorChanged, this, [this]() {
        if (m_cursorItem) {
            recreateCursorItem();
        }
        if (drawsOwnCursor()) {
            effects->addRepaint(m_lastWindRect);
            effects->addRepaint(windCursorRect());
        }
    });
    connect(m_cursor, &Cursor::posChanged, this, [this]() {
        if (m_cursorItem) {
            m_cursorItem->setPosition(m_cursor->pos());
        }
        if (drawsOwnCursor()) {
            effects->addRepaint(m_lastWindRect);
            effects->addRepaint(windCursorRect());
        }
    });

    reconfigure(ReconfigureAll);
}

TahoeCursorEffect::~TahoeCursorEffect()
{
    input()->uninstallInputEventSpy(this);
    m_giveBackTimer.stop();
    giveCursorBack();
}

bool TahoeCursorEffect::supported()
{
    return effects->isOpenGLCompositing();
}

void TahoeCursorEffect::reconfigure(ReconfigureFlags)
{
    const KConfigGroup g = effects->config()->group(QStringLiteral("Effect-tahoecursor"));
    m_stretchEnabled = g.readEntry("Stretch", true);
    m_stretchAmount = g.readEntry("StretchAmount", 1.0);
    m_bounceEnabled = g.readEntry("ClickBounce", true);
    m_dentEnabled = g.readEntry("ScreenPress", true);
    m_rippleEnabled = g.readEntry("Ripple", true);
    m_lensEnabled = g.readEntry("MoveLens", false);
    m_dentRadius = g.readEntry("PressRadius", 140.0);
    m_dentDepth = g.readEntry("PressDepth", 1.0);
    m_dentFollow = g.readEntry("PressFollow", true);
    m_rippleStrength = g.readEntry("RippleStrength", 1.0);
    m_rippleSize = g.readEntry("RippleSize", 220.0);
    m_stretchMax = g.readEntry("StretchMax", 1.5);
    m_stretchSpeed = g.readEntry("StretchSpeed", 1400.0);
    m_flipY = g.readEntry("FlipY", true);
    giveCursorBack(); // trocar de modo com o cursor tomado deixaria o item errado
    m_windMode = !m_windShaderFailed && g.readEntry("Motion", QStringLiteral("wind")) != QLatin1String("stretch");
    m_windStrength = g.readEntry("WindStrength", 1.0);
}

int TahoeCursorEffect::requestedEffectChainPosition() const
{
    // depois de quase tudo, pra distorcer a imagem final
    return 95;
}

bool TahoeCursorEffect::isActive() const
{
    return m_ticking || m_cursorHidden;
}

bool TahoeCursorEffect::cursorAnimating() const
{
    return !m_stretch.settled() || m_stretch.value > 0.002 || windAnimating()
        || !m_clickScale.settled() || std::abs(m_clickScale.value - 1.0) > 0.002;
}

bool TahoeCursorEffect::windAnimating() const
{
    return m_stretchEnabled && m_windMode
        && (!m_windX.settled() || !m_windY.settled() || std::hypot(m_windX.value, m_windY.value) > 0.002);
}

bool TahoeCursorEffect::screenAnimating() const
{
    const bool dent = m_dentEnabled && (!m_dent.settled() || std::abs(m_dent.value) > 0.001);
    const bool ripple = m_rippleEnabled && m_rippleTime >= 0.0;
    const bool lens = m_lensEnabled && m_stretch.value > 0.002;
    return dent || ripple || lens;
}

void TahoeCursorEffect::pointerMotion(PointerMotionEvent *event)
{
    const QPointF delta = event->position - m_lastPos;
    m_lastPos = event->position;
    if (event->warp) {
        return;
    }
    // a velocidade é medida por frame no tick(): mouse e monitor rodam em ritmos
    // diferentes e medir por evento deixa o esticar pulsando
    m_motionAccum += delta;
    wake();
}

void TahoeCursorEffect::pointerButton(PointerButtonEvent *event)
{
    if (event->button != Qt::LeftButton && event->button != Qt::RightButton && event->button != Qt::MiddleButton) {
        return;
    }
    if (event->state == PointerButtonState::Pressed) {
        press(event->position);
    } else {
        release(event->position);
    }
}

void TahoeCursorEffect::press(const QPointF &pos)
{
    ++m_pressed;
    if (m_bounceEnabled) {
        m_clickScale.stiffness = 900.0;
        m_clickScale.damping = 40.0;
        m_clickScale.target = 0.74;
    }
    if (m_dentEnabled) {
        m_dent.stiffness = 600.0;
        m_dent.damping = 38.0;
        m_dent.target = m_dentDepth;
        m_dentCenter = pos;
    }
    wake();
}

void TahoeCursorEffect::release(const QPointF &pos)
{
    m_pressed = std::max(0, m_pressed - 1);
    if (m_pressed > 0) {
        return;
    }
    // molas frouxas na volta = passa do ponto e quica
    m_clickScale.stiffness = 700.0;
    m_clickScale.damping = 13.0;
    m_clickScale.target = 1.0;

    m_dent.stiffness = 420.0;
    m_dent.damping = 11.0;
    m_dent.target = 0.0;

    if (m_rippleEnabled) {
        m_rippleCenter = m_dentEnabled ? m_dentCenter : pos;
        m_rippleTime = 0.0;
    }
    wake();
}

void TahoeCursorEffect::wake()
{
    m_giveBackTimer.stop();
    if (!m_ticking) {
        m_ticking = true;
        m_lastTick = std::chrono::steady_clock::now() - std::chrono::milliseconds(8);
        m_motionAccum = QPointF();
    }
    if (screenAnimating()) {
        effects->addRepaintFull();
    } else {
        const QPointF p = m_cursor->pos();
        effects->addRepaint(RectF(p.x() - 128, p.y() - 128, 256, 256));
    }
    if (drawsOwnCursor()) {
        effects->addRepaint(m_lastWindRect);
        effects->addRepaint(windCursorRect());
    }
}

void TahoeCursorEffect::tick(std::chrono::steady_clock::time_point now)
{
    const double elapsed = std::chrono::duration<double>(now - m_lastTick).count();
    if (elapsed <= 0.0) {
        return; // mesmo frame (outra tela)
    }
    const double dt = std::clamp(elapsed, 0.002, 0.05);
    m_lastTick = now;

    // velocidade do frame, suavizada no tempo (não por evento)
    const QPointF instant = m_motionAccum / dt;
    m_motionAccum = QPointF();
    m_velocity += (instant - m_velocity) * (1.0 - std::exp(-dt / 0.05));

    const double speed = std::hypot(m_velocity.x(), m_velocity.y());

    // eixo do esticar em ângulo dobrado: ir e voltar pros lados é o mesmo eixo, então não
    // vira; e girar é suave, mais rápido quanto mais rápido o mouse
    if (speed > 1.0) {
        const double a = 2.0 * std::atan2(m_velocity.y(), m_velocity.x());
        const double k = (1.0 - std::exp(-dt / 0.035)) * std::min(1.0, speed / 300.0);
        m_axis += (QPointF(std::cos(a), std::sin(a)) - m_axis) * k;
        m_angle = 0.5 * std::atan2(m_axis.y(), m_axis.x());
    }
    // zona morta: a mão apoiada no mouse manda tremidinhas de 1 px que deixavam o efeito
    // desenhando o cursor pra sempre
    const double amount = std::clamp((speed - 40.0) / m_stretchSpeed, 0.0, 1.0) * m_stretchAmount;
    m_stretch.target = ((m_stretchEnabled && !m_windMode) || m_lensEnabled) ? amount : 0.0;

    // vento: as pontas vão pra trás do movimento, mais quanto mais rápido
    const QPointF wind = (m_stretchEnabled && m_windMode && amount > 0.0) ? m_velocity / speed * amount : QPointF();
    m_windX.target = wind.x();
    m_windY.target = wind.y();
    m_windX.step(dt);
    m_windY.step(dt);

    m_stretch.step(dt);
    m_clickScale.step(dt);
    m_dent.step(dt);

    // segurando o clique, o afundado segue o cursor com um leve atraso
    if (m_pressed > 0 && m_dentFollow) {
        const double k = 1.0 - std::exp(-dt / 0.035);
        m_dentCenter += (m_cursor->pos() - m_dentCenter) * k;
    }

    if (m_rippleTime >= 0.0) {
        m_rippleTime += dt;
        if (m_rippleTime > s_rippleDuration) {
            m_rippleTime = -1.0;
        }
    }

    const bool wantsCursor = (m_stretchEnabled || m_bounceEnabled) && cursorAnimating();
    if (wantsCursor) {
        takeCursor();
        updateCursorItem();
    }
}

void TahoeCursorEffect::recreateCursorItem()
{
    m_cursorItem = std::make_unique<CursorItem>(effects->scene()->overlayItem());
    m_cursorItem->setPosition(m_cursor->pos());
    // no vento o item fica invisível na tela: a gente desenha ele numa textura e dobra.
    // É o mesmo item que o KWin usa, então mostra qualquer cursor (luvinha, texto, apps X11).
    m_cursorItem->setVisible(!m_windMode);
    updateCursorItem();
}

void TahoeCursorEffect::takeCursor()
{
    if (m_cursorHidden) {
        return;
    }
    effects->hideCursor();
    m_cursorHidden = true;
    recreateCursorItem();
    if (m_windMode) {
        effects->addRepaint(windCursorRect());
    }
}

void TahoeCursorEffect::giveCursorBack()
{
    if (!m_cursorHidden) {
        return;
    }
    m_cursorItem.reset();
    effects->showCursor();
    m_cursorHidden = false;
    effects->addRepaint(m_lastWindRect);
}

void TahoeCursorEffect::updateCursorItem()
{
    if (!m_cursorItem) {
        return;
    }
    if (m_windMode) {
        m_cursorItem->setTransform(QTransform()); // dobra e quique ficam no shader
        return;
    }
    const double s = (m_stretchEnabled && !m_windMode) ? std::max(0.0, m_stretch.value) : 0.0;
    const double along = 1.0 + m_stretchMax * s;
    const double across = 1.0 / std::sqrt(along);
    const double click = m_bounceEnabled ? m_clickScale.value : 1.0;

    QTransform t;
    t.rotateRadians(m_angle);
    t.scale(along * click, across * click);
    t.rotateRadians(-m_angle);
    m_cursorItem->setTransform(t);
}

void TahoeCursorEffect::prePaintScreen(ScreenPrePaintData &data)
{
    if (m_ticking) {
        // anima pro instante em que o frame aparece na tela, não pra agora: passos regulares
        tick(data.frame ? data.frame->targetPageflipTime() : std::chrono::steady_clock::now());
    }
    effects->prePaintScreen(data);
}

void TahoeCursorEffect::postPaintScreen()
{
    effects->postPaintScreen();

    // O item do cursor fica invisível no vento, e o KWin só avisa "frame desenhado" pra item
    // visível. Apps X11 (Brave) esperam esse aviso pra mandar a próxima imagem do cursor:
    // sem ele a luvinha nunca chegava. Então a gente avisa.
    if (drawsOwnCursor()) {
        if (auto source = qobject_cast<SurfaceCursorSource *>(Cursors::self()->currentCursor()->source())) {
            if (SurfaceInterface *surface = source->surface()) {
                const auto now = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch());
                surface->frameRendered(now.count());
            }
        }
    }

    if (!m_ticking) {
        return;
    }
    const bool screen = screenAnimating();
    if (cursorAnimating() || screen) {
        if (screen) {
            effects->addRepaintFull();
        } else {
            const QPointF p = m_cursor->pos();
            effects->addRepaint(RectF(p.x() - 128, p.y() - 128, 256, 256));
        }
        if (drawsOwnCursor()) {
            effects->addRepaint(m_lastWindRect);
            effects->addRepaint(windCursorRect());
        }
        return;
    }

    // tudo parado: devolve o cursor de hardware e limpa a tela uma última vez
    m_stretch.value = m_stretch.velocity = 0.0;
    m_windX.value = m_windX.velocity = m_windY.value = m_windY.velocity = 0.0;
    m_clickScale.value = 1.0;
    m_clickScale.velocity = 0.0;
    m_dent.value = m_dent.velocity = 0.0;
    m_velocity = QPointF();
    m_ticking = false;
    updateCursorItem();
    m_giveBackTimer.start();
    effects->addRepaintFull();
}

TahoeCursorEffect::OffscreenData *TahoeCursorEffect::ensureOffscreen(const RenderTarget &renderTarget, const RenderViewport &viewport, LogicalOutput *screen)
{
    const QSize nativeSize = viewport.deviceSize();
    OffscreenData &data = m_offscreen[screen];
    data.color = renderTarget.colorDescription();

    const GLenum format = renderTarget.colorDescription() == ColorDescription::sRGB ? GL_RGBA8 : GL_RGBA16F;
    if (!data.texture || data.texture->size() != nativeSize || data.texture->internalFormat() != format) {
        data.texture = GLTexture::allocate(format, nativeSize);
        if (!data.texture) {
            return nullptr;
        }
        data.texture->setFilter(GL_LINEAR);
        data.texture->setWrapMode(GL_CLAMP_TO_EDGE);
        data.framebuffer = std::make_unique<GLFramebuffer>(data.texture.get());
    }
    return &data;
}

GLShader *TahoeCursorEffect::ensureShader()
{
    if (!m_shader && !m_shaderFailed) {
        m_shader = ShaderManager::instance()->generateShaderFromFile(ShaderTrait::MapTexture, QString(), QStringLiteral(":/effects/tahoecursor/shaders/tahoecursor.frag"));
        m_shaderFailed = !m_shader;
    }
    return m_shader.get();
}

void TahoeCursorEffect::paintScreen(const RenderTarget &renderTarget, const RenderViewport &viewport, int mask, const Region &deviceRegion, LogicalOutput *screen)
{
    GLShader *shader = screenAnimating() ? ensureShader() : nullptr;
    OffscreenData *off = shader ? ensureOffscreen(renderTarget, viewport, screen) : nullptr;
    if (!off) {
        effects->paintScreen(renderTarget, viewport, mask, deviceRegion, screen);
        if (drawsOwnCursor()) {
            paintWindCursor(renderTarget, viewport);
        }
        return;
    }

    RenderTarget offTarget(off->framebuffer.get(), renderTarget.colorDescription());
    RenderViewport offViewport(viewport.renderRect(), viewport.scale(), offTarget, QPoint());
    GLFramebuffer::pushFramebuffer(off->framebuffer.get());
    effects->paintScreen(offTarget, offViewport, mask, deviceRegion, screen);
    GLFramebuffer::popFramebuffer();

    const RectF rect = viewport.renderRect();
    const QPointF origin = rect.topLeft();
    const double scale = viewport.scale();

    const double t = m_rippleTime >= 0.0 ? m_rippleTime / s_rippleDuration : 1.0;
    const double fade = (1.0 - t) * (1.0 - t);

    ShaderManager::instance()->pushShader(shader);
    QMatrix4x4 matrix;
    matrix.translate(rect.x() * scale, rect.y() * scale);
    shader->setUniform(GLShader::Mat4Uniform::ModelViewProjectionMatrix, viewport.projectionMatrix() * matrix);
    shader->setColorspaceUniforms(off->color, renderTarget.colorDescription(), RenderingIntent::Perceptual);
    shader->setUniform("screenSize", QVector2D(rect.width(), rect.height()));
    shader->setUniform("flipY", m_flipY ? 1.0f : 0.0f);

    shader->setUniform("dentCenter", QVector2D(m_dentCenter - origin));
    shader->setUniform("dent", float(m_dentEnabled ? m_dent.value : 0.0));
    shader->setUniform("dentRadius", float(m_dentRadius));

    shader->setUniform("rippleCenter", QVector2D(m_rippleCenter - origin));
    shader->setUniform("rippleRadius", float(15.0 + m_rippleSize * std::pow(t, 0.6)));
    shader->setUniform("rippleAmp", float(m_rippleTime >= 0.0 ? 6.0 * m_rippleStrength * fade : 0.0));
    shader->setUniform("rippleWidth", float(14.0 + 22.0 * t));

    shader->setUniform("lensCenter", QVector2D(m_cursor->pos() - origin));
    shader->setUniform("lens", float(m_lensEnabled ? std::max(0.0, m_stretch.value) : 0.0));
    shader->setUniform("lensRadius", 110.0f);

    off->texture->render(rect.size() * scale);
    ShaderManager::instance()->popShader();

    if (drawsOwnCursor()) {
        paintWindCursor(renderTarget, viewport);
    }
}

// ou superfície (apps X11, como o Brave com --ozone-platform=x11). Só roda quando o cursor
// troca, não todo frame.
// sem trocar a fonte: sem isso a gente ficava com a seta velha.
bool TahoeCursorEffect::drawsOwnCursor() const
{
    return m_windMode && m_cursorHidden && m_cursorItem;
}

// Quadrado onde o cursor do vento é desenhado: a imagem mais margem pra dobra e pro quique.
RectF TahoeCursorEffect::windCursorRect() const
{
    RectF geo = m_cursor->geometry();
    if (geo.isEmpty()) {
        geo = RectF(m_cursor->pos().x(), m_cursor->pos().y(), 32, 32);
    }
    const double half = std::max(geo.width(), geo.height()) * 0.5;
    const double margin = std::ceil(half * (0.9 * m_windStrength + 0.3)) + 4.0;
    return RectF(geo.x() - margin, geo.y() - margin, geo.width() + 2 * margin, geo.height() + 2 * margin);
}

void TahoeCursorEffect::paintWindCursor(const RenderTarget &renderTarget, const RenderViewport &viewport)
{
    const RectF geo = m_cursor->geometry();
    if (geo.isEmpty()) {
        return; // app escondeu o cursor
    }
    if (!m_windShader && !m_windShaderFailed) {
        m_windShader = ShaderManager::instance()->generateShaderFromFile(ShaderTrait::MapTexture, QString(), QStringLiteral(":/effects/tahoecursor/shaders/wind.frag"));
        m_windShaderFailed = !m_windShader;
    }
    const double scale = viewport.scale();

    // 1) desenha o item do cursor do KWin numa textura do tamanho do cursor
    const QSize deviceSize(std::ceil(geo.width() * scale), std::ceil(geo.height() * scale));
    const GLenum format = renderTarget.colorDescription() == ColorDescription::sRGB ? GL_RGBA8 : GL_RGBA16F;
    if (m_windShader && (!m_cursorTexture || m_cursorTexture->size() != deviceSize || m_cursorTexture->internalFormat() != format)) {
        m_cursorTexture = GLTexture::allocate(format, deviceSize);
        m_cursorFbo.reset();
        if (m_cursorTexture) {
            m_cursorTexture->setFilter(GL_LINEAR);
            m_cursorTexture->setWrapMode(GL_CLAMP_TO_EDGE);
            m_cursorFbo = std::make_unique<GLFramebuffer>(m_cursorTexture.get());
        }
    }
    if (!m_windShader || !m_cursorFbo || !m_cursorFbo->valid()) {
        // sem como desenhar: volta pro efeito antigo em vez de sumir com o cursor
        m_windMode = false;
        QTimer::singleShot(0, this, [this]() {
            giveCursorBack();
        });
        return;
    }
    m_cursorItem->setPosition(m_cursor->pos());
    {
        RenderTarget target(m_cursorFbo.get(), renderTarget.colorDescription());
        RenderViewport cursorViewport(geo, scale, target, QPoint());
        GLFramebuffer::pushFramebuffer(m_cursorFbo.get());
        glClearColor(0, 0, 0, 0);
        glClear(GL_COLOR_BUFFER_BIT);
        effects->scene()->renderer()->renderItem(target, cursorViewport, m_cursorItem.get(), 0, Region::infinite(), WindowPaintData(), {}, {});
        GLFramebuffer::popFramebuffer();
    }

    // 2) desenha a textura na tela, dobrada pelo vento
    const RectF quad = windCursorRect();
    m_lastWindRect = quad;
    const double half = std::max(geo.width(), geo.height()) * 0.5;
    const QPointF bend = -QPointF(m_windX.value, m_windY.value) * (0.9 * half * m_windStrength);
    const double click = m_bounceEnabled ? m_clickScale.value : 1.0;
    const QPointF margin = geo.topLeft() - quad.topLeft();
    const bool vDown = m_cursorTexture->contentTransform().kind() == OutputTransform::FlipY;

    glEnable(GL_BLEND);
    glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
    ShaderManager::instance()->pushShader(m_windShader.get());
    QMatrix4x4 matrix = viewport.projectionMatrix();
    matrix.translate(quad.x() * scale, quad.y() * scale);
    m_windShader->setUniform(GLShader::Mat4Uniform::ModelViewProjectionMatrix, matrix);
    m_windShader->setColorspaceUniforms(renderTarget.colorDescription(), renderTarget.colorDescription(), RenderingIntent::Perceptual);
    m_windShader->setUniform("quadSize", QVector2D(quad.width(), quad.height()));
    m_windShader->setUniform("margin", QVector2D(margin));
    m_windShader->setUniform("cursorSize", QVector2D(geo.width(), geo.height()));
    m_windShader->setUniform("bend", QVector2D(bend));
    m_windShader->setUniform("scale", float(click));
    m_windShader->setUniform("vDown", vDown ? 1.0f : 0.0f);
    m_cursorTexture->render(quad.size() * scale);
    ShaderManager::instance()->popShader();
    glDisable(GL_BLEND);
}

QString TahoeCursorEffect::debug(const QString &parameter) const
{
    auto self = const_cast<TahoeCursorEffect *>(this);
    const QStringList args = parameter.split(QLatin1Char(' '), Qt::SkipEmptyParts);
    const QString cmd = args.value(0);
    const QPointF at = args.size() >= 3 ? QPointF(args[1].toDouble(), args[2].toDouble()) : m_cursor->pos();

    if (cmd == QLatin1String("press")) {
        self->press(at);
    } else if (cmd == QLatin1String("release")) {
        self->release(at);
    } else if (cmd == QLatin1String("demo")) {
        self->press(at);
        QTimer::singleShot(350, self, [self, at]() {
            self->release(at);
        });
    } else if (cmd == QLatin1String("flip")) {
        self->m_flipY = !m_flipY;
    }
    return QStringLiteral("ticking=%1 hidden=%2 stretch=%3 click=%4 dent=%5 ripple=%6 flipY=%7 wind=%8 own=%9 src=%10 geo=%11x%12")
        .arg(m_ticking)
        .arg(m_cursorHidden)
        .arg(m_stretch.value, 0, 'f', 3)
        .arg(m_clickScale.value, 0, 'f', 3)
        .arg(m_dent.value, 0, 'f', 3)
        .arg(m_rippleTime, 0, 'f', 3)
        .arg(m_flipY)
        .arg(m_windMode)
        .arg(drawsOwnCursor())
        .arg(m_cursor->source() ? QString::fromLatin1(m_cursor->source()->metaObject()->className()) : QStringLiteral("nenhuma"))
        .arg(m_cursor->geometry().width())
        .arg(m_cursor->geometry().height());
}

} // namespace KWin

#include "moc_tahoecursor.cpp"
