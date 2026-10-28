"""Cycles production pipeline. The browser remains the sequence editor.

Run with the retained bpy Python runtime. `stills` is the default; a full
sequence is rendered only with the explicit `render` command.
"""
import argparse
import hashlib
import json
import math
import shutil
import struct
import subprocess
from pathlib import Path

import bpy
import cv2
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
BLEND = ROOT / "EnclosedArray.blend"
ASSETS = ROOT / "assets"
TEXTURES = ASSETS / "textures"
SHOTS = ("near", "switch", "whole")
MM = 0.001
# Retained balanced pin key and neutral world; a weak reflected window gives the top a local sheen.
LIGHT = {"azimuth_deg": 35, "elevation_deg": 50, "distance_m": 1.1, "size_m": (.45, .30), "energy_w": 12, "ambient": .30}
PIN = {"base_colours": ((.90, .91, .92, 1), (.93, .94, .95, 1)), "roughness_range": (.22, .32),
       "ior": 1.48, "transmission_weight": 1, "subsurface_weight": 0,
       "scatter_density_per_m": 2500, "scatter_anisotropy": 0,
       "absorption_colour": (.55, .65, .75, 1), "absorption_density_per_m": 500,
       "bevel_radius_m": .000008, "bump_strength": 0}
SWITCH_ACTUATOR = {"base_colour": (.008, .0085, .009), "roughness_range": (.40, .50),
                   "grain_scale_per_m": 15000, "bump_distance_m": .000003, "bump_strength": .20,
                   "bevel_radius_m": .000035, "ior": 1.48}
TOP_FINISH = {"feature_scale_m": .0006, "roughness_delta_scale": .16,
              "bump_distance_m": .000045, "bump_strength": .4,
              "grain_scale_per_m": 5000, "grain_distance_m": .000035, "grain_strength": .45}
SHELL_FINISH = {"base_colour": (.78, .735, .64), "grain_scale_per_m": 4500, "bump_distance_m": .000085, "bump_strength": .65,
                "roughness_offset": -.24, "roughness_variation_scale": .14,
                "top_factor": "smoothstep(.55, .94, ABS(TrueNormal.Z))"}
TABLE_FINISH = {"base_colour": (.39, .40, .405), "grain_scale_per_m": 2200,
                "bump_distance_m": .00006, "bump_strength": .2, "roughness_range": (.72, .84)}
REFLECTION_WINDOW = {"position_m": (.020, .33, .16), "target_m": (.018, .037, .0545),
                     "size_m": (.06, .08), "energy_w": .08, "colour": (1, 1, 1)}
DEFAULT_NEAR_ELEVATION = 55.0  # Working photo match; not a measured camera angle.
NEAR_FOCUS = (0, 0, .054)
FSTOP = {"near": 64, "switch": 22, "whole": 8}
SWITCH_PULLBACK = 2.4  # about 1:1 magnification instead of 2.5:1


def parse_sequence(path):
    text = Path(path).read_text(encoding="utf-8-sig")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(value, dict):
        value = value.get("frames", [value])
    if (isinstance(value, list) and len(value) == 10
            and all(isinstance(row, list) and len(row) == 9
                    and all(isinstance(cell, (bool, int, float)) for cell in row)
                    for row in value)):
        value = [{"ts": 0, "frame": value}]
    if not isinstance(value, list) or not value or len(value) > 100000:
        raise ValueError("Expected 1 to 100000 frame records")
    records, previous = [], -math.inf
    for i, item in enumerate(value):
        grid = item["frame"]
        if len(grid) != 10 or any(len(row) != 9 for row in grid):
            raise ValueError(f"Record {i}: expected a 10 x 9 grid")
        if any(not isinstance(x, (int, float, bool)) or not math.isfinite(x)
               for row in grid for x in row):
            raise ValueError(f"Record {i}: non-finite or non-numeric cell")
        ts = item.get("ts", i * 500)
        if not isinstance(ts, (int, float)) or not math.isfinite(ts) or ts < 0 or ts < previous:
            raise ValueError(f"Record {i}: invalid or decreasing millisecond timestamp")
        previous = ts
        records.append({**item, "seq": item.get("seq", i), "ts": ts,
                        "frame": [[int(bool(x)) for x in row] for row in grid]})
    return records


def demo_sequence():
    empty = [[0] * 9 for _ in range(10)]
    patterns = [empty, [[int((r + c) % 2 == 0) for c in range(9)] for r in range(10)],
                [[int(c == 4 or r in (4, 5)) for c in range(9)] for r in range(10)],
                [[1] * 9 for _ in range(10)], empty]
    return [{"seq": i, "ts": i * 1000, "mode": "LOCAL_ZOOM", "frame": grid}
            for i, grid in enumerate(patterns)]


