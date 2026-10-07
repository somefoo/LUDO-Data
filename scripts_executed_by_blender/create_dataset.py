import bpy
import numpy as np
import mathutils
import random
import sys
import os
from mathutils import Vector
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
TEST_DATA_UNIFORM_GRID_RESOLUTION = 100
output_image_name = "image.exr"
output_occupancy_name_csv  = "occupancy.csv"
output_occupancy_name_npz  = "occupancy.npz"
output_occupancy_name_pcd  = "occupancy.pcd"
Path(output_path).mkdir(parents=True, exist_ok=True)

def sample_test_points(valid_meshes : list, axis_resolution : int) -> list:
    """ Sample points on a uniform grid """
    min_point, max_point = cdrs.get_equilateral_scene_bounding_box(valid_meshes, 1.1)

    points = []
    step_size = (max_point[0] - min_point[0])/axis_resolution
    for z in range(0, axis_resolution):
        print(z)
        for y in range(0, axis_resolution):
            for x in range(0, axis_resolution):
                point = Vector((min_point[0] + x*step_size, min_point[1] + y*step_size, min_point[2] + z*step_size))
                inside_state = cdrs.point_inside_any_mesh_objects_inside_objects(valid_meshes, point)
                if inside_state == 0:
                    # Outside all objects
                    if cdrs.point_inside_any_bbox_scaled(valid_meshes, point) != 0:
                        # Inside a bounding box
                        points.append(Vector((point[0],point[1],point[2], inside_state)))
                else:
                    # Inside an object
                    points.append(Vector((point[0],point[1],point[2], inside_state)))
    return points


def create_object_bounding_boxes(idv : int, file_format : str = 'csv') -> None:
    """ Obtains the bounding box of each object and stores it as a file, format: idv xmin ymin zmin xmax ymax zmax """
    bounding_boxes = []
    for ob in cdrs.get_valid_meshes():
        bbox = ob.compute_camera_space_bbox_extreme_points()
        unique_id = ob.unique_id

        p_min = Vector((bbox[0][0],bbox[0][1],bbox[0][2],1.0))
        p_max = Vector((bbox[1][0],bbox[1][1],bbox[1][2],1.0))

        object_name = ob.name

        bounding_boxes.append([object_name, unique_id, p_min.x, p_min.y, p_min.z, p_max.x, p_max.y, p_max.z])



    # Store as .csv
    if file_format == 'csv':
        with open(output_path + "/" + str(idv).zfill(5) + "_bounding_boxes.csv", 'w') as f:
            for bbox in bounding_boxes:
                f.write(f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},{bbox[4]},{bbox[5]},{bbox[6]},{bbox[7]}\n")
    else:
        raise Exception("Unknown file format")

def create_occupancy_test(idv : int, file_format : str = 'npz') -> None:
    """ Sample on a regular grid, used for the test dataset """
    mathutils.noise.seed_set(idv)
    valid_meshes = cdrs.get_valid_meshes()
    points = sample_test_points(valid_meshes, TEST_DATA_UNIFORM_GRID_RESOLUTION)

    # Find the closest surface to each point
    # The output will be a list of vector: x,y,z,class,distance
    points = cdrs.append_sdf_vectors(valid_meshes, points)

    # Transform the points to the camera coordinate system
    camera_matrix = bpy.data.objects['Camera'].matrix_world.inverted()
    for p in points:
        new_position = camera_matrix@Vector((p.x,p.y,p.z,1.0))
        p.x = new_position.x
        p.y = new_position.y
        p.z = new_position.z

    # Create the output paths for each possible file
    full_image_path =         output_path + "/" + str(idv).zfill(5) + "_" + output_image_name
    full_occupancy_path_npz = output_path + "/" + str(idv).zfill(5) + "_" + output_occupancy_name_npz
    full_occupancy_path_csv = output_path + "/" + str(idv).zfill(5) + "_" + output_occupancy_name_csv
    full_occupancy_path_pcd = output_path + "/" + str(idv).zfill(5) + "_" + output_occupancy_name_pcd

    # Render and save image
    bpy.context.scene.render.filepath = full_image_path
    bpy.ops.render.render(write_still = True)

    # Convert vector to np.array
    points = [np.array(p) for p in points]
    points = np.array(points)

    if file_format == 'npz':
        # Store as npz
        np.savez_compressed(full_occupancy_path_npz, occ=points)
    elif file_format == 'csv':
        # Store as csv
        np.savetxt(full_occupancy_path_csv, points, fmt="%f,%f,%f,%d,%f")
    elif file_format == 'pcd':
        # Store as pcd
        with open(full_occupancy_path_pcd, 'w') as f:
            f.write("# .PCD v.7 - Point Cloud Data file format\n")
            f.write("VERSION .7\n")
            f.write("FIELDS x y z label x_d y_d z_d\n")
            f.write("SIZE 4 4 4 4 4 4 4\n")
            f.write("TYPE F F F F F F F\n")
            f.write("COUNT 1 1 1 1 1 1 1\n")
            f.write(f"WIDTH {len(points)}\n")
            f.write("HEIGHT 1\n")
            f.write("VIEWPOINT 0 0 0 1 0 0 0\n")
            f.write(f"POINTS {len(points)}\n")
            f.write("DATA ascii\n")
            for p in points:
                f.write(f"{p[0]} {p[1]} {p[2]} {p[3]} {p[4]} {p[5]} {p[6]}\n")

