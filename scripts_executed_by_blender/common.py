import bpy
import mathutils
import random
from mathutils import Vector
from mathutils import Matrix

BOUNDING_BOX_SIZE_FACTOR = 1.5

class BlenderObject:
    def __init__(self, ob, unique_id : int):
        self.ob = ob
        self.name = ob.name
        self.matrix_world = ob.matrix_world
        self.scale = ob.scale
        self.world_space_bbox_corners = self.compute_world_space_bbox()
        self.world_space_bbox = self.bounding_box_to_extreme_points(self.world_space_bbox_corners)
        self.world_space_bbox_center = (self.world_space_bbox[0] + self.world_space_bbox[1]) / 2
        # TODO Removed the transition wall from the radius, but this may cause issues?
        #self.radius = (self.world_space_bbox_center - self.world_space_bbox[0]).length + scene.get_transition_wall()
        self.radius = (self.world_space_bbox_center - self.world_space_bbox[0]).length

        centered_world_space_bbox_corners_scaled = [(corner - self.world_space_bbox_center) * BOUNDING_BOX_SIZE_FACTOR for corner in self.world_space_bbox_corners]
        self.world_space_bbox_corners_scaled = [corner + self.world_space_bbox_center for corner in centered_world_space_bbox_corners_scaled]
        self.world_space_bbox_scaled = self.bounding_box_to_extreme_points(self.world_space_bbox_corners_scaled)
        self.unique_id = unique_id


    def compute_world_space_bbox(self, slow = False):
        if not slow:
            return [self.ob.matrix_world @ Vector(corner) for corner in self.ob.bound_box]
        else:
            # Access the dependency graph
            dg = bpy.context.evaluated_depsgraph_get()

            # Evaluate the object to get the version with modifiers applied
            eval_obj = self.ob.evaluated_get(dg)

            # Get the mesh data from the evaluated object
            mesh = eval_obj.to_mesh()

            # Convert mesh vertices to world space
            world_vertices = [self.ob.matrix_world @ v.co for v in mesh.vertices]

            # Compute min and max coordinates
            min_x = min(v.x for v in world_vertices)
            min_y = min(v.y for v in world_vertices)
            min_z = min(v.z for v in world_vertices)
            max_x = max(v.x for v in world_vertices)
            max_y = max(v.y for v in world_vertices)
            max_z = max(v.z for v in world_vertices)

            # Define the 8 corners of the bounding box
            bbox_corners = [
                (min_x, min_y, min_z),
                (max_x, min_y, min_z),
                (max_x, max_y, min_z),
                (min_x, max_y, min_z),
                (min_x, min_y, max_z),
                (max_x, min_y, max_z),
                (max_x, max_y, max_z),
                (min_x, max_y, max_z),
            ]

            # Convert to Vector objects
            bbox_corners = [Vector(corner) for corner in bbox_corners]

            # Clear the temporary mesh data from the evaluated object
            eval_obj.to_mesh_clear()
            return bbox_corners

    def compute_camera_space_bbox_extreme_points(self, slow=False):
        """
        Compute the extreme points of the object's bounding box in camera space
        Important note: always compute the extreme points in the final coordinate system that
        you are interested in. Otherwise, the extreme points will not be correct.
        """
        if not slow:
            camera = bpy.context.scene.camera
            camera_matrix = camera.matrix_world.inverted()
            bbox_corners =  [camera_matrix@self.ob.matrix_world @ Vector(corner) for corner in self.ob.bound_box]
            return self.bounding_box_to_extreme_points(bbox_corners)
        else:

            # Access the dependency graph
            dg = bpy.context.evaluated_depsgraph_get()

            # Evaluate the object to get the version with modifiers applied
            eval_obj = self.ob.evaluated_get(dg)

            # Get the mesh data from the evaluated object
            mesh = eval_obj.to_mesh()

            # Get camera transformation matrix
            camera = bpy.context.scene.camera
            camera_matrix = camera.matrix_world.inverted()

            # Convert mesh vertices to world space
            world_vertices = [camera_matrix @ self.ob.matrix_world @ v.co for v in mesh.vertices]

            # Compute min and max coordinates
            min_x = min(v.x for v in world_vertices)
            min_y = min(v.y for v in world_vertices)
            min_z = min(v.z for v in world_vertices)
            max_x = max(v.x for v in world_vertices)
            max_y = max(v.y for v in world_vertices)
            max_z = max(v.z for v in world_vertices)

            # Define the 8 corners of the bounding box
            bbox_corners = [
                (min_x, min_y, min_z),
                (max_x, min_y, min_z),
                (max_x, max_y, min_z),
                (min_x, max_y, min_z),
                (min_x, min_y, max_z),
                (max_x, min_y, max_z),
                (max_x, max_y, max_z),
                (min_x, max_y, max_z),
            ]

            # Convert to Vector objects
            bbox_corners = [Vector(corner) for corner in bbox_corners]

            # Clear the temporary mesh data from the evaluated object
            eval_obj.to_mesh_clear()

            return self.bounding_box_to_extreme_points(bbox_corners)


    def bounding_box_to_extreme_points(self, bbox) -> tuple[Vector, Vector]:
        """ Computes the extreme points of the input bounding box """
        x_min = min(bbox, key = lambda k: k[0])[0]
        y_min = min(bbox, key = lambda k: k[1])[1]
        z_min = min(bbox, key = lambda k: k[2])[2]
        x_max = max(bbox, key = lambda k: k[0])[0]
        y_max = max(bbox, key = lambda k: k[1])[1]
        z_max = max(bbox, key = lambda k: k[2])[2]
        return (mathutils.Vector((x_min,y_min,z_min)), mathutils.Vector((x_max,y_max,z_max)))

    def point_inside_bounding_box(self, point : Vector) -> bool:
        """ Check if point is inside the object's bounding box """
        return self.world_space_bbox[0][0] <= point[0] <= self.world_space_bbox[1][0] and \
               self.world_space_bbox[0][1] <= point[1] <= self.world_space_bbox[1][1] and \
               self.world_space_bbox[0][2] <= point[2] <= self.world_space_bbox[1][2]

    def point_inside_bounding_box_scaled(self, point : Vector) -> bool:
        """ Check if point is inside the object's bounding box """
        return self.world_space_bbox_scaled[0][0] <= point[0] <= self.world_space_bbox_scaled[1][0] and \
               self.world_space_bbox_scaled[0][1] <= point[1] <= self.world_space_bbox_scaled[1][1] and \
               self.world_space_bbox_scaled[0][2] <= point[2] <= self.world_space_bbox_scaled[1][2]

    def fast_inside_radius(self, world_position : Vector) -> bool:
        """ Fast check if the point is inside the object's radius """
        return (world_position - self.world_space_bbox_center).length < self.radius

    def world_to_object_space(self, world_position : Vector) -> Vector:
        """ Transforms a world space position to object space """
        return self.ob.matrix_world.inverted() @ world_position

    def object_to_world_space(self, object_position : Vector) -> Vector:
        """ Transforms an object space position to world space """
        return self.ob.matrix_world @ object_position

    def closest_point_on_mesh(self, object_position : Vector):
        """ Returns the closest points on the object's mesh (just a wrapper from for
        the Blender implementation) """
        return self.ob.closest_point_on_mesh(object_position)

    def distance_to_mesh(self, object_position: Vector, return_as_vector : bool = False) -> float:
        """ Returns the distance to the object's mesh """
        _, closest_point, _, _ = self.ob.closest_point_on_mesh(object_position)
        scale_matrix = Matrix(
            (
                (self.ob.scale[0], 0, 0),
                (0, self.ob.scale[1], 0),
                (0, 0, self.ob.scale[2]),
            ),
        )
        difference_vector = scale_matrix @ (closest_point - object_position)
        if return_as_vector:
            return difference_vector
        else:
            return difference_vector.length

    def world_distance_to_mesh(self, world_position: Vector, return_as_vector : bool = False) -> float:
        """ Returns the distance to the object's mesh """
        point = self.matrix_world.inverted() @ world_position
        return self.distance_to_mesh(point, return_as_vector)

    def ray_cast(self, object_position, object_direction):
        """ Casts a ray to intersect the object (just a wrapper from for
        the Blender implementation)
        """
        return self.ob.ray_cast(object_position, object_direction)

    def point_inside_mesh_basic(self, point : Vector) -> bool:
        """
        Returns bool

        Checks if a point is inside an object
        """
        ob = self
        #r1 = [random.uniform(-1,1) for _ in range(9)]
        #r2 = [random.uniform(-1,1) for _ in range(3)]
        #r3 = [random.uniform(-1,1) for _ in range(3)]
        #base = [ mathutils.Vector(r1[0:3]), mathutils.Vector(r1[3:6]), mathutils.Vector(r1[6:9]) ]
        base = [ mathutils.Vector((1,0,0)), mathutils.Vector((0,1,0)), mathutils.Vector((0,0,1))  ]


        q_point = ob.matrix_world.inverted() @ point
        outside_if_positive = 0

        for b in base:
            origin = q_point

            surface_hit_count = 0
            while True:
                (hit, location,_,_) = ob.ray_cast(origin,b)
                if not hit:
                    # Check if first sample already misses - fast way out
                    if surface_hit_count == 0 and outside_if_positive == 0:
                        return False
                    # We can't return, else there may be false negatives
                    # Instead we count and do a majority decision
                    if surface_hit_count%2 == 0:
                        outside_if_positive += 1
                    else:
                        outside_if_positive -= 1
                    surface_hit_count = 0
                    break
                    #break

                surface_hit_count += 1
                origin = location + b*0.00001

        return (outside_if_positive < 0)
        #return True

    def point_inside_mesh_basic_with_distance(self, point : Vector) -> tuple[bool, float]:
        """
        Returns bool

        Checks if a point is inside an object
        """
        ob = self
        #r1 = [random.uniform(-1,1) for _ in range(9)]
        #r2 = [random.uniform(-1,1) for _ in range(3)]
        #r3 = [random.uniform(-1,1) for _ in range(3)]
        #base = [ mathutils.Vector(r1[0:3]), mathutils.Vector(r1[3:6]), mathutils.Vector(r1[6:9]) ]
        base = [ mathutils.Vector((1,0,0)), mathutils.Vector((0,1,0)), mathutils.Vector((0,0,1))]
        #base = []
        base_extra = [ mathutils.Vector((1,1,0)), mathutils.Vector((1,0,1)), mathutils.Vector((0,1,1)) ]
        base = base + base_extra


        q_point = ob.matrix_world.inverted() @ point
        outside_if_positive = 0
        distance = ob.distance_to_mesh(q_point)

        for b in base:
            origin = q_point

            surface_hit_count = 0
            while True:
                #(hit, location,_,_) = ob.ray_cast(origin,origin+b*10000.0)
                #(hit, location,_,_) = ob.ray_cast(origin,origin+b*10000.0)
                (hit, location,_,_) = ob.ray_cast(origin,b)
                if not hit:
                    # Check if first sample already misses - fast way out
                    if surface_hit_count == 0 and outside_if_positive == 0:
                        return (False, distance)
                    # We can't return, else there may be false negatives
                    # Instead we count and do a majority decision
                    if surface_hit_count%2 == 0:
                        outside_if_positive += 1
                    else:
                        outside_if_positive -= 1
                    surface_hit_count = 0
                    break
                    #break

                surface_hit_count += 1
                origin = location + b*0.00001

        return ((outside_if_positive < 0), distance)

