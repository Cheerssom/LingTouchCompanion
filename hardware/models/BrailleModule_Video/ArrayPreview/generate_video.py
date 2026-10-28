"""Render a JSON video job without saving or rebuilding the production scene.

Use the retained structural-runtime Python (it includes bpy and FFmpeg).
The saved animation is the default. Browser sequence exports also work directly.
"""
import argparse
import hashlib
import json
import math
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BLEND = ROOT / "EnclosedArray.blend"
CAMERAS = ("near", "switch", "whole")
JOB_KEYS = {"version", "timeline", "shots", "render", "output_dir"}
RENDER_KEYS = {"width", "height", "fps", "samples", "device", "deduplicate_holds"}


def fail(message):
    raise ValueError(message)


def number(value, label, minimum=0, maximum=None, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        fail(f"{label}: expected a finite {'integer' if integer else 'number'}")
    if value < minimum or (maximum is not None and value > maximum) or (integer and int(value) != value):
        fail(f"{label}: value outside the allowed range")
    return int(value) if integer else float(value)


def reject_unknown(value, allowed, label):
    if not isinstance(value, dict):
        fail(f"{label}: expected an object")
    unknown = set(value) - allowed
    if unknown:
        fail(f"{label}: unknown field(s): {', '.join(sorted(unknown))}")


def pattern(value, label):
    if isinstance(value, str):
        if value == "off":
            return [[0] * 9 for _ in range(10)]
        if value == "on":
            return [[1] * 9 for _ in range(10)]
        if value == "checker":
            return [[int((r + c) % 2 == 0) for c in range(9)] for r in range(10)]
        if value == "cross":
            return [[int(c == 4 or r in (4, 5)) for c in range(9)] for r in range(10)]
        fail(f"{label}: use off, on, checker, cross, or ten rows of nine bits")
    if not isinstance(value, list) or len(value) != 10:
        fail(f"{label}: expected exactly 10 rows")
    grid = []
    for r, row in enumerate(value):
        if not isinstance(row, (list, str)) or len(row) != 9:
            fail(f"{label}, row {r + 1}: expected exactly 9 cells")
        if isinstance(row, str):
            if any(x not in "01" for x in row):
                fail(f"{label}, row {r + 1}: cells must be 0 or 1")
            grid.append([int(x) for x in row])
        else:
            if any(not isinstance(x, (bool, int, float)) or x not in (0, 1) for x in row):
                fail(f"{label}, row {r + 1}: cells must be 0 or 1")
            grid.append([int(x) for x in row])
    return grid


def read_input(path):
    text = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        try:
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        except json.JSONDecodeError:
            fail(f"Invalid JSON: line {error.lineno}, column {error.colno}")


def legacy_records(value, pipeline, path):
    if isinstance(value, dict):
        value = value.get("frames", [value])
    if isinstance(value, list) and len(value) == 10 and all(isinstance(r, list) and len(r) == 9 for r in value):
        value = [{"ts": 0, "frame": value}]
    if not isinstance(value, list) or not value:
        fail("Sequence: expected records, a {frames: [...]} object, or a 10 × 9 matrix")
    for i, record in enumerate(value):
        if not isinstance(record, dict) or "frame" not in record:
            fail(f"Sequence record {i + 1}: missing frame matrix")
        pattern(record["frame"], f"Sequence record {i + 1}")
    try:
        return pipeline.parse_sequence(path)
    except (ValueError, KeyError, TypeError) as error:
        fail(f"Sequence: {error}")


def normalise(value, path, pipeline):
    is_legacy = not isinstance(value, dict) or (not set(value).intersection(JOB_KEYS) and ("frame" in value or "frames" in value))
    records = legacy_records(value, pipeline, path) if is_legacy else None
    job = {} if is_legacy else value
    reject_unknown(job, JOB_KEYS, "Video job")
    if job.get("version", 1) != 1:
        fail("Video job: only version 1 is supported")
    render = job.get("render", {})
    reject_unknown(render, RENDER_KEYS, "render")
    settings = {"width": 1920, "height": 1080, "samples": 128, "device": "auto", "deduplicate_holds": True}
    settings.update(render)
    for key, low, high in (("width", 16, 8192), ("height", 16, 8192), ("samples", 1, 4096)):
        settings[key] = number(settings[key], f"render.{key}", low, high, True)
    if settings["width"] % 2 or settings["height"] % 2:
        fail("render.width and render.height must be even for H.264")
    if "fps" in settings:
        settings["fps"] = number(settings["fps"], "render.fps", 1, 120, True)
    if settings["device"] not in ("auto", "cpu", "gpu"):
        fail("render.device: use auto, cpu, or gpu")
    if not isinstance(settings["deduplicate_holds"], bool):
        fail("render.deduplicate_holds: expected true or false")
    timeline = job.get("timeline", "reference")
    tail = 1.0
    if records is None and timeline != "reference":
        reject_unknown(timeline, {"events", "tail_s"}, "timeline")
        events = timeline.get("events")
        if not isinstance(events, list) or not events or len(events) > 100000:
            fail("timeline.events: expected 1 to 100000 events")
        tail = number(timeline.get("tail_s", 1), "timeline.tail_s", 0, 600)
        records, previous = [], -1.0
        for i, event in enumerate(events):
            reject_unknown(event, {"time_s", "pattern"}, f"timeline.events[{i}]")
            if "time_s" not in event or "pattern" not in event:
                fail(f"timeline.events[{i}]: time_s and pattern are required")
            time = number(event["time_s"], f"timeline.events[{i}].time_s", 0, 86400)
            if time < previous:
                fail(f"timeline.events[{i}].time_s: timestamps must be in ascending order")
            previous = time
            records.append({"seq": i, "ts": time * 1000, "frame": pattern(event["pattern"], f"timeline.events[{i}].pattern")})
        if records[0]["ts"] > 0:
            records.insert(0, {"seq": -1, "ts": 0, "frame": pattern("off", "Initial pattern")})
    shots = job.get("shots", [{"camera": "near"}])
    if not isinstance(shots, list) or not shots or len(shots) > 100:
        fail("shots: expected 1 to 100 shots")
    checked_shots = []
    for i, shot in enumerate(shots):
        reject_unknown(shot, {"camera", "start_s", "end_s", "near_elevation_deg", "fstop"}, f"shots[{i}]")
        if shot.get("camera", "near") not in CAMERAS:
            fail(f"shots[{i}].camera: use near, switch, or whole")
        item = {"camera": shot.get("camera", "near"), "start_s": number(shot.get("start_s", 0), f"shots[{i}].start_s", 0, 86400)}
        for key in ("end_s", "near_elevation_deg", "fstop"):
            if key in shot:
                low, high = ((5, 85) if key == "near_elevation_deg" else (.95, 128) if key == "fstop" else (0, 86400))
                item[key] = number(shot[key], f"shots[{i}].{key}", low, high)
        if "near_elevation_deg" in item and item["camera"] != "near":
            fail(f"shots[{i}].near_elevation_deg is only supported for the near camera")
        checked_shots.append(item)
    output = job.get("output_dir")
    if output is not None and (not isinstance(output, str) or not output.strip()):
        fail("output_dir: expected a nonempty directory path")
    return {"version": 1, "render": settings, "shots": checked_shots,
            "timeline": "reference" if records is None else {"records": records, "tail_s": tail}, "output_dir": output}


def sha_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def texture_inputs(bpy):
    """Fingerprint loaded, referenced external images; ignore packed/generated assets."""
    inputs = {}
    for image in bpy.data.images:
        if image.source != "FILE" or image.users <= int(image.use_fake_user) or image.packed_file or image.packed_files:
            continue
        path = Path(bpy.path.abspath(image.filepath, library=image.library)).resolve()
        if not path.is_file():
            fail(f"Image '{image.name}': external texture is missing: {path}")
        inputs[str(path)] = sha_file(path)
    return [{"path": path, "sha256": inputs[path]} for path in sorted(inputs, key=lambda p: (p.casefold(), p))]


def configure_device(bpy, scene, requested):
    if requested == "cpu":
        scene.cycles.device = "CPU"
        scene.render.threads_mode = "FIXED"
        scene.render.threads = 2
        return
    preferences = bpy.context.preferences.addons["cycles"].preferences
    found = []
    for backend in ("CUDA", "OPTIX", "HIP", "ONEAPI", "METAL"):
        try:
            preferences.compute_device_type = backend
            preferences.get_devices()
            found = [d for d in preferences.devices if d.type == backend]
        except (TypeError, RuntimeError):
            continue
        if found:
            break
    if requested == "gpu" and not found:
        fail("No supported Cycles GPU found; set render.device to cpu or auto")
    for device in preferences.devices:
        device.use = device in found
    scene.cycles.device = "GPU" if found else "CPU"
    scene.render.use_persistent_data = True


def constant_curve(curve, low, high):
    """Endpoints and every internal knot prove constancy for linear/constant curves."""
    if curve.modifiers:
        return False
    keys = list(curve.keyframe_points)
    for a, b in zip(keys, keys[1:]):
        if a.co.x < high and b.co.x > low and a.interpolation not in ("LINEAR", "CONSTANT"):
            return False
    values = [curve.evaluate(low), curve.evaluate(high)]
    values.extend(curve.evaluate(k.co.x) for k in keys if low <= k.co.x <= high)
    if curve.extrapolation != "CONSTANT" and keys and (low < keys[0].co.x or high > keys[-1].co.x):
        return False
    return all(value == values[0] for value in values)


def static_pose(pins, low, high):
    for pin in pins:
        animation = pin.animation_data
        if animation and (animation.drivers or animation.nla_tracks):
            return False
        if animation and animation.action:
            for curve in animation.action.fcurves:
                if not constant_curve(curve, low, high):
                    return False
    return True


def cache_is_safe(bpy, pins):
    pin_names = {p.name for p in pins}
    for obj in bpy.data.objects:
        if obj.name not in pin_names and obj.animation_data:
            return False
        if obj.data and getattr(obj.data, "animation_data", None):
            return False
    for mat in bpy.data.materials:
        if mat.animation_data or (mat.node_tree and mat.node_tree.animation_data):
            return False
    for light in bpy.data.lights:
        if light.node_tree and light.node_tree.animation_data:
            return False
    for group in bpy.data.node_groups:
        if group.users > int(group.use_fake_user) and group.animation_data:
            return False
    if any(image.source in ("MOVIE", "SEQUENCE") for image in bpy.data.images):
        return False
    for scene in bpy.data.scenes:
        if scene.animation_data or (scene.node_tree and scene.node_tree.animation_data):
            return False
        if scene.world and (scene.world.animation_data or (scene.world.node_tree and scene.world.node_tree.animation_data)):
            return False
    return True


def camera_state(camera):
    dof = camera.data.dof
    return {"matrix": [list(row) for row in camera.matrix_world], "lens": camera.data.lens,
            "sensor_width": camera.data.sensor_width, "sensor_fit": camera.data.sensor_fit,
            "shift": [camera.data.shift_x, camera.data.shift_y], "dof": dof.use_dof,
            "fstop": dof.aperture_fstop, "blades": dof.aperture_blades,
            "focus": list(dof.focus_object.matrix_world.translation) if dof.focus_object else dof.focus_distance}


def write_report(path, report):
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def execute(path, out_override=None, validate=False):
    import bpy
    import render_cycles as pipeline
    from mathutils import Vector

    job = normalise(read_input(path), path, pipeline)
    source_hash = sha_file(BLEND)
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    scene = bpy.context.scene
    # Keep links pointed at the repository, even when outputs live elsewhere.
    for image in bpy.data.images:
        if image.filepath.startswith("//"):
            image.filepath = bpy.path.abspath(image.filepath)
    external_textures = texture_inputs(bpy)
    source_fps = scene.render.fps / scene.render.fps_base
    source_start = scene.frame_start
    settings = job["render"]
    settings.setdefault("fps", int(round(source_fps)))
    if job["timeline"] != "reference":
        motion = json.loads(scene.get("Production_motion", (ROOT / "assets/motion.json").read_text(encoding="utf-8")))
        curves = pipeline.animate(scene, job["timeline"]["records"], motion, settings["fps"], job["timeline"]["tail_s"])
        source_fps, source_start = settings["fps"], scene.frame_start
        # Even a zero tail must include the settled endpoint beyond its shutter.
        last_ms = max(keys[-1][0] for keys in curves.values())
        scene.frame_end = max(scene.frame_end, math.ceil(1 + last_ms * source_fps / 1000 + scene.render.motion_blur_shutter))
    duration = (scene.frame_end - scene.frame_start + 1) / source_fps
    for i, shot in enumerate(job["shots"]):
        shot.setdefault("end_s", duration)
        if shot["end_s"] <= shot["start_s"] or shot["end_s"] > duration + 1e-8:
            fail(f"shots[{i}]: require 0 <= start_s < end_s <= timeline duration {duration:.6f} s")
    job_hash = digest_json({"job": {k: v for k, v in job.items() if k != "output_dir"}, "source_blend_sha256": source_hash,
                            "external_texture_inputs": external_textures, "generator_sha256": sha_file(Path(__file__)),
                            "pipeline_sha256": sha_file(ROOT / "render_cycles.py")})
    frame_count = sum(math.ceil((shot["end_s"] - shot["start_s"]) * settings["fps"] - 1e-9) for shot in job["shots"])
    if validate:
        print(json.dumps({"valid": True, "duration_s": duration, "output_frames": frame_count,
                          "saved_animation_used": job["timeline"] == "reference", "job_hash": job_hash}, indent=2), flush=True)
        return
    output_text = out_override or job["output_dir"]
    if output_text:
        output = Path(output_text).expanduser()
        if not output.is_absolute():
            output = path.parent / output
        output = output.resolve()
    else:
        output = Path(tempfile.gettempdir()) / "LingTouchVideo" / (path.stem + "-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    if output == ROOT or output in ROOT.parents:
        fail("Output directory must not be the production scene directory or its parent")
    if output.exists() and not output.is_dir():
        fail(f"Output path is a file; choose a directory: {output}")
    manifest = output / "run.json"
    if output.exists() and any(output.iterdir()):
        if not manifest.is_file():
            fail(f"Output directory already contains files without a matching run.json: {output}")
        old = json.loads(manifest.read_text(encoding="utf-8"))
        if old.get("job_hash") != job_hash:
            fail(f"Output directory belongs to a different job or scene revision: {output}; choose another output_dir")
    else:
        old = {}
    video = output / "video.mp4"
    if video.exists() and (not old.get("video_sha256") or sha_file(video) != old["video_sha256"]):
        fail(f"Existing video is unrecorded or has changed; it was not overwritten: {video}")
    output.mkdir(parents=True, exist_ok=True)
    frames_dir = output / "frames"
    frames_dir.mkdir(exist_ok=True)
    report = {"job_hash": job_hash, "source_blend": str(BLEND), "source_blend_sha256_at_load": source_hash,
              "external_texture_inputs": external_textures,
              "source_scene_saved": False, "saved_animation_used": job["timeline"] == "reference",
              "resolved_job": job, "timeline_duration_s": duration, "output_frames": frame_count,
              "video": str(output / "video.mp4"), "frames": old.get("frames", []), "complete": False}
    if old.get("video_sha256"):
        report["video_sha256"] = old["video_sha256"]
    write_report(manifest, report)
    (output / "resolved_job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    scene.render.resolution_x = settings["width"]
    scene.render.resolution_y = settings["height"]
    scene.render.resolution_percentage = 100
    scene.render.use_border = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "16"
    scene.cycles.samples = settings["samples"]
    configure_device(bpy, scene, settings["device"])
    source_shutter = scene.render.motion_blur_shutter
    scene.render.fps, scene.render.fps_base = settings["fps"], 1
    scene.render.motion_blur_shutter = source_shutter * source_fps / settings["fps"]
    pins = [bpy.data.objects[f"M{m:02d}_Dot_{d}"] for m in range(1, 16) for d in range(1, 7)]
    can_cache = settings["deduplicate_holds"] and cache_is_safe(bpy, pins)
    report["hold_cache_enabled"] = can_cache
    old_frames = {item["number"]: item for item in report["frames"]}
    camera_original = {view: (bpy.data.objects["Production camera " + view].matrix_world.copy(),
                              bpy.data.objects["Production camera " + view].data.dof.aperture_fstop) for view in CAMERAS}
    frame_records = dict(old_frames)
    cache, paths, counter = {}, [], 0
    for shot_index, shot in enumerate(job["shots"]):
        camera = bpy.data.objects["Production camera " + shot["camera"]]
        camera.matrix_world = camera_original[shot["camera"]][0].copy()
        camera.data.dof.aperture_fstop = shot.get("fstop", camera_original[shot["camera"]][1])
        if "near_elevation_deg" in shot:
            camera.location, _ = pipeline.camera_pose(scene, "near", shot["near_elevation_deg"])
            focus = camera.data.dof.focus_object
            target = focus.matrix_world.translation if focus else Vector(pipeline.NEAR_FOCUS)
            camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.camera = camera
        count = math.ceil((shot["end_s"] - shot["start_s"]) * settings["fps"] - 1e-9)
        for offset in range(count):
            counter += 1
            time = shot["start_s"] + offset / settings["fps"]
            source_frame = source_start + time * source_fps
            base_frame = math.floor(source_frame)
            scene.frame_set(base_frame, subframe=source_frame - base_frame)
            bpy.context.view_layer.update()
            shutter = scene.render.motion_blur_shutter if scene.render.use_motion_blur else 0
            position = getattr(scene.render, "motion_blur_position", "CENTER")
            low = source_frame if position == "START" else source_frame - shutter if position == "END" else source_frame - shutter / 2
            high = low + shutter
            held = can_cache and static_pose(pins, low, high)
            cache_key = digest_json({"pose": [list(pin.location) for pin in pins], "camera": camera_state(camera),
                                     "render": settings, "shutter": shutter, "view_transform": scene.view_settings.view_transform,
                                     "look": scene.view_settings.look, "exposure": scene.view_settings.exposure}) if held else None
            target = frames_dir / f"frame_{counter:06d}.png"
            item = {"number": counter, "shot": shot_index + 1, "camera": shot["camera"], "source_time_s": time,
                    "source_frame": source_frame, "static_shutter_window": [low, high] if held else None, "cache_key": cache_key}
            previous = old_frames.get(counter)
            if target.exists():
                if not previous or previous.get("sha256") != sha_file(target):
                    fail(f"Existing frame is unrecorded or has changed; it was not overwritten: {target}")
                item["operation"] = "resumed"
            elif cache_key and cache_key in cache:
                shutil.copy2(cache[cache_key], target)
                item["operation"] = "reused"
            else:
                scene.render.filepath = str(target)
                bpy.ops.render.render(write_still=True)
                item["operation"] = "rendered"
            item["sha256"] = sha_file(target)
            if cache_key:
                cache[cache_key] = target
            paths.append(target)
            frame_records[counter] = item
            report["frames"] = [frame_records[n] for n in sorted(frame_records)]
            write_report(manifest, report)
            print(f"Frame {counter}/{frame_count}: {item['operation']} ({shot['camera']}, {time:.3f}s)", flush=True)
    # OpenCV's path reader fails for some Windows Unicode names; its byte decoder does not.
    old_imread = pipeline.cv2.imread
    with tempfile.NamedTemporaryFile(prefix=".encoding-", suffix=".mp4", dir=output, delete=False) as temporary:
        temporary_video = Path(temporary.name)
    try:
        pipeline.cv2.imread = lambda filename, flags: pipeline.cv2.imdecode(pipeline.np.frombuffer(Path(filename).read_bytes(), pipeline.np.uint8), flags)
        pipeline.compose_builtin(paths, temporary_video, settings["fps"])
        if video.exists() and (not old.get("video_sha256") or sha_file(video) != old["video_sha256"]):
            fail(f"Existing video changed during encoding; it was not overwritten: {video}")
        temporary_video.replace(video)
    finally:
        pipeline.cv2.imread = old_imread
        if temporary_video.exists():
            temporary_video.unlink()
    report.update({"complete": True, "device": scene.cycles.device,
                   "gpu_backend": bpy.context.preferences.addons["cycles"].preferences.compute_device_type,
                   "rendered_frames": sum(f["operation"] == "rendered" for f in report["frames"]),
                   "reused_frames": sum(f["operation"] == "reused" for f in report["frames"]),
                   "resumed_frames": sum(f["operation"] == "resumed" for f in report["frames"]),
                   "video_sha256": sha_file(output / "video.mp4")})
    write_report(manifest, report)
    print(f"VIDEO: {output / 'video.mp4'}", flush=True)
    print(f"REPORT: {manifest}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json", type=Path, help="Video job JSON or browser sequence JSON/JSONL")
    parser.add_argument("--out", help="Isolated output directory; resume only an identical job")
    parser.add_argument("--validate", action="store_true", help="Check inputs and timeline without rendering")
    args = parser.parse_args()
    try:
        execute(args.json.resolve(), args.out, args.validate)
    except (ValueError, KeyError, FileNotFoundError) as error:
        parser.exit(2, f"Video input error: {error}\n")


if __name__ == "__main__":
    main()