def grid_index(r, c):
    return (r // 2 * 3 + c // 3) * 6 + (r % 2) * 3 + 2 - c % 3


def at_time(keys, time):
    for (ta, a), (tb, b) in zip(keys, keys[1:]):
        if ta <= time < tb:
            return a + (b - a) * (time - ta) / (tb - ta)
    return keys[0][1] if time < keys[0][0] else keys[-1][1]


def dot_curve(events, motion):
    """Exact piecewise-linear browser motion, including interrupted strokes."""
    keys, target = [(0.0, 0.0)], False
    for time, next_target in events:
        next_target = bool(next_target)
        if next_target == target:
            continue
        height = at_time(keys, time)
        keys = [(t, h) for t, h in keys if t < time]
        keys.append((time, height))
        if next_target:
            rise = time + motion["rise_ms"]
            pause = rise + motion["peak_pause_ms"]
            end = pause + motion["settle_ms"]
            keys.extend([(rise, motion["peak_mm"]), (pause, motion["peak_mm"]),
                         (end, motion["hold_mm"])])
        else:
            keys.append((time + motion["retract_ms"], 0.0))
        target = next_target
        keys = list(dict(keys).items())  # same-time commands and zero-length pauses
    return sorted(keys)


def check_motion(motion):
    if not (0 < motion["hold_mm"] < motion["peak_mm"] <= 1):
        raise ValueError("Invalid pin heights")
    if (any(motion[k] <= 0 for k in ("rise_ms", "settle_ms", "retract_ms"))
            or motion["peak_pause_ms"] < 0 or motion["curve"] != "linear"):
        raise ValueError("Unsupported motion profile")
    # Compare to the actual browser function, including reversals mid-stroke.
    source = (ROOT / "controls.js").read_text(encoding="utf-8")
    function = source[source.index("  function updateMotion("):source.index("  function setTarget(")]
    cases = [[(0, 1), (400, 0)], [(0, 1), (14, 0), (29, 1), (90, 0), (91, 1)],
             [(0, 1), (0, 0), (0, 1), (50, 1), (100, 0), (110, 0), (125, 1)]]
    times = sorted(set([float(t) for t in range(0, 601, 7)] +
                       [t + x for case in cases for t, _ in case for x in (0, .01, 16.5, 33.333333, 50, 100, 150)]))
    js = "const motion=" + json.dumps(motion) + "; const clamp=v=>Math.max(0,Math.min(1,v));\n" + function
    js += "\nconst cases=" + json.dumps(cases) + ",times=" + json.dumps(times) + ";\n"
    js += """console.log(JSON.stringify(cases.map(events=>times.map(now=>{
      const state={target:false,height:0,phase:'idle',startHeight:0,started:0};
      for(const [t,target] of events){ if(t>now)break;
        if(state.target===Boolean(target))continue;
        updateMotion(state,t);state.startHeight=state.height;state.target=Boolean(target);
        state.started=t;state.phase=state.target?'rise':state.height>0?'retract':'idle';
      } updateMotion(state,now);return state.height;
    }))));"""
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node is required to verify against browser motion")
    expected = json.loads(subprocess.run([node, "-e", js], check=True, capture_output=True, text=True).stdout)
    maximum = 0
    for case, values in zip(cases, expected):
        curve = dot_curve(case, motion)
        maximum = max(maximum, max(abs(at_time(curve, t) - h) for t, h in zip(times, values)))
    if maximum > 1e-7:
        raise AssertionError(f"Browser motion mismatch: {maximum} mm")
    return {"browser_comparison_samples": len(cases) * len(times), "max_error_mm": maximum}


def mesh_fingerprint(obj):
    digest = hashlib.sha256()
    for vertex in obj.data.vertices:
        digest.update(struct.pack("<3f", *vertex.co))
    for poly in obj.data.polygons:
        digest.update(struct.pack("<I", len(poly.vertices)))
        for index in poly.vertices:
            digest.update(struct.pack("<I", index))
    return digest.hexdigest()


def photo_texture():
    """Extract mould detail; remove holes and broad baked illumination."""
    TEXTURES.mkdir(exist_ok=True)
    photo = ROOT.parent / "inputs/Touchpoint_Reference.jpg"
    raw = cv2.imdecode(np.frombuffer(photo.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    corners = np.float32([[626, 285], [873, 623], [1094, 548], [867, 224]])
    matrix = cv2.getPerspectiveTransform(corners, np.float32([[0, 0], [819, 0], [819, 599], [0, 599]]))
    face = cv2.warpPerspective(raw, matrix, (820, 600))
    grey = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
    # Pins and their rim shadows are not a material texture.
    mask = np.zeros_like(grey)
    for x, y in ((155, 151), (393, 129), (642, 122), (159, 409), (397, 405), (647, 397)):
        cv2.circle(mask, (x, y), 118, 255, -1)
    mask[:30] = mask[-30:] = 255
    mask[:, :30] = mask[:, -30:] = 255
    repaired = cv2.inpaint(grey, mask, 7, cv2.INPAINT_TELEA).astype(np.float32)
    detail = repaired - cv2.GaussianBlur(repaired, (0, 0), 13)
    detail = np.clip(detail / 22.0, -1, 1)
    # Seamless reflection about boundaries, limited photographic microvariation.
    detail = np.concatenate((detail, detail[:, ::-1]), axis=1)
    detail = np.concatenate((detail, detail[::-1]), axis=0)
    detail = cv2.resize(detail, (1024, 1024), interpolation=cv2.INTER_AREA)
    path = TEXTURES / "MouldDetail.png"
    cv2.imwrite(str(path), np.round((detail * .30 + .5) * 65535).astype(np.uint16))
    return {"source": "../inputs/Touchpoint_Reference.jpg", "source_sha256": hashlib.sha256(photo.read_bytes()).hexdigest(),
            "rectification_corners_px": corners.tolist(), "texture": "assets/textures/MouldDetail.png",
            "method": "Perspective correction, pin/rim masking, inpainting, broad-illumination removal; grayscale roughness and microscopic normal detail only"}


def linked_image(path, colour=False):
    """Repository texture linked relative to the .blend; large ambientCG maps are not packed."""
    image = bpy.data.images.get(path.name) or bpy.data.images.load(str(path))
    image.colorspace_settings.name = "sRGB" if colour else "Non-Color"
    image.filepath = "//" + path.relative_to(ROOT).as_posix()
    return image


def builders(mat):
    nt = mat.node_tree

    def node(kind, props=None, **inputs):
        item = nt.nodes.new(kind)
        for key, value in (props or {}).items():  # modes first: they create sockets
            setattr(item, key, value)
        for key, value in inputs.items():
            if isinstance(value, bpy.types.NodeSocket):
                nt.links.new(value, item.inputs[key])
            else:
                item.inputs[key].default_value = value
        return item

    def op(operation, a, b=0.0):
        item = nt.nodes.new("ShaderNodeMath")
        item.operation = operation
        for i, value in enumerate((a, b)):
            if isinstance(value, (float, int)):
                item.inputs[i].default_value = value
            else:
                nt.links.new(value, item.inputs[i])
        return item.outputs[0]

    def tex(image, vector, projection="FLAT"):
        item = node("ShaderNodeTexImage", Vector=vector)
        item.image = image
        item.projection = projection
        item.projection_blend = .15
        item.interpolation = "Cubic"
        return item.outputs["Color"]

    def dust(vector, cell_m, share):
        # Sparse specks of varied size; most Voronoi cells stay clean.
        cells = node("ShaderNodeTexVoronoi", Vector=vector, Scale=1 / cell_m)
        size = op("MULTIPLY", op("POWER", cells.outputs["Color"], 3), .22)
        speck = op("LESS_THAN", cells.outputs["Distance"], size)
        return op("MULTIPLY", speck, op("LESS_THAN", node("ShaderNodeSeparateColor", Color=cells.outputs["Color"]).outputs[1], share))

    return node, op, tex, dust


def reset_material(name, colour, roughness):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    shader = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    output = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    mat.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    shader.inputs["Base Color"].default_value = (*colour, 1)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = 0
    shader.inputs["IOR"].default_value = 1.48
    mat.diffuse_color = (*colour, 1)
    return mat, shader


def rounded_normal(mat, shader, radius, normal=None):
    node = mat.node_tree.nodes.new("ShaderNodeBevel")
    node.label = "Microscopic edge highlight"
    node.samples = 6
    node.inputs["Radius"].default_value = radius
    if normal:
        mat.node_tree.links.new(normal, node.inputs["Normal"])
    mat.node_tree.links.new(node.outputs["Normal"], shader.inputs["Normal"])


def moulded_black(name, projection, mould=None, brightness=3.2, roughness_range=(.42, .66)):
    """Plastic003 colour, roughness and height; each object gets its own patch and tone."""
    plastic = TEXTURES / "Plastic003"
    mat, p = reset_material(name, (.02, .021, .023), .5)
    node, op, tex, dust = builders(mat)
    rnd = node("ShaderNodeObjectInfo").outputs["Random"]
    coord = node("ShaderNodeTexCoord")
    location = node("ShaderNodeCombineXYZ", X=op("MULTIPLY", rnd, 7.3), Y=op("MULTIPLY", rnd, 3.1))
    rotation = node("ShaderNodeCombineXYZ", Z=op("MULTIPLY", rnd, 6.283))
    vector = node("ShaderNodeMapping", Vector=coord.outputs["Object"], Location=location.outputs[0],
                  Rotation=rotation.outputs[0], Scale=(1 / .03,) * 3).outputs[0]
    colour = tex(linked_image(plastic / "Plastic003_2K-PNG_Color.png", True), vector, projection)
    gain = op("ADD", op("MULTIPLY", rnd, 1.6), brightness)
    height = tex(linked_image(plastic / "Plastic003_2K-PNG_Displacement.png"), vector, projection)
    if mould:
        # Photographic mould mottling from the reference image.
        detail = tex(mould, vector, projection)
        gain = op("MULTIPLY", gain, op("ADD", op("MULTIPLY", detail, .6), .7))
        height = op("ADD", height, op("MULTIPLY", detail, .5))
    # Half the photographed contrast; full contrast reads as marble under grazing light.
    calm = node("ShaderNodeMixRGB", Fac=.35, Color1=colour, Color2=(.0067, .0067, .0067, 1))
    neutral = node("ShaderNodeHueSaturation", Color=calm.outputs["Color"], Saturation=.3)
    shade = node("ShaderNodeVectorMath", {"operation": "SCALE"}, Vector=neutral.outputs["Color"], Scale=gain)
    specks = dust(node("ShaderNodeNewGeometry").outputs["Position"], .0012, .3)  # world: modules differ
    dusty = node("ShaderNodeMixRGB", Fac=specks, Color1=shade.outputs["Vector"], Color2=(.35, .34, .32, 1))
    mat.node_tree.links.new(dusty.outputs["Color"], p.inputs["Base Color"])
    rough = node("ShaderNodeMapRange", Value=tex(linked_image(plastic / "Plastic003_2K-PNG_Roughness.png"), vector, projection),
                 **{"From Min": 0, "From Max": .7, "To Min": op("ADD", op("MULTIPLY", rnd, .08), roughness_range[0]),
                    "To Max": roughness_range[1]})
    rough_value = rough.outputs["Result"]
    if name == "Photographic black tactile face with broken gloss":
        # Small gloss variations become visible inside reflected light, without painting grey spots.
        gloss = node("ShaderNodeTexNoise", {"noise_dimensions": "4D"},
                     Vector=node("ShaderNodeNewGeometry").outputs["Position"],
                     W=op("MULTIPLY", rnd, 100), Scale=1 / TOP_FINISH["feature_scale_m"], Detail=2, Roughness=.5)
        rough_value = op("ADD", rough_value,
                         op("MULTIPLY", op("SUBTRACT", gloss.outputs["Fac"], .5), TOP_FINISH["roughness_delta_scale"]))
    mat.node_tree.links.new(op("MAXIMUM", rough_value, op("MULTIPLY", specks, .95)), p.inputs["Roughness"])
    tactile = name == "Photographic black tactile face with broken gloss"
    bump = node("ShaderNodeBump", Height=height,
                Strength=TOP_FINISH["bump_strength"] if tactile else .3,
                Distance=TOP_FINISH["bump_distance_m"] if tactile else .00001)
    finish_normal = bump.outputs["Normal"]
    if tactile:
        grain = node("ShaderNodeTexNoise", {"noise_dimensions": "4D"},
                     Vector=node("ShaderNodeNewGeometry").outputs["Position"], W=op("MULTIPLY", rnd, 100),
                     Scale=TOP_FINISH["grain_scale_per_m"], Detail=2, Roughness=.5)
        micro = node("ShaderNodeBump", Height=grain.outputs["Fac"], Normal=finish_normal,
                     Strength=TOP_FINISH["grain_strength"], Distance=TOP_FINISH["grain_distance_m"])
        finish_normal = micro.outputs["Normal"]
    rounded_normal(mat, p, .000035, finish_normal)
    p.inputs["Specular IOR Level"].default_value = .5
    return mat, p


def module_materials():
    names = ["Photographic black moulded broad face", "Photographic black moulded narrow face",
             "Photographic black tactile face with broken gloss", "Clean black moulded housing"]
    for name in names:
        top = "tactile face" in name
        moulded_black(name, "FLAT" if top else "BOX", roughness_range=(.20, .34) if top else (.42, .66))
    # One dielectric surface and participating volume for both crown and shaft.
    mat, p = reset_material("Photographic neutral grey-white complete pins", PIN["base_colours"][0][:3], .27)
    node = builders(mat)[0]
    p.inputs["Subsurface Weight"].default_value = PIN["subsurface_weight"]
    p.inputs["Transmission Weight"].default_value = PIN["transmission_weight"]
    p.inputs["IOR"].default_value = PIN["ior"]
    p.inputs["Specular IOR Level"].default_value = .5
    rnd = node("ShaderNodeObjectInfo").outputs["Random"]
    tint = node("ShaderNodeMixRGB", Fac=rnd, Color1=PIN["base_colours"][0], Color2=PIN["base_colours"][1])
    mat.node_tree.links.new(tint.outputs["Color"], p.inputs["Base Color"])
    rough = node("ShaderNodeMapRange", Value=rnd, **{"To Min": PIN["roughness_range"][0], "To Max": PIN["roughness_range"][1]})
    mat.node_tree.links.new(rough.outputs["Result"], p.inputs["Roughness"])
    rounded_normal(mat, p, PIN["bevel_radius_m"])
    scatter = node("ShaderNodeVolumeScatter", Color=(1, 1, 1, 1), Density=PIN["scatter_density_per_m"],
                   Anisotropy=PIN["scatter_anisotropy"])
    absorption = node("ShaderNodeVolumeAbsorption", Color=PIN["absorption_colour"], Density=PIN["absorption_density_per_m"])
    volume = node("ShaderNodeAddShader")
    mat.node_tree.links.new(scatter.outputs[0], volume.inputs[0])
    mat.node_tree.links.new(absorption.outputs[0], volume.inputs[1])
    output = next(n for n in mat.node_tree.nodes if n.type == "OUTPUT_MATERIAL")
    mat.node_tree.links.new(volume.outputs[0], output.inputs["Volume"])
    if hasattr(mat.cycles, "homogeneous_volume"):
        mat.cycles.homogeneous_volume = True
    for obj in bpy.data.objects:
        if "_Dot_" in obj.name:
            obj.visible_shadow = True
    moulded_black("Web switch plastic", "BOX", brightness=2.2)
    actuator = bpy.data.objects["Switch_Bullet_actuator_20mm"]
    actuator.data.materials[0] = switch_actuator_material()
    return {"top": {"texture_asset": "Plastic003", "source": "https://ambientcg.com/a/Plastic003",
                    "maps": ["Color", "Roughness", "Displacement"], "texture_period_m": .03,
                    "projection": "FLAT", "roughness_base_range": [.20, .34],
                    "roughness_minimum_per_object_offset": [0, .08], "photo_texture_enabled": False,
                    "gloss_mottling": TOP_FINISH},
            "pins": PIN, "switch_actuator": SWITCH_ACTUATOR}


def switch_actuator_material():
    """Fine opaque moulded plastic for the exposed actuator; other switch parts retain their finish."""
    mat, p = reset_material("Moulded black switch actuator", SWITCH_ACTUATOR["base_colour"], .31)
    node, op, _, _ = builders(mat)
    coord = node("ShaderNodeTexCoord").outputs["Object"]
    grain = node("ShaderNodeTexNoise", Vector=coord, Scale=SWITCH_ACTUATOR["grain_scale_per_m"], Detail=2, Roughness=.5)
    rough = node("ShaderNodeMapRange", Value=grain.outputs["Fac"],
                 **{"To Min": SWITCH_ACTUATOR["roughness_range"][0], "To Max": SWITCH_ACTUATOR["roughness_range"][1]})
    mat.node_tree.links.new(rough.outputs["Result"], p.inputs["Roughness"])
    bump = node("ShaderNodeBump", Height=grain.outputs["Fac"], Strength=SWITCH_ACTUATOR["bump_strength"],
                Distance=SWITCH_ACTUATOR["bump_distance_m"])
    rounded_normal(mat, p, SWITCH_ACTUATOR["bevel_radius_m"], bump.outputs["Normal"])
    p.inputs["IOR"].default_value = SWITCH_ACTUATOR["ior"]
    p.inputs["Specular IOR Level"].default_value = .5
    return mat


PRINT = {"side_layer_mm": .20, "top_road_mm": .42, "side_relief_mm": .012, "top_relief_mm": .003,
         "layer_jitter_mm": .004, "road_jitter_mm": .001, "path_wobble_mm": .003, "tone_band_mm": 2.5,
         "top_undulation_mm": .008}


def pla_material():
    mat, p = reset_material("Web enclosure ivory PLA", SHELL_FINISH["base_colour"], .5)
    node, op, tex, _ = builders(mat)
    obj = node("ShaderNodeTexCoord").outputs["Object"]
    split = node("ShaderNodeSeparateXYZ", Vector=obj)
    normal = node("ShaderNodeSeparateXYZ", Vector=node("ShaderNodeNewGeometry").outputs["True Normal"])
    mm = lambda key: PRINT[key] * MM

    def per(index, seed):
        noise = node("ShaderNodeTexWhiteNoise", {"noise_dimensions": "1D"}, W=op("ADD", index, seed))
        return op("SUBTRACT", noise.outputs["Value"], .5)

    def bead(coordinate, pitch):
        # Rounded extrusion profile: crest mid-road, sharp seam between roads.
        scaled = op("DIVIDE", coordinate, pitch)
        crest = op("POWER", op("SINE", op("MULTIPLY", op("FRACT", scaled), math.pi)), .5)
        return crest, op("FLOOR", scaled)

    wobble = node("ShaderNodeTexNoise", Vector=obj, Scale=250, Detail=3)
    side, layer = bead(split.outputs["Z"], mm("side_layer_mm"))
    side_h = op("ADD", op("MULTIPLY", side, mm("side_relief_mm")),
                op("ADD", op("MULTIPLY", per(layer, 0), mm("layer_jitter_mm")),
                   op("MULTIPLY", op("SUBTRACT", wobble.outputs["Fac"], .5), mm("path_wobble_mm"))))
    diagonal = op("MULTIPLY", op("SUBTRACT", split.outputs["X"], split.outputs["Y"]), .7071068)
    top, road = bead(diagonal, mm("top_road_mm"))
    # Uneven top skin: broad pillowing changes the sheen across a flat face.
    pillow = node("ShaderNodeTexNoise", Vector=obj, Scale=200, Detail=2)
    top_h = op("ADD", op("MULTIPLY", op("MULTIPLY", top, op("ADD", wobble.outputs["Fac"], .5)), mm("top_relief_mm")),
               op("ADD", op("MULTIPLY", per(road, 17), mm("road_jitter_mm")),
                  op("MULTIPLY", pillow.outputs["Fac"], mm("top_undulation_mm"))))
    top_factor = node("ShaderNodeMapRange", {"interpolation_type": "SMOOTHSTEP"}, Value=op("ABSOLUTE", normal.outputs["Z"]),
                      **{"From Min": .55, "From Max": .94})
    height = node("ShaderNodeMixRGB", Fac=top_factor.outputs["Result"], Color1=side_h, Color2=top_h)
    bump = node("ShaderNodeBump", Height=height.outputs["Color"], Strength=1, Distance=1)
    grain = node("ShaderNodeTexNoise", Vector=node("ShaderNodeNewGeometry").outputs["Position"],
                 Scale=SHELL_FINISH["grain_scale_per_m"], Detail=2, Roughness=.5)
    grain.label = "Fine isotropic shell finish in world metres"
    grain_bump = node("ShaderNodeBump", Height=grain.outputs["Fac"],
                      Strength=op("MULTIPLY", top_factor.outputs["Result"], SHELL_FINISH["bump_strength"]),
                      Distance=SHELL_FINISH["bump_distance_m"])
    grain_bump.label = "Grain on top only; retains original path/layer normals"
    mat.node_tree.links.new(bump.outputs["Normal"], grain_bump.inputs["Normal"])
    rounded_normal(mat, p, .00012, grain_bump.outputs["Normal"])
    # Filament and flow variation: slow tone bands plus per-layer flicker.
    band = node("ShaderNodeTexNoise", {"noise_dimensions": "1D"}, W=op("DIVIDE", split.outputs["Z"], mm("tone_band_mm")),
                Scale=1, Detail=1)
    tone = op("ADD", 1, op("ADD", op("MULTIPLY", op("SUBTRACT", band.outputs["Fac"], .5), .14),
                           op("MULTIPLY", per(layer, 31), .05)))
    shade = node("ShaderNodeVectorMath", {"operation": "SCALE"}, Vector=SHELL_FINISH["base_colour"], Scale=tone)
    mat.node_tree.links.new(shade.outputs["Vector"], p.inputs["Base Color"])
    rough = op("ADD", .47, op("ADD", op("MULTIPLY", op("SUBTRACT", 1, side), .06),
                              op("MULTIPLY", op("SUBTRACT", band.outputs["Fac"], .5), .08)))
    variation = op("MULTIPLY", op("SUBTRACT", grain.outputs["Fac"], .5), SHELL_FINISH["roughness_variation_scale"])
    offset = op("MULTIPLY", op("ADD", SHELL_FINISH["roughness_offset"], variation), top_factor.outputs["Result"])
    mat.node_tree.links.new(op("ADD", rough, offset), p.inputs["Roughness"])
    p.inputs["Subsurface Weight"].default_value = .12
    p.inputs["Subsurface Scale"].default_value = .0006
    p.inputs["Subsurface Radius"].default_value = (.9, .7, .45)
    p.inputs["Specular IOR Level"].default_value = .5
    for key, value in PRINT.items():
        mat[key] = value


def small_bevels():
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        radius = .00006 if obj.name.endswith("_Housing") else .00018 if obj.name.startswith("Enclosure_") else None
        if radius:
            mod = obj.modifiers.get("Production small round") or obj.modifiers.new("Production small round", "BEVEL")
            mod.width = radius
            mod.segments = 3
            mod.limit_method = "ANGLE"
            mod.angle_limit = math.radians(35)
            mod.use_clamp_overlap = True
            mod.harden_normals = True
        obj.visible_shadow = True


def environment(scene):
    world = scene.world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (LIGHT["ambient"],) * 3 + (1,)
    bg.inputs["Strength"].default_value = 1
    output = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs[0], output.inputs[0])
    # Keep the accepted balanced key; the separate low-power window supplies reflected structure.
    key = bpy.data.objects["Directional window"]
    azimuth, elevation = math.radians(LIGHT["azimuth_deg"]), math.radians(LIGHT["elevation_deg"])
    centre = Vector((0, -.0025, .0545))
    key.location = centre + LIGHT["distance_m"] * Vector((math.cos(elevation) * math.cos(azimuth),
                                                          math.cos(elevation) * math.sin(azimuth), math.sin(elevation)))
    key.rotation_euler = (centre - key.location).to_track_quat("-Z", "Y").to_euler()
    key.hide_render = False
    key.data.type = "AREA"
    key.data.shape = "RECTANGLE"
    key.data.energy = LIGHT["energy_w"]
    key.data.size, key.data.size_y = LIGHT["size_m"]
    key.data.color = (1, 1, 1)
    bpy.data.objects["Weak cool room bounce"].hide_render = True
    reflection = bpy.data.objects.get("Soft reflection window")
    if reflection is None:
        reflection = bpy.data.objects.new("Soft reflection window", bpy.data.lights.new("Soft reflection window", "AREA"))
        scene.collection.objects.link(reflection)
    reflection.location = REFLECTION_WINDOW["position_m"]
    reflection.rotation_euler = (Vector(REFLECTION_WINDOW["target_m"]) - reflection.location).to_track_quat("-Z", "Y").to_euler()
    reflection.hide_render = False
    reflection.data.type = "AREA"
    reflection.data.shape = "RECTANGLE"
    reflection.data.size, reflection.data.size_y = REFLECTION_WINDOW["size_m"]
    reflection.data.energy = REFLECTION_WINDOW["energy_w"]
    reflection.data.color = REFLECTION_WINDOW["colour"]
    table = bpy.data.objects["Tabletop"]
    table.scale = (6, 6, 1)
    table.data.materials[0] = table_material()
    return {"world": {"type": "uniform", "colour": [LIGHT["ambient"]] * 3, "strength": 1},
            "key": {**LIGHT, "type": "AREA", "shape": "RECTANGLE", "colour": [1, 1, 1]},
            "reflection_window": {**REFLECTION_WINDOW, "type": "AREA", "shape": "RECTANGLE"}}


def table_material():
    """Neutral matte tabletop; world-space grain without tiled directional streaks."""
    mat, p = reset_material("Neutral grey matte tabletop", TABLE_FINISH["base_colour"], .78)
    node, op, _, _ = builders(mat)
    vector = node("ShaderNodeNewGeometry").outputs["Position"]
    broad = node("ShaderNodeTexNoise", Vector=vector, Scale=80, Detail=2, Roughness=.5)
    middle = node("ShaderNodeTexNoise", Vector=vector, Scale=220, Detail=2, Roughness=.6)
    grain = node("ShaderNodeTexNoise", Vector=vector, Scale=TABLE_FINISH["grain_scale_per_m"], Detail=2, Roughness=.5)
    tone = op("ADD", 1, op("ADD", op("MULTIPLY", op("SUBTRACT", broad.outputs["Fac"], .5), .50),
                           op("ADD", op("MULTIPLY", op("SUBTRACT", middle.outputs["Fac"], .5), .60),
                                     op("MULTIPLY", op("SUBTRACT", grain.outputs["Fac"], .5), .16))))
    shade = node("ShaderNodeVectorMath", {"operation": "SCALE"}, Vector=TABLE_FINISH["base_colour"], Scale=tone)
    mat.node_tree.links.new(shade.outputs["Vector"], p.inputs["Base Color"])
    rough = node("ShaderNodeMapRange", Value=grain.outputs["Fac"],
                 **{"To Min": TABLE_FINISH["roughness_range"][0], "To Max": TABLE_FINISH["roughness_range"][1]})
    mat.node_tree.links.new(rough.outputs["Result"], p.inputs["Roughness"])
    bump = node("ShaderNodeBump", Height=grain.outputs["Fac"],
                Strength=TABLE_FINISH["bump_strength"], Distance=TABLE_FINISH["bump_distance_m"])
    mat.node_tree.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    return mat



def animate(scene, records, motion, fps, tail):
    scene.render.fps = fps
    scene.render.fps_base = 1
    first_ts = records[0]["ts"]
    curves = {}
    for r in range(10):
        for c in range(9):
            index = grid_index(r, c)
            name = f"M{index // 6 + 1:02d}_Dot_{index % 6 + 1}"
            obj = bpy.data.objects[name]
            base = obj.get("production_rest_location")
            if base is None:
                base = list(obj.location)
                obj["production_rest_location"] = base
            obj.animation_data_clear()
            keys = dot_curve([(item["ts"] - first_ts, item["frame"][r][c]) for item in records], motion)
            curves[name] = keys
            axis = obj.parent.matrix_world.inverted().to_3x3() @ Vector((0, 0, 1))
            obj["grid_row"] = r
            obj["grid_column"] = c
            for time, height in keys:
                obj.location = Vector(base) + axis * height * MM
                obj.keyframe_insert(data_path="location", frame=1 + time * fps / 1000, group="Physical dot travel")
            action = obj.animation_data.action
            for curve in action.fcurves:
                curve.extrapolation = "CONSTANT"
                for key in curve.keyframe_points:
                    key.interpolation = "LINEAR"
    end_ms = max(records[-1]["ts"] - first_ts + tail * 1000,
                 max(keys[-1][0] for keys in curves.values()))
    scene.frame_start = 1
    scene.frame_end = math.ceil(end_ms * fps / 1000)
    for marker in list(scene.timeline_markers):
        scene.timeline_markers.remove(marker)
    for item in records:
        scene.timeline_markers.new(f"JSON seq {item['seq']}", frame=round(1 + (item["ts"] - first_ts) * fps / 1000))
    scene["Production_sequence"] = json.dumps(records)
    scene["Production_motion"] = json.dumps(motion)
    scene["Production_tail_seconds"] = tail
    scene.frame_set(1)
    return curves


def camera_pose(scene, shot, near_elevation=None):
    """Fit scene bounds; near elevation follows the paper photos with the button still below."""
    def xyz(v):
        return Vector((v[0], -v[2], v[1])) * MM
    fov = math.radians(36.243)
    aspect = scene.render.resolution_x / scene.render.resolution_y
    if shot == "switch":
        target = xyz((0, 54.5, 19.5))
        position = target + xyz((6, 19, 10)) * SWITCH_PULLBACK
    else:
        if shot == "near":
            low, high, direction, margin = (-17, 52, -18), (17, 56, 23), (.15, 1.2, .80), 1.05
            near_elevation = DEFAULT_NEAR_ELEVATION if near_elevation is None else near_elevation
            # Keep the existing button-at-bottom direction; only raise the viewpoint.
            direction = (.15, math.hypot(.15, .80) * math.tan(math.radians(near_elevation)), .80)
        else:
            bpy.context.view_layer.update()
            # Browser whole-view bounds are the model, without camera/lights/table.
            points = [obj.matrix_world @ Vector(v) for obj in bpy.data.objects
                      if obj.type == "MESH" and obj.name != "Tabletop" for v in obj.bound_box]
            lows = [min(p[i] for p in points) for i in range(3)]
            highs = [max(p[i] for p in points) for i in range(3)]
            low = (lows[0] / MM, lows[2] / MM, -highs[1] / MM)
            high = (highs[0] / MM, highs[2] / MM, -lows[1] / MM)
            direction, margin = (.85, 1.3, .80), 1.12
        corners = [xyz((x, y, z)) for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])]
        target = (xyz(low) + xyz(high)) / 2
        direction = xyz(direction).normalized()
        right = (-direction).cross(Vector((0, 0, 1))).normalized()
        up = right.cross(-direction).normalized()
        horizontal = math.tan(fov / 2)
        vertical = horizontal / aspect
        distance = max((p - target).dot(direction) + max(abs((p - target).dot(right)) / horizontal,
                       abs((p - target).dot(up)) / vertical) for p in corners) * margin
        position = target + direction * distance
    return position, target


