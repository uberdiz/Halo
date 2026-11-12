// The projector's top: concentric glowing rings that pulse outward, on a transparent disc.
VARYING vec2 vUV;

void MAIN()
{
    vec2 p = vUV * 2.0 - 1.0;
    float r = length(p);
    float rings = 0.0;
    rings += smoothstep(0.035, 0.0, abs(r - 0.92));
    rings += smoothstep(0.025, 0.0, abs(r - 0.70)) * 0.8;
    rings += smoothstep(0.020, 0.0, abs(r - 0.46)) * 0.6;
    float pulse = smoothstep(0.06, 0.0, abs(r - fract(uTime * 0.35))) * 0.7;
    float core = smoothstep(0.45, 0.0, r) * 0.35;
    float a = clamp(rings + pulse + core, 0.0, 1.0) * step(r, 1.0);
    FRAGCOLOR = vec4(uTint.rgb * a * 1.4, a);
}
