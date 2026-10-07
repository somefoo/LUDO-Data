import bpy
import numpy as np
import mathutils
import random
import sys
import os
from mathutils import Vector
from mathutils import Matrix
from pathlib import Path

#### Setup needed as this script is executed in by Blender ####
# Get the needed arguments (defined after --)
argv = sys.argv[sys.argv.index("--") + 1:]
from_index = eval(argv[0])
to_index = eval(argv[1])
create_test_dataset = eval(argv[2])
scene_file = argv[3]
output_path = argv[4]


# We load the scene configuration from a file during runtime
def load_script(path : Path):
    """ Load a script from a file and execute it in the current context """
    import importlib.util
    spec = importlib.util.spec_from_file_location("scene_description", path)
    script_object = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script_object)
    return script_object
# Get the scene description
scene = load_script(scene_file)
# Load functions that are commonly used for occupancy sampling in 3D space
cdrs = load_script(Path(os.path.realpath(__file__)).parent / "common.py")

#### The script starts here ####
output_volume_name_nrrd = "volume.nrrd"
Path(output_path).mkdir(parents=True, exist_ok=True)

class PositionIndexHelper:
    """ Helps to convert between positions in world space and indices in the volume """
    def __init__(self, min_corner : Vector, max_corner : Vector, resolution : tuple[int,int,int]):
        self.min_corner = min_corner
        self.max_corner = max_corner
        self.voxel_size = Vector([x / y for x, y in zip(max_corner - min_corner, resolution)])

    def get_index(self, position : Vector) -> list[int]:
        """ Returns the index of the voxel that contains the given position """
        return [int(x / y) for x, y in zip((position - self.min_corner),self.voxel_size)]

    def get_position(self, index : Vector) -> Vector:
        """ Returns the position (corner) voxel at the given index """
        return Vector(index * self.voxel_size + self.min_corner)

    def get_voxel_size(self) -> Vector:
        """ Returns the size of a voxel (3D)"""
        return self.voxel_size

def get_camera_transformation() -> (Matrix, list[Vector]):
    """ Get scene camera transformation """
    cam_matrix_world = bpy.context.scene.camera.matrix_world
    # We compute the space directions - (x,y,z) of the camera coordinate system
    cam_space_directions = [Vector((1, 0, 0, 0)), Vector((0, 1, 0, 0)), Vector((0, 0, 1, 0))]
    cam_world_directions = [cam_matrix_world.inverted() @ direction for direction in cam_space_directions]
    cam_world_directions = [direction.normalized() for direction in cam_world_directions]
    return cam_matrix_world, cam_world_directions

def create_nrrd(idv : int, resolution : tuple[int,int,int] = (400,400,400)) -> None:
    """ Create NRRD volume for a given index """

    print("WARNING: NRRD generation has not been adjusted to handle objects inside objects!")

    # We also set the blender internal seed
    mathutils.noise.seed_set(idv)

    valid_meshes = cdrs.get_valid_meshes()

    # Compute scene bounding box
    min_corner, max_corner = cdrs.scene_extreme_points(valid_meshes)

    # Turn the scene bounding box into a regular cube """
    min_corner = Vector([min(min_corner[0], min_corner[1], min_corner[2])] * 3)
    max_corner = Vector([max(max_corner[0], max_corner[1], max_corner[2])] * 3)

    # Create empty volume and index helper
    volume = np.zeros(resolution)
    index_helper = PositionIndexHelper(min_corner, max_corner, resolution)

    # NRRD defines the position to be the 0th voxel
    volume_position = index_helper.get_position(Vector((0,0,0)))
    cam_matrix_world, cam_space_directions = get_camera_transformation()
    volume_in_camera_space = cam_matrix_world.inverted() @ volume_position

    # Compute the coordinate origin and direction for the NRRD file
    voxel_size = index_helper.get_voxel_size()
    scaled_cam_space_directions = [direction * voxel_size[i] for i, direction in enumerate(cam_space_directions)]


    # Set values at positions inside any object
    value = 1
    for ob in valid_meshes:
        value += 10
        # Only check within the object bounding box
        object_min, object_max = ob.world_space_bbox
        object_min_index = index_helper.get_index(object_min)
        object_max_index = index_helper.get_index(object_max)

        for z in range(object_min_index[2], object_max_index[2]):
            for y in range(object_min_index[1], object_max_index[1]):
                for x in range(object_min_index[0], object_max_index[0]):
                    # Check if the point is inside the object
                    position = index_helper.get_position(Vector((x,y,z)))
                    # TODO: This causes weird artifacts sometimes (false positives)
                    # but only in scenes with rigging
                    #inside = ob.point_inside_mesh_basic(position)
                    inside = cdrs.point_inside_any_mesh_objects_inside_objects(valid_meshes, position)
                    if inside:
                        volume[z][y][x] = inside * 10 + 1;

    # Write the volume to a NRRD file
    full_volume_path_nrrd = output_path + "/" + str(idv).zfill(5) + "_" + output_volume_name_nrrd
    f = open(full_volume_path_nrrd, "w")
    f.write("NRRD0004\n")
    f.write("type: short\n")
    f.write("dimension: 3\n")
    f.write("space: left-posterior-superior\n")
    f.write(f'sizes: {resolution[0]} {resolution[1]} {resolution[2]}\n')
    # Just an alias
    s = scaled_cam_space_directions
    f.write(f"space directions: ({s[0][0]},{s[0][1]},{s[0][2]}) ({s[1][0]},{s[1][1]},{s[1][2]}) ({s[2][0]},{s[2][1]},{s[2][2]})\n")
    f.write("kinds: domain domain domain\n")
    f.write("endian: little\n")
    f.write("encoding: raw\n")
    f.write(f"space origin: ({volume_in_camera_space[0]}, {volume_in_camera_space[1]}, {volume_in_camera_space[2]})\n")
    # NRRD format defines another empty line (end of header)
    f.write("\n")

    # Note, header type is short (= int16)
    volume.astype('int16').tofile(f)
    f.close()

if __name__ == "__main__":
    # Set seed to make sure we get the same results every time
    if not create_test_dataset:
        # Create training data
        random.seed(from_index)
        np.random.seed(from_index)
    else:
        # Create test data
        random.seed(from_index + 100000)
        np.random.seed(from_index + 100000)

    for i in range(from_index, to_index):
        # Update the view_layer, as some components in Blender
        # are not updated automatically
        bpy.context.view_layer.update()

        # Randomize the scene
        scene.randomize_scene()

        # And again, just to be safe
        bpy.context.view_layer.update()

        # Create the volume
        create_nrrd(i)
