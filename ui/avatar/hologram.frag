// SAINT hologram (shaded CustomMaterial, so Qt keeps skinning + morph targets): the model's own texture,
// lit softly and tinted the accent colour so the face reads like a portrait in coloured light, plus a fresnel
// rim, fine scanlines, a slow scan band and a fade below the bust. Output is emission only (no PBR lighting).
void MAIN()
{
    vec3 n = normalize(VAR_WORLD_NORMAL);
    vec3 v = normalize(CAMERA_POSITION - VAR_WORLD_POSITION);
    float facing = clamp(abs(dot(n, v)), 0.0, 1.0);
    float fres = pow(1.0 - facing, 2.5);
    vec4 tex = texture(baseMap, UV0);
    float lum = dot(tex.rgb, vec3(0.299, 0.587, 0.114));
    float light = 0.35 + 0.65 * max(dot(n, normalize(vec3(0.35, 0.55, 0.75))), 0.0);
    float y = VAR_WORLD_POSITION.y;
    float scan = 0.92 + 0.08 * sin(y * 1100.0 - uTime * 4.0);
    float band = smoothstep(0.97, 1.0, sin(y * 3.0 - uTime * 0.9));
    float fade = smoothstep(uCutY - 0.09, uCutY + 0.07, y);
    vec3 c = uTint.rgb * (pow(lum, 0.8) * light * 1.7 * scan + fres * 1.3 + band * 0.35);
    c += vec3(1.0) * pow(lum * light, 3.0) * 0.25;
    BASE_COLOR = vec4(0.0, 0.0, 0.0, clamp(fade * tex.a, 0.0, 1.0));
    EMISSIVE_COLOR = clamp(c, 0.0, 1.0);
    METALNESS = 0.0;
    ROUGHNESS = 1.0;
    SPECULAR_AMOUNT = 0.0;
}