def cameras(scene, near_elevation=None):
    old_camera = scene.camera
    for shot in SHOTS:
        name = "Production camera " + shot
        obj = bpy.data.objects.get(name)
        if not obj:
            obj = bpy.data.objects.new(name, bpy.data.cameras.new(name))
            scene.collection.objects.link(obj)
        obj.animation_data_clear()
        obj.location, target = camera_pose(scene, shot, near_elevation)
        if shot == "near":
            target = Vector(NEAR_FOCUS)
        obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()
        obj.data.type = "PERSP"
        obj.data.sensor_fit = "HORIZONTAL"
        obj.data.sensor_width = 36
        obj.data.lens = 36 / (2 * math.tan(math.radians(36.243) / 2))
        obj.data.clip_start = .0001
        obj.data.clip_end = 10
        focus = bpy.data.objects.get("Production focus " + shot)
        if not focus:
            focus = bpy.data.objects.new("Production focus " + shot, None)
            scene.collection.objects.link(focus)
        # Switch focus on the nose apex, 1.2 mm above the faceplate.
        focus.location = target + Vector((0, 0, .0012)) if shot == "switch" else target
        focus.hide_render = True
        obj.data.dof.use_dof = True
        obj.data.dof.focus_object = focus
        obj.data.dof.aperture_fstop = FSTOP[shot]
        obj.data.dof.aperture_blades = 7
    scene.camera = bpy.data.objects["Production camera near"]
    if old_camera and old_camera.name == "Array photographic camera":
        bpy.data.objects.remove(old_camera, do_unlink=True)


