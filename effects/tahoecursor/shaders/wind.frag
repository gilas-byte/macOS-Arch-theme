#version 140

#include "colormanagement.glsl"

// Desenha a imagem do cursor dobrada pelo vento. Só o cursor: o resto da tela não passa aqui.

uniform sampler2D sampler;
uniform vec2 quadSize;   // px do quadrado desenhado (cursor + margem)
uniform vec2 margin;     // px de margem em volta da imagem do cursor
uniform vec2 cursorSize; // px da imagem do cursor
uniform vec2 bend;       // px que as pontas vão pra trás (contra o movimento)
uniform float scale;     // encolher do clique
uniform float vDown;     // 1 = coordenada v da textura cresce pra baixo na tela

in vec2 texcoord0;

out vec4 fragColor;

void main()
{
    vec2 uv = texcoord0;
    if (vDown < 0.5) {
        uv.y = 1.0 - uv.y;
    }
    vec2 p = uv * quadSize - margin; // px na imagem do cursor, y pra baixo
    vec2 c = cursorSize * 0.5;
    float halfSize = max(cursorSize.x, cursorSize.y) * 0.5;

    // as pontas de lado (perpendiculares ao movimento) vão pra trás em parábola, o meio
    // fica; o deslocamento é ao longo do movimento, então o inverso é exato
    float len = length(bend);
    if (len > 0.01) {
        vec2 n = vec2(-bend.y, bend.x) / len;
        float s = dot(p - c, n) / halfSize;
        p -= bend * s * s;
    }
    p = c + (p - c) / scale;

    vec2 src = p / cursorSize;
    if (any(lessThan(src, vec2(0.0))) || any(greaterThan(src, vec2(1.0)))) {
        discard;
    }
    if (vDown < 0.5) {
        src.y = 1.0 - src.y;
    }
    vec4 col = sourceEncodingToNitsInDestinationColorspace(texture(sampler, src));
    fragColor = nitsToDestinationEncoding(col);
}
