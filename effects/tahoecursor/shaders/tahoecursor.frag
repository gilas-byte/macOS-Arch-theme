#version 140

#include "colormanagement.glsl"

uniform sampler2D sampler;
uniform vec2 screenSize; // px lógicos da tela
uniform float flipY;

uniform vec2 dentCenter;
uniform float dent;       // >0 afunda, <0 estufa (rebote)
uniform float dentRadius;

uniform vec2 rippleCenter;
uniform float rippleRadius;
uniform float rippleAmp;
uniform float rippleWidth;

uniform vec2 lensCenter;
uniform float lens;
uniform float lensRadius;

in vec2 texcoord0;

out vec4 fragColor;

vec2 toPx(vec2 uv)
{
    vec2 p = uv * screenSize;
    if (flipY > 0.5) {
        p.y = screenSize.y - p.y;
    }
    return p;
}

vec2 toUv(vec2 p)
{
    if (flipY > 0.5) {
        p.y = screenSize.y - p.y;
    }
    return p / screenSize;
}

void main()
{
    vec2 p = toPx(texcoord0);
    vec2 q = p;
    float shade = 0.0;
    float light = 0.0;

    // Tela afundando: amostra mais longe do centro, então o miolo encolhe como uma lente côncava.
    if (dent != 0.0) {
        vec2 d = p - dentCenter;
        float r = length(d);
        float f = 1.0 - smoothstep(0.0, dentRadius, r);
        f = f * f;
        q += d * dent * 0.45 * f;
        shade += dent * 0.22 * f;
        // borda do buraco pega luz
        float rim = exp(-pow((r - dentRadius * 0.55) / (dentRadius * 0.18), 2.0));
        light += max(dent, 0.0) * 0.10 * rim;
    }

    // Onda saindo do clique
    if (rippleAmp > 0.0) {
        vec2 d = p - rippleCenter;
        float r = length(d);
        float x = (r - rippleRadius) / rippleWidth;
        float w = exp(-x * x) * sin(x * 3.14159);
        if (r > 0.001) {
            q -= (d / r) * w * rippleAmp;
        }
        light += 0.012 * w * rippleAmp;
    }

    // Lente seguindo o cursor (aumenta o que está embaixo)
    if (lens > 0.0) {
        vec2 d = p - lensCenter;
        float r = length(d);
        float f = 1.0 - smoothstep(0.0, lensRadius, r);
        q -= d * lens * 0.35 * f * f;
    }

    vec4 c = sourceEncodingToNitsInDestinationColorspace(texture(sampler, toUv(q)));
    c.rgb *= clamp(1.0 - shade + light, 0.0, 2.0);
    fragColor = nitsToDestinationEncoding(c);
}