def render_settings(scene, width, height, samples):
    scene.render.engine = "CYCLES"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .012
    scene.cycles.use_denoising = True
    scene.cycles.filter_width = .9
    scene.cycles.max_bounces = 16
    scene.cycles.volume_bounces = 8
    scene.cycles.transmission_bounces = 6
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 4
    scene.cycles.transparent_max_bounces = 8
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = .5
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "16"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -.35
    lens_finish(scene)
    pref = bpy.context.preferences.addons["cycles"].preferences
    gpu = []
    for backend in ("CUDA", "OPTIX"):
        try:
            pref.compute_device_type = backend
            pref.get_devices()
            gpu = [d for d in pref.devices if d.type == backend]
        except (TypeError, RuntimeError):
            continue
        if gpu:
            break
    for d in pref.devices:
        d.use = d in gpu
    scene.cycles.device = "GPU" if gpu else "CPU"
    scene.render.use_persistent_data = True


LENS = {"dispersion": 0, "vignette_floor": .90, "vignette_blur_fraction": .3}


def lens_finish(scene):
    """Mild lateral dispersion and optical vignetting; sequences get the same finish."""
    scene.use_nodes = True
    nt = scene.node_tree
    nt.nodes.clear()
    layers = nt.nodes.new("CompositorNodeRLayers")
    lens = nt.nodes.new("CompositorNodeLensdist")
    lens.inputs["Dispersion"].default_value = LENS["dispersion"]
    nt.links.new(layers.outputs["Image"], lens.inputs["Image"])
    ellipse = nt.nodes.new("CompositorNodeEllipseMask")
    ellipse.inputs["Mask"].default_value = 0
    ellipse.inputs["Value"].default_value = 1
    ellipse.inputs["Size"].default_value[0] = ellipse.inputs["Size"].default_value[1] = 1
    blur = nt.nodes.new("CompositorNodeBlur")
    blur.filter_type = "GAUSS"
    size = LENS["vignette_blur_fraction"] * scene.render.resolution_x
    blur.inputs["Size"].default_value[0] = blur.inputs["Size"].default_value[1] = size
    nt.links.new(ellipse.outputs["Mask"], blur.inputs["Image"])
    falloff = nt.nodes.new("CompositorNodeMapRange")
    falloff.inputs["To Min"].default_value = LENS["vignette_floor"]
    nt.links.new(blur.outputs["Image"], falloff.inputs["Value"])
    multiply = nt.nodes.new("CompositorNodeMixRGB")
    multiply.blend_type = "MULTIPLY"
    nt.links.new(lens.outputs["Image"], multiply.inputs[1])
    nt.links.new(falloff.outputs["Value"], multiply.inputs[2])
    composite = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(multiply.outputs["Image"], composite.inputs["Image"])
    scene.render.use_compositing = True