def create_occupancy(idv : int, file_format : str = 'pcd') -> None:
    """ Create training dataset according to the sampling method defined in the scene description """
    mathutils.noise.seed_set(idv)

    half_occupancy_count = scene.get_half_occupancy_count() # Number of points inside or outside

    transition_wall = scene.get_transition_wall() # The "no sample" thickness at the transition between objects
    sampling_method = scene.get_sampling_method() # The sampling method to use

    # We store the points inside and outside separately.
    # Samples of all objects are stored in these lists.
    inside_points = [] # > 0
    outside_points = [] # = 0

    valid_meshes = cdrs.get_valid_meshes()

    # Enumerate all objects, but inside_value_by_index starts at 1 instead of 0
    # This is because we want to use the index as a label for inside points
    # and 0 is reserved for outside points
    for inside_value_by_index, ob in enumerate(valid_meshes, start=1):
        # List of all meshes except the current one
        valid_other_meshes = list(filter(lambda x: not(x == ob), valid_meshes))
        # Remove objects whose bounding box does not intersect with the current object
        valid_other_meshes = list(filter(lambda x: cdrs.intersecting_bounding_box(x, ob), valid_other_meshes))

        if(cdrs.ignore_obj(ob)): continue

        # Get bounding box, we will sample within the bounding box
        bbox = ob.world_space_bbox_scaled
        x_min, y_min, z_min = bbox[0]
        x_max, y_max, z_max = bbox[1]

        # If this object is degenrate, we will not sample
        if(x_min == x_max or y_min == y_max or z_min == z_max):
            pass

        # Inside/Outside samples of the current object
        object_inside_points = []
        object_outside_points = []

        # Number of total points that will be sampled (n)
        draw_count = half_occupancy_count
        eval_draw_count = half_occupancy_count
        if sampling_method in ["n1", "body_uniform",]:
            draw_count = half_occupancy_count
        elif sampling_method in ["n2","uniform"]:
            draw_count = half_occupancy_count * 2

        # Select breaking condition for how the samples are distributed to each region
        if sampling_method in ["n1", "n2", "body_uniform",]:
            # Break if at both region have the desired number of samples or more
            while_loop_break_condition = lambda i,o: len(i) < draw_count or len(o) < draw_count
        elif sampling_method in ["uniform"]:
            # Break if there are enough samples overall
            while_loop_break_condition = lambda i,o: len(i) + len(o) < draw_count

        sanity_counter = 0

        while while_loop_break_condition(object_inside_points, object_outside_points):
            sanity_counter += 1
            if sanity_counter > 1000000:
                raise Exception("Sanity counter reached limit, something went wrong! Sampling object: " + ob.name)

            # Sample a point randomly in the object bounding box
            xpn =  random.uniform(x_min, x_max)
            ypn =  random.uniform(y_min, y_max)
            zpn =  random.uniform(z_min, z_max)

            # Compute the occupancy and the distance to the object surface
            inside, distance = ob.point_inside_mesh_basic_with_distance(mathutils.Vector((xpn,ypn,zpn)))

            # Discard the point if it is too close to the surface
            if distance < transition_wall:
                continue

            # Need to make sure that the found sample doesn't intersect another object
            for oob in valid_other_meshes:
                # Compute the occupancy and the distance to the other objects surface
                inside_other, distance_other = oob.point_inside_mesh_basic_with_distance(mathutils.Vector((xpn,ypn,zpn)))

                if distance_other < transition_wall:
                    # If the distance is too close, we discard the point
                    break
                if inside_other:
                    if not inside:
                        object_outside_points.append(mathutils.Vector((xpn,ypn,zpn,oob.unique_id,distance)))
                    else:
                        # Problem, points from the larger object are inside the smaller object. Fix:
                        # If the point is inside both, place it in the object with the smaller distance
                        if distance < distance_other:
                            object_inside_points.append(mathutils.Vector((xpn,ypn,zpn,ob.unique_id,distance)))
                        else:
                            object_inside_points.append(mathutils.Vector((xpn,ypn,zpn,oob.unique_id,distance)))
                    # If the point is inside another object, we discard the point
                    break
            else:
                # If no intersection was found, we can add the point to the list
                if inside:
                    object_inside_points.append(mathutils.Vector((xpn,ypn,zpn,ob.unique_id,distance)))
                else:
                    object_outside_points.append(mathutils.Vector((xpn,ypn,zpn,0,distance)))

        # Sort the samples by distance if one of the sortsampling methods are used
        if sampling_method not in ["uniform", "body_uniform"]:
            object_inside_points.sort(key=lambda x: x[4])
            object_outside_points.sort(key=lambda x: x[4])

        # If the object name starts with ZZ, replace all its
        # inside values with outside values. This can be used to
        # assist the learning algorithm to not reconstruct
        # objects which may be missing in some training examples
        # by penalizing a wrongful reconstruction.
        # WARNING: Replacing the name will cause a change in the order
        # of other objects, in  the future don't do this via naming!
        if ob.name[0:2] == 'ZZ':
            for p in object_inside_points:
                p[3] = outside_value


        # Add the samples to the global list
        if sampling_method not in ["uniform"]:
            # (k = half_occupancy_count)
            inside_points += object_inside_points[0:half_occupancy_count]
            outside_points += object_outside_points[0:half_occupancy_count]
        else:
            inside_points += object_inside_points
            outside_points += object_outside_points


    # Add points (very far away) to minimize the change of mirroring artifacts
    # Should be around 15% of all samples
    far_outside_points_count = int(len(valid_meshes) * 2 * half_occupancy_count * 0.15)
    object_far_outside_points = cdrs.sample_points_outside_mesh(valid_meshes, far_outside_points_count) 
    outside_points += object_far_outside_points

    # Compine points and shuffle
    points = inside_points + outside_points
    random.shuffle(points)
    total_counter = len(points)

    # Find the closest surface to each point
    # The output will be a list of vector: x,y,z,class,distance
    points = cdrs.append_sdf_vectors(valid_meshes, points)

    # Transform all points into the cameras space
    camera_matrix = bpy.context.scene.camera.matrix_world.inverted()
    for p in points:
        new_position = camera_matrix@Vector((p.x,p.y,p.z,1.0))
        p.x = new_position.x
        p.y = new_position.y
        p.z = new_position.z

    # Create the output paths for each possible file
    full_image_path =         output_path + "/" + str(idv).zfill(5) + "_" + output_image_name
    full_occupancy_path_csv = output_path + "/" + str(idv).zfill(5) + "_" + output_occupancy_name_csv
    full_occupancy_path_npz = output_path + "/" + str(idv).zfill(5) + "_" + output_occupancy_name_npz
    full_occupancy_path_pcd = output_path + "/" + str(idv).zfill(5) + "_" + output_occupancy_name_pcd

    # Render image and save it
    bpy.context.scene.render.filepath = full_image_path
    bpy.ops.render.render(write_still = True)



    if file_format == "npz":
        # Save the occupancy data as a numpy array
        points = [np.array(p) for p in points]
        points = np.array(points)
        np.savez(full_occupancy_path_npz, points)
    elif file_format == 'csv':
        # Write .csv file
        cf = open(full_occupancy_path_csv, "w")
        for v in points:
            cf.write(f"{v.x},{v.y},{v.z},{v.w},{v[4]},{v[5]},{v[6]}\n")
        cf.close()
    elif file_format == 'pcd':
        # Write .pcd file
        f = open(full_occupancy_path_pcd, "w")
        f.write("# .PCD v.7 - Point Cloud Data file format\n")
        f.write("VERSION .7\n")
        f.write("FIELDS x y z rgb x_d y_d z_d\n")
        f.write("SIZE 4 4 4 4 4 4 4\n")
        f.write("TYPE F F F F F F F\n")
        f.write("COUNT 1 1 1 1 1 1 1\n")
        f.write(f"WIDTH {total_counter}\n")
        f.write("HEIGHT 1\n")
        f.write("VIEWPOINT 0 0 0 1 0 0 0\n")
        f.write(f"POINTS {total_counter}\n")
        f.write("DATA ascii\n")
        for v in points:
            f.write(f"{v.x} {v.y} {v.z} {v.w} {v[4]} {v[5]} {v[6]}\n")
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
        message = scene.randomize_scene()

        # And again, just to be safe
        bpy.context.view_layer.update()

        # Create data
        if create_test_dataset:
            create_occupancy_test(i)
            create_object_bounding_boxes(i)
        else:
            try:
                create_occupancy(i)
                create_object_bounding_boxes(i)
            except Exception as e:
                # Print error messages, and date
                import datetime

                print(f"\033[91mFailed to create occupancy for index {i}\033[0m")
                print(f"\033[91mException: {e}\033[0m")
                print(f"\033[91mMessage of failed state: {message}\033[0m")
                # Write to log file, in /tmp/create_dataset_log_from_index_to_index.txt
                with open(f"/tmp/create_dataset_log_{from_index}_{to_index}.txt", "a") as f:
                    f.write(f"Date: {datetime.datetime.now()}\n")
                    f.write(f"  Failed to create occupancy for index {i}\n")
                    f.write(f"  Exception: {e}\n")
                    f.write(f"  Message of failed state: {message}\n")
