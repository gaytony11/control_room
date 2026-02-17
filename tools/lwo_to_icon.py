import os
import math
import bpy
import addon_utils

# ============================================
# FORCE ENABLE LIGHTWAVE IMPORTER
# ============================================

addon_name = "io_scene_lwo"

if addon_name not in bpy.context.preferences.addons:
    try:
        addon_utils.enable(addon_name)
        print("Enabled addon:", addon_name)
    except Exception as e:
        print("Failed to enable addon:", e)

# ============================================
# PATHS
# ============================================

INPUT_DIR = r"C:\Users\44752\Desktop\Control Room\gfx\vehicle_icons\extracted"
OUTPUT_DIR = r"C:\Users\44752\Desktop\Control Room\gfx\vehicle_icons\entity_icons"

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Scanning for LWO files in:", INPUT_DIR)

# ============================================
# SCENE MANAGEMENT
# ============================================

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    for block in bpy.data.meshes:
        bpy.data.meshes.remove(block)

    for block in bpy.data.materials:
        bpy.data.materials.remove(block)

# ============================================
# RENDER SETTINGS (FAST + GOOD QUALITY)
# ============================================

def setup_render(output_path):

    scene = bpy.context.scene

    scene.render.engine = 'CYCLES'
    scene.render.filepath = output_path
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'

    scene.render.resolution_x = 256
    scene.render.resolution_y = 256

    scene.render.film_transparent = True

    # MASSIVE SPEED IMPROVEMENT
    scene.cycles.samples = 64
    scene.cycles.preview_samples = 32

    scene.cycles.use_denoising = True

# ============================================
# CAMERA SETUP
# ============================================

def setup_camera(target):

    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)

    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    cam.location = (4, -4, 3)
    cam.rotation_euler = (math.radians(60), 0, math.radians(45))

    return cam

# ============================================
# LIGHTING
# ============================================

def setup_light():

    light_data = bpy.data.lights.new(name="Light", type='AREA')
    light_data.energy = 1500

    light = bpy.data.objects.new(name="Light", object_data=light_data)

    bpy.context.collection.objects.link(light)

    light.location = (5, -5, 5)

# ============================================
# FIND ALL LWO FILES
# ============================================

def find_lwo_files(folder):

    lwo_files = []

    for root, dirs, files in os.walk(folder):

        for file in files:

            if file.lower().endswith(".lwo"):

                full_path = os.path.join(root, file)

                lwo_files.append(full_path)

                print("Found:", full_path)

    return lwo_files

# ============================================
# CENTER AND SCALE OBJECT
# ============================================

def center_and_scale(obj):

    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')

    obj.location = (0, 0, 0)

    max_dim = max(obj.dimensions)

    if max_dim > 0:
        scale = 2.0 / max_dim
        obj.scale = (scale, scale, scale)

# ============================================
# MAIN PROCESS
# ============================================

files = find_lwo_files(INPUT_DIR)

print(f"\nTotal LWO files found: {len(files)}\n")

if len(files) == 0:
    print("ERROR: No LWO files found")
    exit()

count = 0
skipped = 0

for filepath in files:

    filename = os.path.basename(filepath)

    output_path = os.path.join(
        OUTPUT_DIR,
        filename.replace(".lwo", ".png")
    )

    print("\nRendering:", filename)

    clear_scene()

    try:

        bpy.ops.import_scene.lwo(filepath=filepath)


    except Exception as e:

        print("SKIPPED:", filename)
        print("Reason:", e)

        skipped += 1
        continue

    objects = bpy.context.selected_objects

    if not objects:
        print("SKIPPED: No objects found")
        skipped += 1
        continue

    obj = objects[0]

    center_and_scale(obj)

    setup_camera(obj)

    setup_light()

    setup_render(output_path)

    bpy.ops.render.render(write_still=True)

    count += 1

# ============================================
# DONE
# ============================================

print("\n===================================")
print("COMPLETE")
print("Rendered:", count)
print("Skipped:", skipped)
print("Output:", OUTPUT_DIR)
print("===================================")