def verify(scene):
    records = json.loads(scene["Production_sequence"])
    motion = json.loads(scene["Production_motion"])
    motion_checks = check_motion(motion)
    original_frame, subframe = scene.frame_current, scene.frame_subframe
    times = sorted(set([0, 16.666667, 33.333333, 100, 125, 150] +
                       [item["ts"] - records[0]["ts"] + dt for item in records
                        for dt in (0, 16.666667, 33.333333, 100, 125, 150, 175)]))
    maximum, count = 0, 0
    for r in range(10):
        for c in range(9):
            index = grid_index(r, c)
            obj = bpy.data.objects[f"M{index // 6 + 1:02d}_Dot_{index % 6 + 1}"]
            keys = dot_curve([(item["ts"] - records[0]["ts"], item["frame"][r][c]) for item in records], motion)
            if not obj.animation_data or not obj.animation_data.action:
                raise AssertionError(f"No animation on {obj.name}")
            curve = next(fc for fc in obj.animation_data.action.fcurves if fc.data_path == "location" and fc.array_index == 2)
            base = obj["production_rest_location"][2]
            for time in times:
                actual = (curve.evaluate(1 + time * scene.render.fps / 1000) - base) / MM
                maximum = max(maximum, abs(actual - at_time(keys, time)))
                count += 1
    if maximum > .00002:
        raise AssertionError(f"Baked keyframe error: {maximum} mm")
    # A geometric grid check prevents mirroring or a module-number permutation.
    bpy.context.view_layer.update()
    for r in range(10):
        row = [bpy.data.objects[f"M{grid_index(r,c)//6+1:02d}_Dot_{grid_index(r,c)%6+1}"] for c in range(9)]
        if any(a.matrix_world.translation.x >= b.matrix_world.translation.x for a, b in zip(row, row[1:])):
            raise AssertionError("Grid is mirrored or module columns are reordered")
    scene.frame_set(original_frame, subframe=subframe)
    return {"independent_animated_dots": 90, "baked_comparison_samples": count, "max_baked_error_mm": maximum,
            "grid_left_to_right_checked": True, **motion_checks}


