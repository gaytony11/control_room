import bpy
import os
import math
import addon_utils
from mathutils import Vector

# =====================================================
# PATHS
# =====================================================
INPUT_DIR  = r"C:\Users\44752\Desktop\Control Room\gfx\vehicle_icons\extracted"
OUTPUT_DIR = r"C:\Users\44752\Desktop\Control Room\gfx\vehicle_icons\entity_icons_coloured_TEST"

# =====================================================
# RENDER SETTINGS
# =====================================================
RESOLUTION = 256
SAMPLES = 32

# Camera orbit (consistent angle)
# tweak these if you want: azimuth = left/right, elevation = up/down, distance scale
AZIMUTH_DEG   = 225   # 225 = classic "back-left" 3/4 view. Try 135 for "front-left"
ELEVATION_DEG = 28
DIST_SCALE    = 2.2   # bigger = farther away

# IMPORTANT: if you previously had a good orientation, set this
ROOT_ROTATE_Z_DEG = 0   # try 0 first. If every vehicle faces the wrong way, try 180.

# =====================================================
# COLOUR TARGETS (RGBA)
# =====================================================
COLOURS = {
    "black":  (0.08, 0.08, 0.08, 1.0),
    "blue":   (0.12, 0.32, 0.90, 1.0),
    "red":    (0.90, 0.12, 0.12, 1.0),
    "yellow": (0.95, 0.78, 0.10, 1.0),
    "white":  (0.92, 0.92, 0.92, 1.0),
    "police": (0.18, 0.40, 0.85, 1.0),
}

# Enable LWO importer
addon_utils.enable("io_scene_lwo")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# =====================================================
# UTILS
# =====================================================

def clear_scene():
    # Keep cameras/lights (we recreate anyway)
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

def setup_cycles_gpu():
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'

    prefs = bpy.context.preferences
    cprefs = prefs.addons['cycles'].preferences

    # Prefer OPTIX -> CUDA -> default
    try:
        cprefs.compute_device_type = 'OPTIX'
    except:
        try:
            cprefs.compute_device_type = 'CUDA'
        except:
            pass

    try:
        cprefs.get_devices()
        for d in cprefs.devices:
            if d.type != 'CPU':
                d.use = True
        scene.cycles.device = 'GPU'
    except:
        scene.cycles.device = 'CPU'

def ensure_camera():
    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam

def setup_lights():
    def area(name, energy, loc, size=3.0):
        data = bpy.data.lights.new(name, 'AREA')
        data.energy = energy
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        obj.location = loc
        obj.scale = (size, size, size)
        return obj

    # simple studio-ish setup
    area("Key",  2000, ( 6, -6,  6), 3.0)
    area("Fill",  900, (-6, -3,  4), 3.0)
    area("Rim",  1400, (-4,  6,  5), 3.0)

def render_settings(outpath):
    scene = bpy.context.scene
    scene.render.filepath = outpath
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = True
    scene.render.resolution_x = RESOLUTION
    scene.render.resolution_y = RESOLUTION
    scene.cycles.samples = SAMPLES

def find_lwo_files(root_dir):
    files = []
    for r, _, fs in os.walk(root_dir):
        for f in fs:
            if f.lower().endswith(".lwo"):
                files.append(os.path.join(r, f))
    return files

def mesh_objects():
    return [o for o in bpy.context.scene.objects if o.type == 'MESH']

def world_bbox_size(obj):
    # returns (min, max, diag_len)
    mat = obj.matrix_world
    coords = [mat @ Vector(c) for c in obj.bound_box]
    mn = Vector((min(v.x for v in coords), min(v.y for v in coords), min(v.z for v in coords)))
    mx = Vector((max(v.x for v in coords), max(v.y for v in coords), max(v.z for v in coords)))
    diag = (mx - mn).length
    return mn, mx, diag

def pick_body_mesh(meshes):
    # BODY = largest mesh by world bbox diagonal
    best = None
    best_diag = -1
    for m in meshes:
        _, _, diag = world_bbox_size(m)
        if diag > best_diag:
            best_diag = diag
            best = m
    return best

def make_root(meshes):
    root = bpy.data.objects.new("Root", None)
    bpy.context.collection.objects.link(root)
    for m in meshes:
        m.parent = root
    return root