def ignore_obj(ob) -> bool:
    """
    Returns bool

    Given an object, this functions decides if the object is to be
    ignored for the occupancy computation.
    """
    if(ob == bpy.context.scene.camera):
        return True
    if(ob.name == "Background"):
        return True
    if(ob.name[0] == "0"):
        return True
    if(ob.name[0:3] == "WGT"):
        return True
    return False

def get_valid_meshes() -> list:
    """ Returns a list of all valid meshes in the Blender scene """
    valid_meshes = list(filter(lambda x: not(ignore_obj(x)), bpy.data.objects))
    #valid_meshes = [BlenderObject(x) for x in valid_meshes]
    valid_meshes = [BlenderObject(x, id + 1) for id, x in enumerate(valid_meshes)]
    return valid_meshes

def intersecting_bounding_box(a, b) -> bool:
    """ We do not need to extend the bounding box of the other object """
    corners1 = a.world_space_bbox_scaled
    corners2 = b.world_space_bbox

    return (corners1[0][0] <= corners2[1][0] and corners1[1][0] >= corners2[0][0] and
            corners1[0][1] <= corners2[1][1] and corners1[1][1] >= corners2[0][1] and
            corners1[0][2] <= corners2[1][2] and corners1[1][2] >= corners2[0][2])

def scene_extreme_points(valid_meshes) -> tuple[Vector, Vector]:
    """
    Returns Vector, Vector

    Returns the min and max points of the scene.
    """
    min_point = Vector((1000000,1000000,1000000))
    max_point = Vector((-1000000,-1000000,-1000000))
    for ob in valid_meshes:
        corners = ob.world_space_bbox
        min_point = Vector((min(corners[0][0],min_point[0]),min(corners[0][1],min_point[1]),min(corners[0][2],min_point[2])))
        max_point = Vector((max(corners[1][0],max_point[0]),max(corners[1][1],max_point[1]),max(corners[1][2],max_point[2])))

    return (min_point,max_point)