def prepare(args):
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    scene = bpy.context.scene
    before = {obj.name: mesh_fingerprint(obj) for obj in bpy.data.objects if obj.type == "MESH"}
    appearance_only = getattr(args, "appearance_only", False)
    before_actions = saved_pin_actions() if appearance_only else None
    if appearance_only:
        records = json.loads(scene["Production_sequence"])
        motion = json.loads(scene["Production_motion"])
        sequence_source = scene.get("Production_sequence_source", "Saved reference animation")
        args.fps = scene.render.fps
    elif args.sequence:
        records = parse_sequence(args.sequence)
        sequence_source = str(Path(args.sequence).resolve())
    elif (ASSETS / "sequence.json").exists():
        records = parse_sequence(ASSETS / "sequence.json")
        sequence_source = "assets/sequence.json"
    else:
        records = demo_sequence()
        sequence_source = "Browser built-in demo (appearance approval only)"
    if not appearance_only:
        (ASSETS / "sequence.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        motion = json.loads((ASSETS / "motion.json").read_text(encoding="utf-8"))
    check_motion(motion)
    materials = module_materials()
    pla_material()
    if not appearance_only:
        small_bevels()
    env = environment(scene)
    if not appearance_only:
        animate(scene, records, motion, args.fps, args.tail)
    render_settings(scene, args.width, args.height, args.samples)
    cameras(scene, args.near_elevation)
    checks = verify(scene)
    after = {obj.name: mesh_fingerprint(obj) for obj in bpy.data.objects if obj.type == "MESH"}
    if before != after:
        raise AssertionError("Original mesh vertices or topology changed")
    if appearance_only and before_actions != saved_pin_actions():
        raise AssertionError("Saved pin curves or rest positions changed")
    # Retain source geometry and assembly placements; only dot travel is animated.
    scene["Production_sequence_source"] = sequence_source
    scene["Production_pipeline"] = "Cycles PNG sequence -> compositor grain -> Blender FFmpeg H.264 video"
    scene["Production_approval"] = "Gray-table working target; balanced pin material retained; appearance and video review recorded separately"
    scene["Production_reference"] = json.dumps(materials)
    scene["Production_mesh_fingerprints"] = json.dumps(after)
    scene.frame_set(1 + round(1.5 * args.fps))
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND), check_existing=False)
    web_path = ASSETS / "scene.json"
    web = json.loads(web_path.read_text(encoding="utf-8"))
    if "source_sha256" in web:
        web["model_export_source_sha256"] = web.pop("source_sha256")
    web.pop("blender_source_unchanged", None)
    web["production_scene"] = "EnclosedArray.blend"
    web["production_scene_sha256"] = hashlib.sha256(BLEND.read_bytes()).hexdigest()
    web["browser_role"] = "Sequence editing and interactive preview; final pictures and video use Cycles"
    web_path.write_text(json.dumps(web, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"engine": "CYCLES", "device": scene.cycles.device, "mesh_count": len(after),
              "gpu_backend": bpy.context.preferences.addons["cycles"].preferences.compute_device_type,
              "original_mesh_geometry_preserved": True, "materials": materials, "environment": env,
              "appearance_only": appearance_only, "saved_pin_actions_preserved": appearance_only,
              "sequence_source": sequence_source, "input_records": len(records), "fps": args.fps,
              "frame_start": scene.frame_start, "frame_end": scene.frame_end,
              "motion": motion, "animation": checks, "preview_frame": scene.frame_current,
              "cameras": {shot: {"position_m": list(bpy.data.objects['Production camera '+shot].location),
                                  "fstop": bpy.data.objects['Production camera '+shot].data.dof.aperture_fstop,
                                  "focus_m": list(bpy.data.objects['Production focus '+shot].location),
                                  "source": "viewer3d.js bounds fit + balanced focus" if shot == "near"
                                            else "viewer3d.js setView + frameBounds"} for shot in SHOTS},
              "near_elevation_deg": DEFAULT_NEAR_ELEVATION if args.near_elevation is None else args.near_elevation,
              "switch_pullback": SWITCH_PULLBACK, "lens_finish": LENS, "print_texture": PRINT,
              "shell_surface_finish": SHELL_FINISH, "table_surface_finish": TABLE_FINISH,
              "motion_blur_shutter_frames": .5, "full_sequence_rendered": False,
              "approval": "Gray-table working target; actual output reviewed separately"}
    (ROOT / "CyclesVerification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Prepared existing EnclosedArray.blend; 90 independent animations verified.", flush=True)


def saved_pin_actions():
    """Exact guard for appearance-only preparation; animation is never regenerated."""
    result = {}
    for obj in bpy.data.objects:
        if "_Dot_" not in obj.name:
            continue
        action = obj.animation_data.action
        result[obj.name] = {"rest": list(obj["production_rest_location"]),
                            "action": action.name,
                            "curves": [(fc.data_path, fc.array_index, fc.extrapolation,
                                        [(list(k.co), k.interpolation, list(k.handle_left), list(k.handle_right),
                                          k.handle_left_type, k.handle_right_type) for k in fc.keyframe_points])
                                       for fc in action.fcurves]}
    return result


def load(args):
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    scene = bpy.context.scene
    if "Production_sequence" not in scene:
        raise RuntimeError("Run prepare or stills before rendering")
    render_settings(scene, args.width, args.height, args.samples)
    cameras(scene, args.near_elevation)
    return scene


GRAIN_SIGMA = 1.0  # display levels of 255


def grain_still(path):
    pixels = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    rng = np.random.default_rng(31)
    scale = 65535 if pixels.dtype == np.uint16 else 255
    noise = rng.normal(0, GRAIN_SIGMA / 255 * scale, (*pixels.shape[:2], 1))
    pixels = np.clip(pixels.astype(np.float32) + noise, 0, scale).astype(pixels.dtype)
    cv2.imwrite(str(path), pixels)


def stills(args):
    prepare(args)
    scene = bpy.context.scene
    selected = SHOTS if args.shot == "all" else (args.shot,)
    frame = args.frame if args.frame is not None else scene.frame_current
    scene.frame_set(frame)
    out = Path(args.out) if args.out else ROOT
    out.mkdir(parents=True, exist_ok=True)
    names = {"near": "PinCloseup.png", "switch": "SwitchPreview.png", "whole": "EnclosureOverview.png"}
    for shot in selected:
        scene.camera = bpy.data.objects["Production camera " + shot]
        path = out / names[shot]
        scene.render.filepath = str(path)
        print(f"Still {shot}, frame {frame}, {args.width} x {args.height}, {args.samples} samples", flush=True)
        bpy.ops.render.render(write_still=True)
        grain_still(path)
    report_path = ROOT / "CyclesVerification.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["stills"] = {"width": args.width, "height": args.height, "samples": args.samples,
                        "frame": frame, "grain_sigma_display_levels": GRAIN_SIGMA,
                        "files": [str(out / names[shot]) for shot in selected]}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Still review ready. No video sequence rendered.", flush=True)