def center_root_on_ground(root, meshes):

    # IMPORTANT: DO NOT ROTATE OBJECT
    root.rotation_euler = (0, 0, 0)

    bpy.context.view_layer.update()

    mins = Vector(( 1e9,  1e9,  1e9))
    maxs = Vector((-1e9, -1e9, -1e9))

    for m in meshes:
        for c in m.bound_box:
            v = m.matrix_world @ Vector(c)

            mins.x = min(mins.x, v.x)
            mins.y = min(mins.y, v.y)
            mins.z = min(mins.z, v.z)

            maxs.x = max(maxs.x, v.x)
            maxs.y = max(maxs.y, v.y)
            maxs.z = max(maxs.z, v.z)

    center = (mins + maxs) / 2.0

    # ONLY MOVE — DO NOT ROTATE
    root.location -= Vector((center.x, center.y, mins.z))

    bpy.context.view_layer.update()

    size = (maxs - mins).length

    return size


def position_camera_orbit(cam, target_point, size):
    # place camera using spherical-ish orbit coordinates and point it at target
    az = math.radians(AZIMUTH_DEG)
    el = math.radians(ELEVATION_DEG)

    dist = max(0.01, size * DIST_SCALE)

    # spherical to cartesian
    x = dist * math.cos(el) * math.cos(az)
    y = dist * math.cos(el) * math.sin(az)
    z = dist * math.sin(el)

    cam.location = (target_point.x + x, target_point.y + y, target_point.z + z)

    # aim camera at target
    direction = target_point - cam.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()

def ensure_tint_node(mat):
    """
    Adds (or reuses) a 'VehicleTint' multiply node chain:
    - Finds Principled BSDF
    - Inserts MixRGB (MULTIPLY) between current Base Color source and Principled Base Color
    Returns the tint node so we can set its color.
    """
    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links

    principled = None
    for n in nodes:
        if n.type == 'BSDF_PRINCIPLED':
            principled = n
            break
    if not principled:
        return None

    # already exists?
    tint = nodes.get("VehicleTint")
    if tint:
        return tint

    tint = nodes.new("ShaderNodeMixRGB")
    tint.name = "VehicleTint"
    tint.label = "VehicleTint"
    tint.blend_type = 'MULTIPLY'
    tint.inputs[0].default_value = 1.0  # factor

    # Where is base color coming from?
    base_input = principled.inputs.get("Base Color")
    if not base_input:
        return tint

    if base_input.is_linked:
        src_link = base_input.links[0]
        src_node = src_link.from_node
        src_socket = src_link.from_socket
        # remove existing link
        links.remove(src_link)
        # connect src -> tint Color1
        links.new(src_socket, tint.inputs[1])
    else:
        # use the existing base color value as Color1
        tint.inputs[1].default_value = base_input.default_value

    # tint Color2 = chosen colour
    tint.inputs[2].default_value = (1, 1, 1, 1)

    # connect tint -> principled base color
    links.new(tint.outputs[0], base_input)

    return tint

def recolour_body_only(body_obj, rgba):
    """
    Recolour ONLY the materials used by the largest mesh (body),
    leaving wheels/windows/etc alone if they're separate meshes.
    """
    if not body_obj:
        return

    for slot in body_obj.material_slots:
        if not slot.material:
            continue
        tint = ensure_tint_node(slot.material)
        if tint:
            tint.inputs[2].default_value = rgba  # Color2 of multiply

def derive_output_basename(lwo_path):
    # you want vehicle_audi_a6_blue.png etc
    # assume your source LWO name is already in the vehicle_* format
    name = os.path.splitext(os.path.basename(lwo_path))[0].lower().strip()
    name = name.replace(" ", "_")
    if not name.startswith("vehicle_"):
        name = "vehicle_" + name
    return name

# =====================================================
# MAIN
# =====================================================

setup_cycles_gpu()

files = find_lwo_files(INPUT_DIR)
print("Found vehicles:", len(files))

for i, fpath in enumerate(files, 1):
    clear_scene()
    setup_lights()
    cam = ensure_camera()

    base = derive_output_basename(fpath)
    print(f"[{i}/{len(files)}] Processing:", base)

    # import LWO
    bpy.ops.import_scene.lwo(filepath=fpath)
    meshes = mesh_objects()
    if not meshes:
        print("  -> no meshes, skipping")
        continue

    root = make_root(meshes)
    size = center_root_on_ground(root, meshes)

    # pick body by largest mesh
    body = pick_body_mesh(meshes)

    # camera target slightly above ground for nicer framing
    target = Vector((0, 0, size * 0.20))
    position_camera_orbit(cam, target, size)

    for cname, rgba in COLOURS.items():
        recolour_body_only(body, rgba)

        outpath = os.path.join(OUTPUT_DIR, f"{base}_{cname}.png")
        render_settings(outpath)
        bpy.ops.render.render(write_still=True)

print("DONE")
