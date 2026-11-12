"""Build SAINT from scratch in Blender 5.2 with MPFB 2 (CC0 MakeHuman assets).

Run inside Blender (Blender MCP execute, or: blender -b -P build_saint.py). Idempotent: clears the scene.
Set CLOTHES / HAIR below to try variants. Everything after the MPFB base (materials, hair, studio) is
applied by the later scripts in this folder.
"""
import bpy

CLOTHES = ["female_casualsuit01/female_casualsuit01.mhclo", "shoes03/shoes03.mhclo"]
HAIR = "long01/long01.mhclo"          # stock hair cards are replaced by curve hair (hair_curves.py)

for o in list(bpy.data.objects):
    if o.type != "LIGHT" and o.type != "CAMERA":
        bpy.data.objects.remove(o, do_unlink=True)
bpy.data.orphans_purge(do_recursive=True)

from bl_ext.blender_org.mpfb.services.humanservice import HumanService as H

info = H._create_default_human_info_dict()
info["phenotype"].update({
    "gender": 0.0, "age": 0.42, "muscle": 0.52, "weight": 0.44, "proportions": 0.8, "height": 0.62,
    "cupsize": 0.5, "firmness": 0.55, "race": {"asian": 0.25, "caucasian": 0.5, "african": 0.25}})
info.update({
    "rig": "game_engine", "eyes": "high-poly/high-poly.mhclo", "eyebrows": "eyebrow010/eyebrow010.mhclo",
    "eyelashes": "eyelashes02/eyelashes02.mhclo", "teeth": "teeth_base/teeth_base.mhclo",
    "tongue": "tongue01/tongue01.mhclo", "hair": HAIR,
    "skin_mhmat": "young_caucasian_female/young_caucasian_female.mhmat", "skin_material_type": "ENHANCED_SSS",
    "eyes_material_type": "PROCEDURAL_EYES", "clothes": CLOTHES})
s = H.get_default_deserialization_settings()
s["subdiv_levels"] = 0
human = H.deserialize_from_dict(info, s)

# skin: warm, natural tone with visible pores and real subsurface
g = next(n for n in human.active_material.node_tree.nodes if n.bl_idname == "ShaderNodeGroup")
for k, v in {"colorMixIn": (0.80, 0.50, 0.34, 1), "colorMixInStrength": 0.32, "Brightness": -0.06,
             "Contrast": 0.05, "Roughness": 0.48, "Pore strength": 0.28, "SSS strength": 0.35}.items():
    g.inputs[k].default_value = v
# eyes: warm hazel (a nod to the orange HalOS star)
eyes = next(o for o in human.parent.children if o.name.startswith("Human.high-poly"))
e = next(n for n in eyes.active_material.node_tree.nodes if n.bl_idname == "ShaderNodeGroup")
e.inputs["IrisMajorColor"].default_value = (0.30, 0.16, 0.05, 1)
e.inputs["IrisMinorColor"].default_value = (0.09, 0.05, 0.02, 1)
e.inputs["EyeWhiteColor"].default_value = (0.93, 0.91, 0.89, 1)
