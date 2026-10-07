import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:]
scene_file = argv[0]

# We load the scene configuration from a file during runtime
import importlib.util
spec = importlib.util.spec_from_file_location("scene_description", scene_file)
scene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scene)

noise = scene.get_noise()

print(f"<camera_focal_length:{bpy.context.scene.camera.data.lens}>")
print(f"<camera_sensor_width:{bpy.context.scene.camera.data.sensor_width}>")
print(f"<camera_noise:{noise:.5f}>")
