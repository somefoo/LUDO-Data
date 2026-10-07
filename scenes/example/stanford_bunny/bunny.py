import bpy
import random
import math
from mathutils import Vector

# The amount of noise that is to be added to the camera observation
def get_noise() -> float:
    return 0.1

# Used for data generation:
def randomize_scene():

    # For this application, we simply use a basic bone rig to animate the bunny a bit.
    bpy.data.objects['0rig'].pose.bones["Head"].rotation_euler.x = math.radians(random.uniform(-30, 0))
    bpy.data.objects['0rig'].pose.bones["Head"].rotation_euler.y = math.radians(random.uniform(-25, 25))
    bpy.data.objects['0rig'].pose.bones["Head"].rotation_euler.z = math.radians(random.uniform(-40, 40))

    bpy.data.objects['0rig'].pose.bones["Ear_Left"].rotation_euler.x = math.radians(random.uniform(-50, 5))
    bpy.data.objects['0rig'].pose.bones["Ear_Left"].rotation_euler.y = math.radians(random.uniform(-40, 40))
    bpy.data.objects['0rig'].pose.bones["Ear_Left"].rotation_euler.z = math.radians(random.uniform(-20, 40))

    bpy.data.objects['0rig'].pose.bones["Ear_Right"].rotation_euler.x = math.radians(random.uniform(-50, 5))
    bpy.data.objects['0rig'].pose.bones["Ear_Right"].rotation_euler.y = math.radians(random.uniform(-40, 40))
    bpy.data.objects['0rig'].pose.bones["Ear_Right"].rotation_euler.z = math.radians(random.uniform(-20, 40))



    # We move the camera around the bunny (note, the camera has a "lookat" modifier)
    distance = random.uniform(100, 200)

    hs_trunc = math.pi*2 * (20/360)

    p1 = random.uniform(-math.pi/2 + hs_trunc, math.pi/2 - hs_trunc)
    p2 = random.uniform(-math.pi/2 + hs_trunc, math.pi/2 - hs_trunc)

    z = math.cos(p1) * math.cos(p2) * distance
    x = math.cos(p1) * math.sin(p2) * distance
    y = math.sin(p1)                * distance

    bpy.data.objects['Camera'].location = Vector((x,y,z))

# Some additional scene parameters

# A small gap around the surface of the object in which no samples are drawn
def get_transition_wall() -> float:
    return 0.02

# Additional thickness of the bounding box around the object within which inside/outside samples will be drawn
def get_outside_wall() -> float:
    return 3.0

# Number of samples that will be drawn inside and outside the object (256 => 256 inside + 256 outside samples)
def get_half_occupancy_count() -> int:
    return 256

# Choice of sampling method, usually it's fine to stick with "n1". 
def get_sampling_method() -> str:
    return "n1"