def point_inside_any_mesh_objects_inside_objects(valid_meshes, point) -> int:
    """
    Returns int

    Checks if a point is inside any object. If it inside an object
    the id of the object will be returned (position in enumeration).
    If it is inside multiple objects, the id of the object closest to the
    point will be returned.
    """
    ob_id = 0
    inside_ids = []
    for ob in valid_meshes:
        ob_id += 1
        if not ob.fast_inside_radius(point):
            continue
        inside, distance = ob.point_inside_mesh_basic_with_distance(point)
        if inside:
            inside_ids.append((ob_id, distance))

    if len(inside_ids) > 0:
        inside_ids.sort(key=lambda x: x[1])
        return inside_ids[0][0]
    return 0

def point_inside_any_mesh(valid_meshes, point) -> int:
    """
    Returns int

    Checks if a point is inside any object. If it inside an object
    the id of the object will be returned (position in enumeration).
    """
    ob_id = 0
    for ob in valid_meshes:
        ob_id += 1
        if not ob.fast_inside_radius(point):
            continue
        if ob.point_inside_mesh_basic(point):
            return ob_id
    return 0


def point_inside_any_bbox_scaled(valid_meshes, point):
    """
    Returns int

    Checks if a point is inside any bounding box. If it inside an object
    the id of the object will be returned (position in enumeration).
    """
    ob_id = 0
    for ob in valid_meshes:
        ob_id += 1
        if ob.point_inside_bounding_box_scaled(point):
            return ob_id
    return 0

