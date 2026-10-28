"""Check a posed hand against exact original or redesigned handle shells.

This is a geometric reference check, not a fit test on a person. Original meshes
and the saved Blender scene are read-only. Temporary wrist and nail-bed caps are
used solely to make the source skin suitable for a volumetric intersection.
Run with the project's structural-runtime Python (bpy, manifold3d, trimesh).
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET

import bpy
import manifold3d as manifold
import numpy as np
import trimesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from source import read_source, SOURCE, SHA256


def evaluated_mesh(obj):
    """Return the rendered mesh in CAD millimetres, with original vertex order."""
    graph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh()
    mesh.calc_loop_triangles()
    vertices = np.asarray([list(evaluated.matrix_world @ v.co) for v in mesh.vertices]) * 1000
    faces = np.asarray([list(t.vertices) for t in mesh.loop_triangles], dtype=np.int64)
    # A full-rig reflection preserves vertex order but reverses orientation.
    # Restore outward winding in the world-space mesh used by solid checks.
    if evaluated.matrix_world.to_3x3().determinant() < 0:
        faces = faces[:, [0, 2, 1]]
    evaluated.to_mesh_clear()
    return vertices, faces


def evaluated_normals(obj):
    graph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh()
    normal_matrix = evaluated.matrix_world.to_3x3().inverted().transposed()
    normals = np.asarray([list((normal_matrix @ v.normal).normalized()) for v in mesh.vertices])
    evaluated.to_mesh_clear()
    return normals


def solid(vertices, faces):
    result = manifold.Manifold(manifold.Mesh64(
        np.ascontiguousarray(vertices, dtype=np.float64),
        np.ascontiguousarray(faces, dtype=np.uint64)))
    if result.status() != manifold.Error.NoError:
        raise ValueError(f'Manifold conversion failed: {result.status()}')
    return result


def geometry_union(geometry=None):
    """Read assembled CAD-mm meshes; never use print-bed placements."""
    if geometry is None:
        rows, members = read_source()
        settings = ET.fromstring(members['Metadata/model_settings.config'])
        meshes = []
        for row in rows:
            record = settings.find("object[@id='%s']" % row['build_object_id'])
            offset = np.array([float(record.find(
                "part/metadata[@key='source_offset_%s']" % axis).get('value')) for axis in 'xyz'])
            meshes.append((row['name'], row['v'] + offset, row['f']))
    else:
        geometry = Path(geometry).resolve()
        meshes = []
        for name in ['housing', 'cover']:
            with np.load(geometry / (name + '.npz'), allow_pickle=False) as data:
                meshes.append((name, np.asarray(data['v'], dtype=float), np.asarray(data['f'], dtype=np.int64)))
    solids, component_report, comparison = [], [], {}
    for name, vertices, faces in meshes:
        if not np.isfinite(vertices).all():
            raise ValueError('Nonfinite shell coordinates: ' + name)
        comparison[name] = (vertices, faces)
        # Original overlapping components need coordinate welding for splitting.
        # Redesigned Manifold output already has authoritative indexed topology;
        # trimesh's decimal welding can collapse its legitimate tiny edges.
        mesh = trimesh.Trimesh(vertices, faces, process=geometry is None)
        # Housing components intentionally overlap. Inspect and union each closed
        # component instead of interpreting the combined non-manifold mesh as a void.
        for index, component in enumerate(mesh.split(only_watertight=False)):
            if not component.is_watertight or not component.is_winding_consistent:
                raise ValueError(f'{name} component {index} is not a closed oriented solid')
            part = solid(component.vertices, component.faces)
            if part.volume() <= 0:
                raise ValueError(f'{name} component {index} has nonpositive volume')
            solids.append(part)
            component_report.append({'shell': name, 'component': index,
                                     'volume_mm3': float(part.volume()),
                                     'vertices': len(component.vertices), 'triangles': len(component.faces)})
    result = manifold.Manifold.batch_boolean(solids, manifold.OpType.Add)
    if result.status() != manifold.Error.NoError or result.is_empty():
        raise ValueError(f'Shell union failed: {result.status()}')
    return result, component_report, comparison


def source_union():
    return geometry_union()


def weighted_vertex_ids(obj, name, minimum=.8):
    group = obj.vertex_groups.get(name)
    if group is None:
        raise ValueError('Missing landmark skin group: ' + name)
    return np.asarray([v.index for v in obj.data.vertices
                       if any(g.group == group.index and g.weight > minimum for g in v.groups)], dtype=int)


def handedness_report(hand, vertices):
    """Use the neutral anatomical frame, retaining the saved whole-rig reflection.

    A curled distal finger rotates its nail through the palm frame. Combining
    that posed distal normal with uncurled proximal landmarks can reverse an
    arbitrary scalar without changing the hand's anatomical chirality.
    """
    rig = bpy.data.objects['Rig']
    nails = bpy.data.objects['Nails']
    skin_ids = weighted_vertex_ids(hand, 'midd_dist')
    nail_ids = weighted_vertex_ids(nails, 'midd_dist')
    def head(name):
        return np.asarray(rig.matrix_world @ rig.data.bones[name].head_local) * 1000
    wrist = np.asarray(rig.matrix_world @ rig.data.bones['radius_ulna'].tail_local) * 1000
    radial = head('index_prox') - head('pinky_prox')
    distal = head('midd_prox') - wrist
    nail_native = np.asarray([list(v.co) for v in nails.data.vertices])[nail_ids].mean(0)
    skin_native = np.asarray([list(v.co) for v in hand.data.vertices])[skin_ids].mean(0)
    dorsal = (np.asarray(nails.matrix_world @ Vector(nail_native)) -
              np.asarray(hand.matrix_world @ Vector(skin_native))) * 1000
    scalar = float(np.dot(np.cross(distal, radial), dorsal))
    denominator = np.linalg.norm(distal) * np.linalg.norm(radial) * np.linalg.norm(dorsal)
    return {'hand_world_linear_determinant': float(hand.matrix_world.to_3x3().determinant()),
            'radial_pinky_to_index_mcp_cad_mm': radial.tolist(),
            'distal_wrist_to_middle_mcp_cad_mm': distal.tolist(),
            'dorsal_middle_skin_center_to_nail_cad_mm': dorsal.tolist(),
            'anatomical_triple_product_mm3': scalar,
            'normalized_anatomical_triple_product': float(scalar / denominator),
            'chirality': 'right' if scalar > 0 else 'left',
            'reference_frame': 'Native neutral anatomical landmarks transformed by the saved rig/skin/nail world matrices; joint bending excluded.',
            'definition': 'dot(cross(distal wrist-to-middle-MCP, radial pinky-to-index-MCP), neutral dorsal skin-to-nail). Positive is right; source left is negative. The whole-rig reflection is retained. Posed distal nail direction is not a chirality test.'}


def boundary_caps(vertices, faces, source_vertices):
    """Close each simple boundary loop by a temporary consistently oriented fan."""
    directed = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    ordered = np.sort(directed, axis=1)
    unique, inverse, counts = np.unique(ordered, axis=0, return_inverse=True, return_counts=True)
    if np.any(counts > 2):
        raise ValueError('Skin has a non-manifold edge; no reliable capped-volume check')
    boundary = directed[counts[inverse] == 1]
    incoming, outgoing = {}, {}
    for a, b in boundary:
        a, b = int(a), int(b)
        if a in outgoing or b in incoming:
            raise ValueError('Skin boundary branches; no simple closure exists')
        outgoing[a], incoming[b] = b, a
    if set(incoming) != set(outgoing):
        raise ValueError('Skin boundary has an unclosed chain')
    seen, loops = set(), []
    for start in outgoing:
        if start in seen:
            continue
        loop, current = [], start
        while current not in seen:
            seen.add(current)
            loop.append(current)
            current = outgoing[current]
        if current != start or len(loop) < 3:
            raise ValueError('Invalid skin boundary loop')
        loops.append(loop)
    capped_vertices = vertices.tolist()
    capped_faces = faces.tolist()
    report = []
    for loop in loops:
        center = len(capped_vertices)
        capped_vertices.append(vertices[loop].mean(axis=0).tolist())
        for a, b in zip(loop, loop[1:] + loop[:1]):
            # Opposite to the existing boundary half-edge.
            capped_faces.append([b, a, center])
        native = source_vertices[loop]
        report.append({'edge_count': len(loop),
                       'source_bounds': [native.min(0).tolist(), native.max(0).tolist()],
                       'cad_bounds_mm': [vertices[loop].min(0).tolist(), vertices[loop].max(0).tolist()]})
    capped_vertices, capped_faces = np.asarray(capped_vertices), np.asarray(capped_faces)
    mesh = trimesh.Trimesh(capped_vertices, capped_faces, process=False)
    if not mesh.is_watertight or not mesh.is_winding_consistent:
        raise ValueError('Temporary capped skin failed closure/orientation checks')
    if mesh.volume <= 0:
        raise ValueError('Temporary capped skin has nonpositive volume')
    return solid(capped_vertices, capped_faces), report


class ShellDistance:
    def __init__(self, shell):
        self.shell = shell
        mesh = shell.to_mesh64()
        self.vertices = np.asarray(mesh.vert_properties)[:, :3]
        self.faces = np.asarray(mesh.tri_verts, dtype=np.int64)
        self.bvh = BVHTree.FromPolygons(self.vertices.tolist(), self.faces.tolist(), all_triangles=True)
        triangles=self.vertices[self.faces]
        raw=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
        lengths=np.linalg.norm(raw,axis=1)
        self.face_normals=raw/np.maximum(lengths,1e-30)[:,None]
        self.rays = np.array([[1373.239,517.123,311.817],[-431.617,1377.343,619.181],[631.127,-479.913,1381.217]])
        self.ray_disagreement_count = 0
        self.normal_ray_disagreement_count = 0
        self.sign_sample_count = 0
        self.strict_face_sign_count = 0
        self.edge_ray_sign_count = 0

    def strict_face_side(self, point, nearest, face, distance):
        normal=self.face_normals[face]
        side=float(np.dot(point-nearest,normal))
        # The closest point must be inside the actual triangle, rather than on
        # any shared edge, and its vector must be perpendicular to that face.
        tangent=np.linalg.norm(point-nearest-side*normal)
        if tangent>1e-4:return None,side
        triangle=self.vertices[self.faces[face]]
        edge=np.roll(triangle,-1,axis=0)-triangle
        edge_length=np.linalg.norm(edge,axis=1)
        if np.any(edge_length<1e-9):return None,side
        edge_side=np.cross(edge,nearest-triangle)@normal/edge_length
        if np.min(edge_side)<=5e-5:return None,side
        return side<0,side

    def ray_parity(self, point, ray):
        hits = self.shell.ray_cast(point.tolist(), (point + ray).tolist())
        parameters = sorted(hit.distance for hit in hits if hit.distance > 1e-10)
        # Manifold can return numerically distinct hits at a common edge. Merge
        # in physical mm rather than using an unrealistically tiny ray fraction.
        tolerance = 1e-5 / np.linalg.norm(ray)
        count = sum(i == 0 or value - parameters[i - 1] > tolerance
                    for i, value in enumerate(parameters))
        return int(count % 2)

    def __call__(self, points):
        distances = np.empty(len(points))
        nearest = np.empty_like(points, dtype=float)
        for index, point in enumerate(points):
            location, normal, face, distance = self.bvh.find_nearest(Vector(point))
            nearest[index] = tuple(location)
            if distance <= 1e-5:
                distances[index] = 0
                continue
            # The nearest triangle may end at an edge: its normal can be
            # tangential or point to either incident side. Three differently
            # directed rays avoid treating one tiny-edge parity failure as the
            # sign, while the nearest actual surface still supplies magnitude.
            strict_inside,side=self.strict_face_side(point,nearest[index],face,distance)
            if strict_inside is not None:
                inside=strict_inside
                self.strict_face_sign_count+=1
            else:
                votes = [self.ray_parity(point, ray) for ray in self.rays]
                inside = sum(votes) >= 2
                self.edge_ray_sign_count+=1
                self.ray_disagreement_count += int(len(set(votes)) != 1)
                self.normal_ray_disagreement_count += int((side < 0) != inside)
            self.sign_sample_count += 1
            distances[index] = -distance if inside else distance
        return distances, nearest

    def audit(self, points):
        report = []
        for point in points:
            location, normal, face, distance = self.bvh.find_nearest(Vector(point))
            normal=self.face_normals[face]
            normal_side = float(np.dot(point - np.asarray(location), normal))
            parities = [self.ray_parity(point, ray) for ray in self.rays]
            report.append({'point_cad_mm': point.tolist(), 'nearest_surface_cad_mm': list(location),
                           'nearest_outward_normal': normal.tolist(), 'unsigned_distance_mm': float(distance),
                           'point_to_surface_dot_outward_normal_mm': normal_side,
                           'three_ray_inside_votes': parities,
                           'normal_side_inside': normal_side < 0,
                           'rays_agree': len(set(parities)) == 1})
        return {'signed_distance_method': 'Nearest exact union surface supplies magnitude. For a closest point strictly inside one face and perpendicular to it, its outward normal supplies side. At edges/vertices/tangential ambiguity, majority parity of three skew rays supplies sign, merging coincident ray hits within 0.00001 mm.',
                'normal_audit_role': 'Diagnostic comparison only. At a nearest shared edge a single incident face normal can give the wrong side.',
                'signed_samples_so_far': self.sign_sample_count,
                'strict_face_sign_sample_count': self.strict_face_sign_count,
                'edge_or_vertex_three_ray_sign_sample_count': self.edge_ray_sign_count,
                'three_ray_disagreement_sample_count': self.ray_disagreement_count,
                'nearest_normal_vs_ray_majority_disagreement_sample_count': self.normal_ray_disagreement_count,
                'points': report}


def pads(hand):
    vertices = np.asarray([list(v.co) for v in hand.data.vertices])
    normals = np.asarray([list(v.normal) for v in hand.data.vertices])
    rig = bpy.data.objects['Rig']
    weights = {}
    names_to_check=[(finger,finger+'_dist') for finger in ['index','midd','ring','pinky','thumb']]
    names_to_check += [(finger+'_'+part,finger+'_'+part) for finger in ['index','midd','ring','pinky'] for part in ['prox','midd']]
    for finger,name in names_to_check:
        group = hand.vertex_groups.get(name)
        if group is None:
            raise ValueError(f'Missing skin group {name}')
        influence = np.zeros(len(vertices))
        for i, vertex in enumerate(hand.data.vertices):
            for membership in vertex.groups:
                if membership.group == group.index:
                    influence[i] = membership.weight
        bone = rig.data.bones[name]
        along = (vertices - np.asarray(bone.head_local)) @ (
            np.asarray(bone.tail_local) - np.asarray(bone.head_local)) / bone.length ** 2
        ids = np.flatnonzero((influence > .25) & (along > .25) & (along < .95) & (normals[:, 1] < -.35))
        if len(ids) < 3:
            raise ValueError(f'Too few pad vertices in {finger}: {len(ids)}')
        weights[finger] = ids
    names = [b.name for b in rig.data.bones]
    group_to_bone = {group.index: names.index(group.name) for group in hand.vertex_groups if group.name in names}
    all_influence = np.zeros((len(vertices), len(names)))
    for i, vertex in enumerate(hand.data.vertices):
        for membership in vertex.groups:
            if membership.group in group_to_bone:
                all_influence[i, group_to_bone[membership.group]] = membership.weight
    dominant = np.asarray(names)[all_influence.argmax(1)]
    weights['palm'] = np.flatnonzero((vertices[:, 2] > 7) & (vertices[:, 2] < 10) &
                                   (vertices[:, 0] > -5) & (vertices[:, 0] < 2) &
                                   (normals[:, 1] < -.65) & ~np.char.startswith(dominant, 'thumb'))
    if len(weights['palm']) < 3:
        raise ValueError('Too few palm contact vertices')
    regions={
        'central_palm':(vertices[:,2]>7)&(vertices[:,2]<10)&(vertices[:,0]>-4)&(vertices[:,0]<1)&(normals[:,1]<-.65),
        'distal_palm_mcp':(vertices[:,2]>9.5)&(vertices[:,2]<11.8)&(vertices[:,0]>-6.2)&(vertices[:,0]<3.2)&(normals[:,1]<-.6),
        'thenar':(vertices[:,0]>-6.5)&(vertices[:,0]<-2.7)&(vertices[:,2]>4.7)&(vertices[:,2]<8.5)&(normals[:,1]<-.4),
        'hypothenar':(vertices[:,0]>0)&(vertices[:,0]<3.3)&(vertices[:,2]>4.7)&(vertices[:,2]<9.2)&(normals[:,1]<-.4),
        'thumb_index_web':(vertices[:,0]>-7.5)&(vertices[:,0]<-4.4)&(vertices[:,2]>8)&(vertices[:,2]<11.1)&(vertices[:,1]<.1)}
    weights.update({k:np.flatnonzero(mask) for k,mask in regions.items()})
    return weights


def stats(distance):
    return {'sample_count': len(distance), 'minimum_signed_distance_mm': float(distance.min()),
            'maximum_signed_distance_mm': float(distance.max()),
            'distance_p10_mm':float(np.quantile(distance,.1)),
            'distance_p20_mm':float(np.quantile(distance,.2)),
            'distance_median_mm':float(np.median(distance)),
            'samples_inside_by_over_0_05_mm': int(np.sum(distance < -.05)),
            'samples_within_0_5_mm': int(np.sum(np.abs(distance) <= .5)),
            'samples_within_1_mm': int(np.sum(np.abs(distance) <= 1.0))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('blend', nargs='?')
    parser.add_argument('--geometry', help='Directory with assembled CAD-mm housing.npz and cover.npz; omitted means original source.')
    parser.add_argument('--pose-dir', help='Directory containing the pose scene and receiving its report.')
    parser.add_argument('--output')
    args = parser.parse_args()
    pose_dir = Path(args.pose_dir).resolve() if args.pose_dir else HERE
    path = Path(args.blend).resolve() if args.blend else pose_dir / (
        'AdultRightHand_RedesignedHandle.blend' if args.geometry else 'AdultHand_OriginalHandle.blend')
    output_path = Path(args.output).resolve() if args.output else pose_dir / 'contact_check.json'
    scene_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    scene_modified_ns = path.stat().st_mtime_ns
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
    bpy.context.view_layer.update()
    shell, components, comparison = geometry_union(args.geometry)
    unchanged = {}
    for name, (vertices, faces) in comparison.items():
        prefix = 'Redesigned handle ' if args.geometry else 'Original handle '
        obj = bpy.data.objects.get(prefix + name)
        if obj is None:
            raise ValueError('Missing checked handle shell in saved scene: ' + name)
        actual_vertices, actual_faces = evaluated_mesh(obj)
        if actual_vertices.shape != vertices.shape or actual_faces.shape != faces.shape:
            raise ValueError('Checked shell topology changed: ' + name)
        error = float(np.linalg.norm(actual_vertices - vertices, axis=1).max())
        if error > .001 or not np.array_equal(actual_faces, faces):
            raise ValueError(f'Checked shell differs from supplied geometry: {name}, max error {error} mm')
        unchanged[name] = {'vertices': len(vertices), 'triangles': len(faces),
                           'source_to_saved_max_error_mm': error}
    hand = bpy.data.objects['Hand']
    vertices, faces = evaluated_mesh(hand)
    normals = evaluated_normals(hand)
    native = np.asarray([list(v.co) for v in hand.data.vertices])
    if len(vertices) != len(native):
        raise ValueError('Skin modifier changed vertex order/count; pad groups cannot be evaluated')
    capped, caps = boundary_caps(vertices, faces, native)
    penetration = capped ^ shell
    if penetration.status() != manifold.Error.NoError:
        raise ValueError('Boolean intersection failed: ' + str(penetration.status()))
    distance = ShellDistance(shell)
    vertex_distances, vertex_nearest = distance(vertices)
    centroids = vertices[faces].mean(1)
    # Triangles may cross the shell even when all vertices are outside. These
    # additional samples supplement the capped-skin boolean volume.
    centroid_distances, _ = distance(centroids)
    worst_vertex = int(np.argmin(vertex_distances))
    worst_centroid = int(np.argmin(centroid_distances))
    audit_ids = np.unique(np.r_[np.argsort(vertex_distances)[:6], np.argsort(vertices[:,1])[:4],
                               np.arange(0,len(vertices),max(1,len(vertices)//8))])
    sign_audit = distance.audit(vertices[audit_ids])
    finger_report = {}
    pad_ids = pads(hand)
    for finger, ids in pad_ids.items():
        d = vertex_distances[ids]
        closest = int(ids[np.argmin(np.abs(d))])
        normal = normals[ids].mean(0)
        normal /= np.linalg.norm(normal)
        finger_report[finger] = dict(stats(d), pad_mean_cad_mm=vertices[ids].mean(0).tolist(),
                                    pad_mean_outward_normal_cad=normal.tolist(),
                                    closest_pad_cad_mm=vertices[closest].tolist(),
                                    nearest_actual_shell_cad_mm=vertex_nearest[closest].tolist())
    thumb_ids = pad_ids['thumb']
    thumb = vertices[thumb_ids]
    thumb_reference = {'face_reference_y_mm': 23.5,
                       'pad_mean_cad_mm': thumb.mean(0).tolist(),
                       'pad_minimum_height_above_reference_mm': float(thumb[:, 1].min() - 23.5),
                       'pad_mean_height_above_reference_mm': float(thumb[:, 1].mean() - 23.5),
                       'pad_vertices_over_array_extent': int(np.sum(
                           (thumb[:, 0] >= 48) & (thumb[:, 0] <= 80) & (np.abs(thumb[:, 2]) <= 16))),
                       'note': 'This height/extent check uses only the declared touch-face datum. '
                               'The reference module boxes are excluded from the checked shell union. '
                               'It does not verify a complete physical module/PCB assembly.'}
    nails = bpy.data.objects.get('Nails')
    nail_report = None
    if nails:
        nv, nf = evaluated_mesh(nails)
        nd, _ = distance(nv)
        nail_report = stats(nd)
    output = {'blend': str(path), 'blend_sha256_at_read': scene_hash,
              'blend_modified_ns_at_read': scene_modified_ns,
              'blend_unchanged_during_check': hashlib.sha256(path.read_bytes()).hexdigest() == scene_hash,
              'units': 'millimetres',
              'source_handle_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              'source_handle_expected_sha256': SHA256,
              'geometry_directory': str(Path(args.geometry).resolve()) if args.geometry else None,
              'checked_shell_meshes': unchanged,
              'checked_shell_closed_components': components,
              'shell_geometry_sha256': {name: hashlib.sha256((Path(args.geometry) / (name + '.npz')).read_bytes()).hexdigest() for name in comparison} if args.geometry else None,
              'unchanged_source_shells': unchanged if not args.geometry else None,
              'original_closed_components': components if not args.geometry else None,
              'handedness': handedness_report(hand, vertices),
              'shell_union_volume_mm3': float(shell.volume()),
              'temporary_capped_skin_volume_mm3': float(capped.volume()),
              'temporary_skin_caps': caps,
              'skin_shell_boolean_overlap_volume_mm3': float(penetration.volume()),
              'capped_skin_shell_minimum_gap_with_5_mm_search_mm': float(capped.min_gap(shell, 5.0)),
              'skin_vertex_distances': stats(vertex_distances),
              'skin_triangle_centroid_distances': stats(centroid_distances),
              'signed_distance_audit': sign_audit,
              'deepest_skin_vertex': {'index': worst_vertex, 'cad_mm': vertices[worst_vertex].tolist(),
                                     'nearest_actual_shell_cad_mm': vertex_nearest[worst_vertex].tolist()},
              'deepest_skin_triangle_centroid': {'triangle': worst_centroid,
                                                 'cad_mm': centroids[worst_centroid].tolist()},
              'finger_pads_to_actual_shell': finger_report,
              'thumb_touch_face_reference': thumb_reference,
              'nail_vertex_distances': nail_report,
              'limits': ['The source skin has six openings: wrist and five nail beds. '
                         'Temporary fan caps are used only in memory for a closed-solid volume check; '
                         'actual vertex/triangle-centroid reports exclude those caps.',
                         'Joint deformation can self-intersect. Boolean volume is interpreted together '
                         'with actual skin samples and visual inspection, not as a person-specific fit certificate.',
                         'Signed distances sample vertices and triangle centroids. Narrow triangle crossings '
                         'can be missed by sampling; the closed-solid boolean is the complementary check.',
                         'Touch-face datum objects are excluded. Shell clearance is not tactile contact verification.']}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding='utf8')
    print(json.dumps({'output': str(output_path), 'handedness': output['handedness'], 'shell_volume_mm3': output['shell_union_volume_mm3'],
                      'skin_shell_overlap_mm3': output['skin_shell_boolean_overlap_volume_mm3'],
                      'skin_minimum_signed_distance_mm': vertex_distances.min(),
                      'centroid_minimum_signed_distance_mm': centroid_distances.min(),
                      'finger_pad_minimum_signed_distance_mm': {
                          f: r['minimum_signed_distance_mm'] for f, r in finger_report.items()},
                      'thumb_reference': thumb_reference}, indent=2), flush=True)


if __name__ == '__main__':
    main()