def render_sequence(args):
    scene = load(args)
    # An explicit command is the only entry point to expensive whole-shot rendering.
    for shot in SHOTS if args.shot == "all" else (args.shot,):
        destination = ROOT / "frames" / shot
        destination.mkdir(parents=True, exist_ok=True)
        scene.camera = bpy.data.objects["Production camera " + shot]
        scene.render.filepath = str(destination / "frame_")
        print(f"Rendering {shot}: {scene.frame_start}..{scene.frame_end}", flush=True)
        bpy.ops.render.render(animation=True)


def compose(args):
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    scene = bpy.context.scene
    for shot in SHOTS if args.shot == "all" else (args.shot,):
        destination = ROOT / "frames" / shot
        missing = [frame for frame in range(scene.frame_start, scene.frame_end + 1)
                   if not (destination / f"frame_{frame:04d}.png").exists()]
        if missing:
            raise RuntimeError(f"{shot}: {len(missing)} PNGs missing; video not composed")
        if args.ffmpeg:
            subprocess.run([args.ffmpeg, "-hide_banner", "-loglevel", "warning", "-y", "-framerate", str(scene.render.fps),
                            "-start_number", str(scene.frame_start), "-i", str(destination / "frame_%04d.png"),
                            "-vf", "format=yuv420p,noise=c0s=2:c0f=t+u:c1s=0:c2s=0:all_seed=31",
                            "-c:v", "libx264", "-crf", "17", "-preset", "slow", "-movflags", "+faststart",
                            str(ROOT / f"Array_{shot}.mp4")], check=True)
        else:
            compose_builtin([destination / f"frame_{frame:04d}.png"
                             for frame in range(scene.frame_start, scene.frame_end + 1)],
                            ROOT / f"Array_{shot}.mp4", scene.render.fps)


