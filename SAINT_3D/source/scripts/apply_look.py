"""Point SAINT's suit, hair and shoes at the recoloured textures (recolor_textures.py) and set fabric response.
Run in Blender after build_saint.py (with CLOTHES = casualsuit01 + shoes03 and HAIR = long01)."""
import bpy
from pathlib import Path

TEX = Path(r"C:\Users\sebas\Documents\HalOS\SAINT_3D\textures")


def obj(prefix):
    return next(o for o in bpy.data.objects if o.name.startswith("Human." + prefix))


def set_diffuse(o, png, roughness, sheen=0.0):
    m = o.active_material
    nt = m.node_tree
    tex = nt.nodes["diffuseTexture"]
    tex.image = bpy.data.images.load(str(TEX / png), check_existing=True)
    bsdf = nt.nodes["Principled BSDF"]
    mix = nt.nodes.get("diffuseIntensity")          # MPFB multiplies by an intensity colour: bypass it
    if mix:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    if sheen:
        bsdf.inputs["Sheen Weight"].default_value = sheen
        bsdf.inputs["Sheen Tint"].default_value = (0.25, 0.27, 0.3, 1)   # a dark fabric's sheen, not white
    for l in list(nt.links):                       # MakeHuman's jeans normal map has rips and fades: drop it
        if l.to_socket == bsdf.inputs["Normal"] and o.name.startswith("Human.female_casualsuit01"):
            nt.links.remove(l)
    tex.image.reload()
    return bsdf


suit = set_diffuse(obj("female_casualsuit01"), "saint_suit_diffuse.png", 0.85, sheen=0.15)
suit.inputs["Specular IOR Level"].default_value = 0.18              # matte knit / wool, little glare
set_diffuse(obj("shoes03"), "saint_shoes_diffuse.png", 0.35)
hb = set_diffuse(obj("long01"), "saint_hair_diffuse.png", 0.55)
hb.inputs["Specular IOR Level"].default_value = 0.3     # soft sheen; the cards' flat tops glare white otherwise
hb.inputs["Coat Weight"].default_value = 0.0
hb.inputs["Anisotropic"].default_value = 0.6

# skin: the blended mid-tone texture inside MPFB's enhanced SSS group; no extra tint
human = bpy.data.objects["Human"]
g = next(n for n in human.active_material.node_tree.nodes if n.bl_idname == "ShaderNodeGroup")
g.node_tree.nodes["DiffuseTexture"].image = bpy.data.images.load(str(TEX / "saint_skin_diffuse.png"), check_existing=True)
g.node_tree.nodes["DiffuseTexture"].image.reload()
for k, v in {"colorMixInStrength": 0.0, "Brightness": 0.0, "Contrast": 0.04, "Roughness": 0.5,
             "Pore strength": 0.3, "SSS strength": 0.4}.items():
    g.inputs[k].default_value = v
