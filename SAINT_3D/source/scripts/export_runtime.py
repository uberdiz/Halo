"""Make SAINT's optimized runtime copy and export it to ../../exports/SAINT.glb.

Run in Blender on SAINT.blend (after build_saint.py, apply_look.py and the face targets are loaded).
The editable source is not changed: everything happens on a copy, and the .blend is not saved.

1. copy the character (MPFB ExportService), bake masks, remove helper geometry
2. fold MPFB's body-shape ("$md…") keys into the Basis so only the 67 face keys remain
3. give eyelashes and eyebrows the same face keys (Surface Deform, sampled per key), so a blink closes the lashes
4. downscale textures for real-time use and export glTF binary with skin, morph targets and materials
"""
import os
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(r"C:\Users\sebas\Documents\HalOS\SAINT_3D")
OUT = ROOT / "exports" / "SAINT.glb"
TEX_MAX = 2048

from bl_ext.blender_org.mpfb.services.exportservice import ExportService as E

src = bpy.data.objects["Human"]
rig = E.create_character_copy(src.parent, name_suffix="_rt")
body = next(c for c in rig.children if c.type == "MESH" and c.name.startswith("Human_rt") or c.name == "Human_rt")
E.bake_modifiers_remove_helpers(body, bake_masks=True, remove_helpers=True, also_proxy=True)

# --- 2. fold body-shape keys into Basis
kb = body.data.shape_keys.key_blocks
n = len(body.data.vertices)


def co(k):
    a = np.empty(n * 3, np.float32)
    k.data.foreach_get("co", a)
    return a


basis = co(kb["Basis"])
shaped = basis.copy()
for k in kb:
    if k.name.startswith("$md"):
        shaped += (co(k) - basis) * k.value
for k in kb:
    if k.name != "Basis" and not k.name.startswith("$md"):
        k.data.foreach_set("co", shaped + (co(k) - basis))
        k.value = 0.0
kb["Basis"].data.foreach_set("co", shaped)
body.data.vertices.foreach_set("co", shaped)
for k in [k for k in kb if k.name.startswith("$md")]:
    body.shape_key_remove(k)
face_keys = [k.name for k in body.data.shape_keys.key_blocks if k.name != "Basis"]

# --- 3. lashes and brows follow the face keys
for part in [c for c in rig.children if c.type == "MESH" and ("eyelash" in c.name or "eyebrow" in c.name)]:
    sd = part.modifiers.new("SAINT_follow_face", "SURFACE_DEFORM")
    sd.target = body
    bpy.context.view_layer.objects.active = part
    bpy.ops.object.surfacedeform_bind(modifier=sd.name)
    if not part.data.shape_keys:
        part.shape_key_add(name="Basis")
    m = len(part.data.vertices)
    for name in face_keys:
        body.data.shape_keys.key_blocks[name].value = 1.0
        dg = bpy.context.evaluated_depsgraph_get()
        ev = part.evaluated_get(dg)
        a = np.empty(m * 3, np.float32)
        ev.data.vertices.foreach_get("co", a)
        part.shape_key_add(name=name, from_mix=False).data.foreach_set("co", a)
        body.data.shape_keys.key_blocks[name].value = 0.0
    part.modifiers.remove(sd)

# --- 3b. glTF-friendly materials for the body (MPFB's SSS node group) and eyes (procedural iris)
def principled(name, image, roughness, sss=0.0):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = image
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = roughness
    b.inputs["Subsurface Weight"].default_value = sss
    return m


skin_img = bpy.data.images.load(str(ROOT / "textures" / "saint_skin_diffuse.png"), check_existing=True)
body.data.materials.clear()
body.data.materials.append(principled("SAINT_skin", skin_img, 0.5, sss=0.15))

eyes = next(c for c in rig.children if c.type == "MESH" and "high-poly" in c.name)
eye_png = ROOT / "textures" / "saint_eyes_baked.png"
if not eye_png.exists():                       # bake the procedural eye shader's colour once
    img = bpy.data.images.new("saint_eyes_baked", 1024, 1024)
    mat = eyes.active_material
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = img
    mat.node_tree.nodes.active = node
    bpy.ops.object.select_all(action="DESELECT")
    eyes.select_set(True)
    bpy.context.view_layer.objects.active = eyes
    sc = bpy.context.scene
    engine, sc.render.engine = sc.render.engine, "CYCLES"
    sc.render.bake.use_pass_direct = sc.render.bake.use_pass_indirect = False
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=8)
    sc.render.engine = engine
    img.filepath_raw = str(eye_png)
    img.file_format = "PNG"
    img.save()
    mat.node_tree.nodes.remove(node)
eyes.data.materials.clear()
eye_img = bpy.data.images.load(str(eye_png), check_existing=True)
eyes.data.materials.append(principled("SAINT_eyes", eye_img, 0.25))
# the outer cornea shell maps to the black (unused) part of the eye texture: give it its own clear material
cornea = bpy.data.materials.new("SAINT_cornea")
cb = cornea.node_tree.nodes["Principled BSDF"]
cb.inputs["Base Color"].default_value = (1, 1, 1, 1)
cb.inputs["Roughness"].default_value = 0.02
cb.inputs["Alpha"].default_value = 0.08          # glTF alphaMode BLEND: a wet highlight, iris visible below
cornea.surface_render_method = "BLENDED"
eyes.data.materials.append(cornea)
px = np.array(eye_img.pixels[:], np.float32).reshape(eye_img.size[1], eye_img.size[0], 4)
uv = eyes.data.uv_layers.active.data
for poly in eyes.data.polygons:
    u = sum(uv[i].uv[0] for i in poly.loop_indices) / poly.loop_total
    v = sum(uv[i].uv[1] for i in poly.loop_indices) / poly.loop_total
    x, y = min(int(u * eye_img.size[0]), eye_img.size[0] - 1), min(int(v * eye_img.size[1]), eye_img.size[1] - 1)
    if px[y, x, :3].max() < 0.02 and not (0.2 < u < 0.4 and 0.2 < v < 0.4) and not (0.6 < u < 0.8 and 0.6 < v < 0.8):
        poly.material_index = 1                      # black outside the pupils = cornea faces

# --- 4. textures: real-time size (copies, so the source keeps full resolution)
for o in [rig, *rig.children]:
    for slot in getattr(o, "material_slots", []):
        if not slot.material or not slot.material.node_tree:
            continue
        for node in slot.material.node_tree.nodes:
            img = getattr(node, "image", None)
            if img and max(img.size) > TEX_MAX:
                small = img.copy()
                small.scale(TEX_MAX, TEX_MAX * img.size[1] // img.size[0])
                node.image = small

bpy.ops.object.select_all(action="DESELECT")
for o in [rig, *rig.children]:
    o.select_set(True)
bpy.context.view_layer.objects.active = rig
OUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(OUT), export_format="GLB", use_selection=True, export_skins=True,
                          export_morph=True, export_morph_normal=False, export_animations=False,
                          export_image_format="AUTO", export_yup=True, export_apply=False)
stats = {"file": str(OUT), "mb": round(os.path.getsize(OUT) / 2 ** 20, 1), "face_keys": len(face_keys),
         "tris": sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in rig.children if o.type == "MESH")}
for o in [*rig.children, rig]:                  # drop the runtime copy from the source scene
    bpy.data.objects.remove(o, do_unlink=True)
print("SAINT runtime export:", stats)