def compose_builtin(paths, output, fps):
    """Image-sequence compositor and bundled FFmpeg; original PNGs are retained."""
    if not bpy.app.build_options.codec_ffmpeg:
        raise RuntimeError("This Blender build has no FFmpeg encoder")
    first = cv2.imread(str(paths[0]), cv2.IMREAD_UNCHANGED)
    height, width = first.shape[:2]
    scene = bpy.data.scenes.new("PNG sequence composition")
    image = bpy.data.images.load(str(paths[0]), check_existing=False)
    image.source = "SEQUENCE"
    grain = bpy.data.textures.new("Fine monochrome film grain", "CLOUDS")
    grain.noise_scale = .001
    grain.noise_depth = 0
    camera = bpy.data.objects.new("Composition dummy camera", bpy.data.cameras.new("Composition dummy camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.cycles.device = "CPU"
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 2
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.render.fps_base = 1
    scene.frame_start, scene.frame_end = 1, len(paths)
    scene.use_nodes = True
    scene.node_tree.nodes.clear()
    source = scene.node_tree.nodes.new("CompositorNodeImage")
    source.image = image
    source.frame_start = 1
    source.frame_duration = len(paths)
    source.use_auto_refresh = True
    grain_node = scene.node_tree.nodes.new("CompositorNodeTexture")
    grain_node.texture = grain
    grain_node.inputs["Offset"].default_value = (0, 0, 0)
    grain_node.inputs["Offset"].keyframe_insert(data_path="default_value", frame=1)
    grain_node.inputs["Offset"].default_value = (len(paths) * .17, 0, len(paths) * .093)
    grain_node.inputs["Offset"].keyframe_insert(data_path="default_value", frame=max(2, len(paths)))
    subtract = scene.node_tree.nodes.new("CompositorNodeMath")
    subtract.operation = "SUBTRACT"
    subtract.inputs[1].default_value = .5
    scene.node_tree.links.new(grain_node.outputs["Value"], subtract.inputs[0])
    gamma_in = scene.node_tree.nodes.new("CompositorNodeGamma")
    gamma_in.inputs["Gamma"].default_value = 1 / 2.2
    scene.node_tree.links.new(source.outputs["Image"], gamma_in.inputs["Image"])
    mix = scene.node_tree.nodes.new("CompositorNodeMixRGB")
    mix.blend_type = "ADD"
    mix.inputs[0].default_value = .016
    scene.node_tree.links.new(gamma_in.outputs["Image"], mix.inputs[1])
    scene.node_tree.links.new(subtract.outputs[0], mix.inputs[2])
    gamma_out = scene.node_tree.nodes.new("CompositorNodeGamma")
    gamma_out.inputs["Gamma"].default_value = 2.2
    scene.node_tree.links.new(mix.outputs[0], gamma_out.inputs["Image"])
    composite = scene.node_tree.nodes.new("CompositorNodeComposite")
    scene.node_tree.links.new(gamma_out.outputs["Image"], composite.inputs["Image"])
    scene.render.use_compositing = True
    scene.render.use_sequencer = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.ffmpeg.gopsize = fps
    scene.render.filepath = str(output)

    window = bpy.context.window
    previous_scene = window.scene if window else None
    try:
        if window:
            window.scene = scene
        scene.frame_set(1)
        with bpy.context.temp_override(scene=scene):
            bpy.ops.render.render(animation=True, scene=scene.name)
    finally:
        if window:
            window.scene = previous_scene
        bpy.data.scenes.remove(scene)
        bpy.data.objects.remove(camera, do_unlink=True)
        bpy.data.images.remove(image)
        bpy.data.textures.remove(grain)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="stills", choices=("prepare", "stills", "render", "compose", "verify"))
    parser.add_argument("--sequence", help="Browser-exported JSON/JSONL; copied to assets/sequence.json")
    parser.add_argument("--appearance-only", action="store_true",
                        help="Refresh appearance while preserving exact saved pin curves, rest positions and modifiers")
    parser.add_argument("--shot", choices=(*SHOTS, "all"), default="all")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--samples", type=int, default=192)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--tail", type=float, default=1)
    parser.add_argument("--frame", type=int)
    parser.add_argument("--out", help="Directory for review stills (default: alongside this script)")
    parser.add_argument("--near-elevation", type=float, default=DEFAULT_NEAR_ELEVATION,
                        help="Close-up camera elevation in degrees (default: 55, paper-photo working match)")
    parser.add_argument("--ffmpeg")
    args = parser.parse_args()
    if args.appearance_only and (args.sequence or args.command not in ("prepare", "stills")):
        parser.error("--appearance-only is for prepare/stills and cannot import a sequence")
    if min(args.width, args.height, args.samples, args.fps) <= 0 or args.tail < 0:
        parser.error("Render dimensions, samples and fps must be positive; tail must be nonnegative")
    if args.command == "prepare":
        prepare(args)
    elif args.command == "stills":
        stills(args)
    elif args.command == "render":
        render_sequence(args)
    elif args.command == "compose":
        compose(args)
    else:
        scene = load(args)
        print(json.dumps(verify(scene), indent=2))


if __name__ == "__main__":
    main()