def get_equilateral_scene_bounding_box(valid_meshes, scale_factor=1.0) -> tuple[Vector, Vector]:
    """ Compute the equilateral scene bounding box """
    min_point, max_point = scene_extreme_points(valid_meshes)
    mid_point = (min_point + max_point)/2
    max_distance_to_mid_along_axis = max(abs(min_point[0]-mid_point[0]),abs(min_point[1]-mid_point[1]),abs(min_point[2]-mid_point[2])) * scale_factor
    min_point = mid_point - (Vector((1,1,1))*max_distance_to_mid_along_axis)
    max_point = mid_point + (Vector((1,1,1))*max_distance_to_mid_along_axis)
    return (min_point, max_point)



def sample_points_outside_mesh(valid_meshes : list, num_samples_to_draw : int) -> list:
    """
    Sample points in extended scene bounding box but discard them if they are inside any mesh
    The scene bounding box is always equilateral and centered around the origin.
    """
    min_point, max_point = get_equilateral_scene_bounding_box(valid_meshes, BOUNDING_BOX_SIZE_FACTOR)

    points = []
    while len(points) < num_samples_to_draw:
        point = Vector((random.uniform(min_point[0],max_point[0]),random.uniform(min_point[1],max_point[1]),random.uniform(min_point[2],max_point[2])))
        if point_inside_any_mesh(valid_meshes, point) != 0:
            continue
        points.append(Vector((point[0],point[1],point[2], 0, 100000)))

    return points

def append_sdf_vectors(valid_meshes : list, points : list) -> list:
    """
    Appends the vector pointing to the nearest surface.
    """
    new_points = []
    for p in points:
        p_pos = p.xyz
        min_d = float("inf")
        min_vector = Vector((0,0,0))
        for ob in valid_meshes:
            to_surface_vector = ob.world_distance_to_mesh(p.xyz, return_as_vector=True)
            if to_surface_vector.length < min_d:
                min_d = to_surface_vector.length
                min_vector = to_surface_vector
        # x,y,z,class,nx,ny,nz
        new_points.append(Vector((p[0],p[1],p[2], p[3], min_vector[0], min_vector[1], min_vector[2])))
    return new_points
