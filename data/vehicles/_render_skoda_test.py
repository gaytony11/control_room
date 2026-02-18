import bpy
import os
import math
import addon_utils
from mathutils import Vector

# =====================================================
# CONFIG
# =====================================================

INPUT_DIR  = r"C:\Users\44752\Desktop\Control Room\data\vehicles"
OUTPUT_DIR = os.path.join(INPUT_DIR, "png_test")
TEMP_DIR   = os.path.join(INPUT_DIR, "_temp")

HDRI_PATH  = r"C:\Users\44752\Desktop\Control Room\assets\studio_small_08_4k.exr"

FINAL_SIZE = 256
RENDER_SIZE = 512

# Zoom control
FRAME_MARGIN = 1.65
TARGET_MAX_DIM = 3.2

# Crop tuning
ALPHA_THRESHOLD = 0.02
CROP_MARGIN_PX = 40
FINAL_PADDING_PX = 24

# Quality / speed
SAMPLES = 32

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# =====================================================
# GPU ENABLE (CRITICAL FOR SPEED)
# =====================================================

def enable_gpu():

    prefs = bpy.context.preferences
    cycles = prefs.addons['cycles'].preferences

    cycles.compute_device_type = 'OPTIX'

    for device in cycles.devices:
        device.use = True

    bpy.context.scene.cycles.device = 'GPU'

    print("GPU enabled")

# =====================================================
# SCENE SETUP
# =====================================================

def clear_scene():

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def setup_render():

    scene = bpy.context.scene

    scene.render.engine = 'CYCLES'
    scene.cycles.samples = SAMPLES

    scene.render.film_transparent = True

    scene.render.resolution_x = RENDER_SIZE
    scene.render.resolution_y = RENDER_SIZE

    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'

def setup_hdri():

    world = bpy.data.worlds.new("HDRI")
    bpy.context.scene.world = world
    world.use_nodes = True

    nodes = world.node_tree.nodes
    links = world.node_tree.links

    nodes.clear()

    env = nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(HDRI_PATH)

    bg = nodes.new("ShaderNodeBackground")
    out = nodes.new("ShaderNodeOutputWorld")

    links.new(env.outputs[0], bg.inputs[0])
    links.new(bg.outputs[0], out.inputs[0])

def setup_camera():

    bpy.ops.object.camera_add()
    cam = bpy.context.object

    bpy.context.scene.camera = cam

    cam.data.lens = 70

    bpy.ops.object.empty_add(location=(0,0,0))
    target = bpy.context.object

    con = cam.constraints.new(type='TRACK_TO')
    con.target = target
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'

    return cam, target

# =====================================================
# IMPORT
# =====================================================

def import_model(path):

    bpy.ops.import_scene.gltf(filepath=path)

    meshes = [o for o in bpy.context.selected_objects if o.type == 'MESH']

    bpy.ops.object.empty_add()
    root = bpy.context.object

    for m in meshes:
        m.parent = root

    return root, meshes

# =====================================================
# BOUNDS
# =====================================================

def get_bounds(meshes):

    minv = Vector((999,999,999))
    maxv = Vector((-999,-999,-999))

    for obj in meshes:

        for v in obj.bound_box:

            w = obj.matrix_world @ Vector(v)

            minv.x = min(minv.x, w.x)
            minv.y = min(minv.y, w.y)
            minv.z = min(minv.z, w.z)

            maxv.x = max(maxv.x, w.x)
            maxv.y = max(maxv.y, w.y)
            maxv.z = max(maxv.z, w.z)

    return minv, maxv

# =====================================================
# ORIENTATION (GUARANTEED CORRECT)
# =====================================================

def fix_orientation(root, meshes):

    # Force consistent orientation: nose bottom-left
    # GLB vehicles almost always face +Y forward
    # We rotate to make forward point toward (-X,-Y)

    root.rotation_euler = (0, 0, math.radians(225))

    bpy.context.view_layer.update()

# =====================================================
# CENTER / SCALE
# =====================================================

def center_and_scale(root, meshes):

    minv, maxv = get_bounds(meshes)

    center = (minv + maxv) / 2
    size = max(maxv - minv)

    root.location -= Vector((center.x, center.y, minv.z))

    scale = TARGET_MAX_DIM / size
    root.scale = (scale, scale, scale)

# =====================================================
# CAMERA POSITION
# =====================================================

def place_camera(cam, target, meshes):

    minv, maxv = get_bounds(meshes)
    size = max(maxv - minv)

    dist = size * FRAME_MARGIN

    cam.location = (dist, -dist, dist * 0.7)

# =====================================================
# RENDER
# =====================================================

def render_temp(path):

    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

# =====================================================
# ALPHA CROP
# =====================================================

def alpha_crop(src, dst):

    img = bpy.data.images.load(src)

    w, h = img.size
    pixels = list(img.pixels)

    minx, miny = w, h
    maxx, maxy = 0, 0

    for y in range(h):
        for x in range(w):

            a = pixels[4*(y*w+x)+3]

            if a > ALPHA_THRESHOLD:

                minx = min(minx, x)
                miny = min(miny, y)
                maxx = max(maxx, x)
                maxy = max(maxy, y)

    minx -= CROP_MARGIN_PX
    miny -= CROP_MARGIN_PX
    maxx += CROP_MARGIN_PX
    maxy += CROP_MARGIN_PX

    minx = max(minx, 0)
    miny = max(miny, 0)
    maxx = min(maxx, w)
    maxy = min(maxy, h)

    cw = maxx - minx
    ch = maxy - miny

    crop = [0]*(cw*ch*4)

    for y in range(ch):
        for x in range(cw):

            crop[4*(y*cw+x):4*(y*cw+x)+4] = \
            pixels[4*((y+miny)*w+(x+minx)):4*((y+miny)*w+(x+minx))+4]

    canvas = [0]*(FINAL_SIZE*FINAL_SIZE*4)

    scale = min(
        (FINAL_SIZE-2*FINAL_PADDING_PX)/cw,
        (FINAL_SIZE-2*FINAL_PADDING_PX)/ch
    )

    nw = int(cw*scale)
    nh = int(ch*scale)

    ox = (FINAL_SIZE-nw)//2
    oy = (FINAL_SIZE-nh)//2

    for y in range(nh):
        for x in range(nw):

            sx = int(x/scale)
            sy = int(y/scale)

            canvas[4*((y+oy)*FINAL_SIZE+(x+ox)):
                   4*((y+oy)*FINAL_SIZE+(x+ox))+4] = \
                   crop[4*(sy*cw+sx):4*(sy*cw+sx)+4]

    out = bpy.data.images.new("out", FINAL_SIZE, FINAL_SIZE)

    out.pixels = canvas
    out.filepath_raw = dst
    out.file_format = 'PNG'
    out.save()

    bpy.data.images.remove(img)
    bpy.data.images.remove(out)

# =====================================================
# MAIN
# =====================================================

def process(path):

    print("Processing:", path)

    clear_scene()

    setup_render()
    setup_hdri()

    cam, target = setup_camera()

    root, meshes = import_model(path)

    fix_orientation(root, meshes)

    center_and_scale(root, meshes)

    place_camera(cam, target, meshes)

    temp = os.path.join(TEMP_DIR, "temp.png")

    render_temp(temp)

    out = os.path.join(
        OUTPUT_DIR,
        os.path.splitext(os.path.basename(path))[0] + ".png"
    )

    alpha_crop(temp, out)

    print("Saved:", out)

def main():

    enable_gpu()

    files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".glb")]

    print("Found", len(files), "vehicles")

    for f in files:

        process(os.path.join(INPUT_DIR, f))

main()
