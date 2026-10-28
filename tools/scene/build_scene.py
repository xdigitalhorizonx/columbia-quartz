# Builds the Columbia Quartz hero scene in Blender (Cycles) and saves scene.blend in the source folder.
#   blender -b --factory-startup --python tools/scene/build_scene.py -- --src C:/dev/columbia-quartz-source/3d
# <src> holds assets/ (CC0 scans and textures, see README) and tex/slab-lx-gold-tex.png (Columbia's slab photo).
# Units are metres, Z up. The island runs along X; its front edge (-Y) faces the camera at the end of the move.
import bpy, bmesh, math, os, random, sys
from mathutils import Vector, Euler, Matrix, noise as mnoise

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
opt = {argv[i][2:]: argv[i + 1] for i in range(0, len(argv) - 1, 2)}
SRC = opt.get('src', r'C:\dev\columbia-quartz-source\3d')
A = os.path.join(SRC, 'assets')
TEX = os.path.join(SRC, 'tex')

TOP_Z = 0.92                 # counter height
EDGE = 0.10                  # mitred apron depth
X0, X1, Y0, Y1 = -1.45, 1.5, -0.55, 0.55  # island top
SLAB_W = 3.2                 # the slab photo covers 3.2 m; its height follows the image aspect
SLAB_OFF = (0.93, 0.02)      # where the island sits on the slab: puts its strongest gold vein over the front edge

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
rng = random.Random(7)


# ---------- helpers ----------
def link(obj):
    scene.collection.objects.link(obj)
    return obj

def new_mat(name):
    m = bpy.data.materials.new(name)
    return m, m.node_tree.nodes, m.node_tree.links

def principled(nodes):
    return next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')

def inp(node, ident):
    return next(s for s in node.inputs if s.identifier == ident or (s.name == ident and s.enabled))

def out(node, ident):
    return next(s for s in node.outputs if s.identifier == ident or (s.name == ident and s.enabled))

def img(nodes, path, srgb=True):
    n = nodes.new('ShaderNodeTexImage')
    n.image = bpy.data.images.load(path, check_existing=True)
    n.image.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    n.interpolation = 'Cubic'
    return n

def mix(nodes, links, a, b, blend='MIX', fac=1.0):
    n = nodes.new('ShaderNodeMix'); n.data_type = 'RGBA'; n.blend_type = blend
    f = inp(n, 'Factor_Float')
    if isinstance(fac, (int, float)): f.default_value = fac
    else: links.new(fac, f)
    for s, v in ((inp(n, 'A_Color'), a), (inp(n, 'B_Color'), b)):
        if isinstance(v, tuple): s.default_value = v if len(v) == 4 else (*v, 1)
        else: links.new(v, s)
    return out(n, 'Result_Color')

def math_node(nodes, links, op, a, b=None, clamp=False):
    n = nodes.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
    for s, v in zip(n.inputs, (a, b)):
        if v is None: continue
        if isinstance(v, (int, float)): s.default_value = v
        else: links.new(v, s)
    return n.outputs[0]

def map_range(nodes, links, v, lo, hi, a=0.0, b=1.0):
    n = nodes.new('ShaderNodeMapRange')
    n.inputs['From Min'].default_value = a; n.inputs['From Max'].default_value = b
    n.inputs['To Min'].default_value = lo; n.inputs['To Max'].default_value = hi
    links.new(v, n.inputs['Value'])
    return n.outputs['Result']

def noise(nodes, links, scale, detail=2.0, rough=0.5, coord='Object', w=None):
    n = nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail; n.inputs['Roughness'].default_value = rough
    tc = nodes.new('ShaderNodeTexCoord'); links.new(tc.outputs[coord], n.inputs['Vector'])
    return n.outputs['Fac']

def bump(nodes, links, height, strength, distance=0.001, normal=None):
    b = nodes.new('ShaderNodeBump'); b.inputs['Strength'].default_value = strength
    b.inputs['Distance'].default_value = distance
    links.new(height, b.inputs['Height'])
    if normal is not None: links.new(normal, b.inputs['Normal'])
    return b.outputs['Normal']

def speckle(nodes, links, scale, density):
    """Tiny dark flecks, as in glazed stoneware: thresholded cellular noise."""
    v = nodes.new('ShaderNodeTexVoronoi'); v.feature = 'F1'; v.inputs['Scale'].default_value = scale
    v.inputs['Randomness'].default_value = 1.0
    tc = nodes.new('ShaderNodeTexCoord'); links.new(tc.outputs['Object'], v.inputs['Vector'])
    return map_range(nodes, links, v.outputs['Distance'], 1.0, 0.0, density * 0.6, density)

def simple_mat(name, color, rough=0.5, metal=0.0, coat=0.0):
    m, nodes, links = new_mat(name)
    p = principled(nodes)
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    if coat: p.inputs['Coat Weight'].default_value = coat
    return m

def box(name, x0, x1, y0, y1, z0, z1, mat=None, bevel=0.0):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 if v.co.x < 0 else x1
        v.co.y = y0 if v.co.y < 0 else y1
        v.co.z = z0 if v.co.z < 0 else z1
    bm.to_mesh(me); bm.free()
    o = link(bpy.data.objects.new(name, me))
    if mat: o.data.materials.append(mat)
    if bevel:
        b = o.modifiers.new('bevel', 'BEVEL'); b.width = bevel; b.segments = 3; b.limit_method = 'ANGLE'
        b.harden_normals = False
    return o

def lathe(name, prof, mat, steps=96, subsurf=2):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    vs = [bm.verts.new((r, 0, z)) for r, z in prof]
    for a, b in zip(vs, vs[1:]): bm.edges.new((a, b))
    bmesh.ops.spin(bm, geom=bm.verts[:] + bm.edges[:], cent=(0, 0, 0), axis=(0, 0, 1),
                   angle=2 * math.pi, steps=steps, use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for f in me.polygons: f.use_smooth = True
    o = link(bpy.data.objects.new(name, me))
    o.data.materials.append(mat)
    if subsurf:
        s = o.modifiers.new('sub', 'SUBSURF'); s.levels = s.render_levels = subsurf
    return o

def handmade(o, amount, scale=0.35):
    """A little low-frequency wobble, so thrown pottery is not machine-perfect."""
    t = bpy.data.textures.new(o.name + ' wobble', 'CLOUDS'); t.noise_scale = scale; t.noise_depth = 1
    d = o.modifiers.new('wobble', 'DISPLACE'); d.texture = t; d.strength = amount; d.mid_level = 0.5
    d.texture_coords = 'OBJECT'
    return o

def import_gltf(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    for o in new:
        if o.type != 'MESH': bpy.data.objects.remove(o)
    for o in meshes: o.parent = None
    return meshes

def select_only(o):
    for s in bpy.context.selected_objects: s.select_set(False)
    bpy.context.view_layer.objects.active = o; o.select_set(True)

def apply_all(o):
    select_only(o)
    for m in list(o.modifiers): bpy.ops.object.modifier_apply(modifier=m.name)
    o.select_set(False)


# ---------- render settings ----------
scene.render.engine = 'CYCLES'
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
for d in prefs.devices: d.use = d.type == 'OPTIX'
c = scene.cycles
c.device = 'GPU'
c.samples = 384
c.adaptive_threshold = 0.01
c.use_denoising = True
c.denoiser = 'OPENIMAGEDENOISE'
c.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
c.denoising_prefilter = 'ACCURATE'
c.denoising_use_gpu = True
c.max_bounces = 10; c.diffuse_bounces = 5; c.glossy_bounces = 5; c.transmission_bounces = 6
c.transparent_max_bounces = 8; c.volume_bounces = 0
c.sample_clamp_indirect = 6
c.blur_glossy = 0.6
c.caustics_reflective = False; c.caustics_refractive = False
c.use_light_tree = True
c.seed = 11
c.film_exposure = 1.0
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Punchy'
scene.render.film_transparent = False
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_depth = '16'


# ---------- world: a real outdoor HDRI, seen blown out through the windows ----------
world = bpy.data.worlds.new('World'); scene.world = world
wn, wl = world.node_tree.nodes, world.node_tree.links
for n in list(wn): wn.remove(n)
env = wn.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(os.path.join(A, 'hdri', 'meadow_4k.hdr'))
wmap = wn.new('ShaderNodeMapping'); wtc = wn.new('ShaderNodeTexCoord')
wmap.inputs['Rotation'].default_value = (0, 0, math.radians(200))
wl.new(wtc.outputs['Generated'], wmap.inputs['Vector']); wl.new(wmap.outputs['Vector'], env.inputs['Vector'])
cap = wn.new('ShaderNodeVectorMath'); cap.operation = 'MINIMUM'; cap.inputs[1].default_value = (3.0, 3.0, 3.0)
wl.new(env.outputs['Color'], cap.inputs[0])       # the sun lamp lights the room; clip the HDRI's own sun
bg = wn.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 1.0
seen = wn.new('ShaderNodeBackground'); seen.inputs['Strength'].default_value = 5.0
wl.new(cap.outputs['Vector'], bg.inputs['Color'])
haze = wn.new('ShaderNodeMix'); haze.data_type = 'RGBA'; haze.inputs['Factor'].default_value = 0.55
wl.new(cap.outputs['Vector'], haze.inputs[6]); haze.inputs[7].default_value = (1.0, 0.93, 0.82, 1)
wl.new(haze.outputs[2], seen.inputs['Color'])
lp = wn.new('ShaderNodeLightPath')
eye = wn.new('ShaderNodeMath'); eye.operation = 'MAXIMUM'
wl.new(lp.outputs['Is Camera Ray'], eye.inputs[0]); wl.new(lp.outputs['Is Glossy Ray'], eye.inputs[1])
wmix = wn.new('ShaderNodeMixShader'); wl.new(eye.outputs[0], wmix.inputs['Fac'])
wl.new(bg.outputs['Background'], wmix.inputs[1]); wl.new(seen.outputs['Background'], wmix.inputs[2])
wo = wn.new('ShaderNodeOutputWorld')
wl.new(wmix.outputs['Shader'], wo.inputs['Surface'])


# ---------- quartz: Columbia's real Calacatta LX Gold slab photo ----------
slab_img = bpy.data.images.load(os.path.join(TEX, 'slab-lx-gold-tex.png'))
SLAB_H = SLAB_W * slab_img.size[1] / slab_img.size[0]
quartz, qn, ql = new_mat('Quartz LX Gold')
qp = principled(qn)
qt = qn.new('ShaderNodeTexImage'); qt.image = slab_img; qt.interpolation = 'Cubic'; qt.extension = 'MIRROR'
quv = qn.new('ShaderNodeUVMap'); quv.uv_map = 'UV'; ql.new(quv.outputs['UV'], qt.inputs['Vector'])
grain = map_range(qn, ql, noise(qn, ql, 2400, 2), 0.975, 1.0)        # resin-bound grain, below the vein scale
cloud = map_range(qn, ql, noise(qn, ql, 3.0, 3), 0.985, 1.01)         # faint cloudiness of the batch
g = qn.new('ShaderNodeCombineColor')
gm = math_node(qn, ql, 'MULTIPLY', grain, cloud)
for i in range(3): ql.new(gm, g.inputs[i])
deep = mix(qn, ql, qt.outputs['Color'], qt.outputs['Color'], 'MULTIPLY', 0.75)
lift = mix(qn, ql, deep, (1.13, 1.12, 1.1), 'MULTIPLY')
qhs = qn.new('ShaderNodeHueSaturation'); qhs.inputs['Saturation'].default_value = 1.25
ql.new(lift, qhs.inputs['Color'])
ql.new(mix(qn, ql, qhs.outputs['Color'], g.outputs['Color'], 'MULTIPLY'), qp.inputs['Base Color'])
wipe = noise(qn, ql, 1.6, 6, 0.62)                                    # polish is never perfectly even
ql.new(map_range(qn, ql, wipe, 0.035, 0.11, 0.35, 0.75), qp.inputs['Roughness'])
qp.inputs['IOR'].default_value = 1.54
qp.inputs['Specular IOR Level'].default_value = 0.55
peel = noise(qn, ql, 55, 2)                                           # the faint orange peel of a polished face
bev = qn.new('ShaderNodeBevel'); bev.inputs['Radius'].default_value = 0.0015; bev.samples = 6
ql.new(bump(qn, ql, peel, 0.025, 0.0004, bev.outputs['Normal']), qp.inputs['Normal'])

def slab_uv(x, y):
    return ((x + SLAB_W / 2 + SLAB_OFF[0]) / SLAB_W, (y + SLAB_H / 2 + SLAB_OFF[1]) / SLAB_H)

def countertop():
    """Island top with a mitred apron. The apron faces are unfolded from the top on the slab, so the
    veins run over the edge exactly the way a mitred apron cut from the same slab does."""
    o = box('Countertop', X0, X1, Y0, Y1, TOP_Z - EDGE, TOP_Z, quartz)
    me = o.data; uv = me.uv_layers.new(name='UV')
    for poly in me.polygons:
        nrm = poly.normal
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            drop = TOP_Z - co.z
            if nrm.z > 0.5 or nrm.z < -0.5: u, v = slab_uv(co.x, co.y)
            elif nrm.y < -0.5: u, v = slab_uv(co.x, Y0 - drop)
            elif nrm.y > 0.5: u, v = slab_uv(co.x, Y1 + drop)
            elif nrm.x < -0.5: u, v = slab_uv(X0 - drop, co.y)
            else: u, v = slab_uv(X1 + drop, co.y)
            uv.data[li].uv = (u, v)
    b = o.modifiers.new('ease', 'BEVEL'); b.width = 0.0022; b.segments = 4; b.limit_method = 'ANGLE'
    return o

top = countertop()


# ---------- island base: fluted walnut ----------
def walnut_mat(name, tint, rough=0.42):
    m, nodes, links = new_mat(name)
    p = principled(nodes)
    uvn = nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'UV'
    def tex(suffix, srgb):
        n = img(nodes, os.path.join(A, 'walnut', f'smoked_walnut_veneer_{suffix}_2k.jpg'), srgb)
        links.new(uvn.outputs['UV'], n.inputs['Vector'])
        return n
    d = tex('diff', True)
    links.new(mix(nodes, links, d.outputs['Color'], tint, 'MULTIPLY'), p.inputs['Base Color'])
    r = tex('rough', False)
    links.new(map_range(nodes, links, r.outputs['Color'], rough - 0.08, rough + 0.12), p.inputs['Roughness'])
    nm = tex('nor_gl', False); nmap = nodes.new('ShaderNodeNormalMap'); nmap.inputs['Strength'].default_value = 0.7
    links.new(nm.outputs['Color'], nmap.inputs['Color']); links.new(nmap.outputs['Normal'], p.inputs['Normal'])
    p.inputs['Coat Weight'].default_value = 0.12; p.inputs['Coat Roughness'].default_value = 0.25
    return m

walnut = walnut_mat('Walnut', (0.19, 0.125, 0.09))
walnut_dark = walnut_mat('Walnut cabinetry', (0.15, 0.1, 0.075), rough=0.5)
black = simple_mat('Blackened steel', (0.012, 0.012, 0.011), rough=0.42, metal=0.5)

def planar_uv(o, axis_u, axis_v, scale=0.9, off=(0.0, 0.0)):
    me = o.data; uv = me.uv_layers.get('UV') or me.uv_layers.new(name='UV')
    for li, loop in enumerate(me.loops):
        co = me.vertices[loop.vertex_index].co
        uv.data[li].uv = (co[axis_u] * scale + off[0], co[axis_v] * scale + off[1])

BX0, BX1, BY0, BY1 = X0 + 0.05, X1 - 0.05, Y0 + 0.035, Y1 - 0.035
BZ0, BZ1 = 0.1, TOP_Z - EDGE
carcass = box('Base', BX0, BX1, BY0 + 0.012, BY1, BZ0, BZ1, walnut, bevel=0.002)
planar_uv(carcass, 2, 1, off=(0.3, 0.1))          # grain runs vertically on the ends
box('Toe kick', BX0 + 0.06, BX1 - 0.06, BY0 + 0.07, BY1 - 0.07, 0.0, BZ0, black)

def fluted_panel(name, x0, x1, y, z0, z1, pitch=0.027, depth=0.01):
    """Reeded front: a row of half-round reeds with small V gaps, one mesh, grain running up the reeds."""
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    n = int((x1 - x0) / pitch); pitch = (x1 - x0) / n
    prof = []
    for k in range(n):
        for j in range(13):
            s = j / 12
            x = x0 + (k + s) * pitch
            d = depth * math.sqrt(max(0.0, 1 - (2 * s - 1) ** 2)) ** 0.9
            prof.append((x, y - d))
    rows = [[bm.verts.new((x, yy, z)) for x, yy in prof] for z in (z0, z1)]
    for k in range(len(prof) - 1):
        bm.faces.new((rows[0][k], rows[0][k + 1], rows[1][k + 1], rows[1][k]))
    bm.to_mesh(me); bm.free()
    for f in me.polygons: f.use_smooth = True
    o = link(bpy.data.objects.new(name, me)); o.data.materials.append(walnut)
    planar_uv(o, 2, 0, off=(0.1, 0.4))             # u follows height: the veneer grain runs up each reed
    return o

fluted_panel('Flutes', BX0, BX1, BY0 + 0.012, BZ0 + 0.004, BZ1 - 0.002)


# ---------- room ----------
plaster, pn, pl = new_mat('Plaster')
pp = principled(pn)
ln = map_range(pn, pl, noise(pn, pl, 2.5, 4), 0.93, 1.04)
pc = pn.new('ShaderNodeCombineColor')
for i, v in enumerate((0.5, 0.465, 0.415)): pl.new(math_node(pn, pl, 'MULTIPLY', ln, v), pc.inputs[i])
pl.new(pc.outputs['Color'], pp.inputs['Base Color'])
pp.inputs['Roughness'].default_value = 0.92
pl.new(bump(pn, pl, noise(pn, pl, 180, 4), 0.08, 0.002), pp.inputs['Normal'])

floor, fn, fl_ = new_mat('Herringbone oak, ebonised')
fp = principled(fn)
ftc = fn.new('ShaderNodeTexCoord'); fmap = fn.new('ShaderNodeMapping')
fmap.inputs['Scale'].default_value = (0.3, 0.3, 0.3); fmap.inputs['Rotation'].default_value = (0, 0, math.radians(90))
fl_.new(ftc.outputs['Object'], fmap.inputs['Vector'])
def ftex(suffix, srgb):
    n = img(fn, os.path.join(A, 'parquet', f'herringbone_parquet_{suffix}_2k.jpg'), srgb)
    fl_.new(fmap.outputs['Vector'], n.inputs['Vector']); return n
fd = ftex('diff', True)
fl_.new(mix(fn, fl_, fd.outputs['Color'], (0.12, 0.085, 0.07), 'MULTIPLY'), fp.inputs['Base Color'])
fr = ftex('rough', False)
fl_.new(map_range(fn, fl_, fr.outputs['Color'], 0.32, 0.6), fp.inputs['Roughness'])
fnm = ftex('nor_gl', False); fnn = fn.new('ShaderNodeNormalMap'); fnn.inputs['Strength'].default_value = 0.8
fl_.new(fnm.outputs['Color'], fnn.inputs['Color']); fl_.new(fnn.outputs['Normal'], fp.inputs['Normal'])

bpy.ops.mesh.primitive_plane_add(size=1, location=(0, -0.4, 0))
fl = bpy.context.active_object; fl.name = 'Floor'; fl.scale = (9.0, 7.4, 1)
bpy.ops.object.transform_apply(scale=True)
fl.data.materials.append(floor)

RX0, RX1, RY0, RY1, RZ = -4.5, 2.3, -4.1, 3.2, 3.05
box('Wall left', RX0 - 0.2, RX0, RY0, RY1, 0, RZ, plaster)
ceil = box('Ceiling', RX0, 2.1, RY0, RY1 + 0.25, RZ, RZ + 0.2, plaster)
ceil.visible_camera = False          # the plan camera sits above ceiling height
# the right side of the room is open glazing (out of shot): the low sun comes in from there
bpy.ops.object.light_add(type='AREA', location=(RX1 + 0.4, -0.45, 1.6), rotation=(0, math.radians(90), 0))
side = bpy.context.active_object; side.name = 'Side glazing portal'
side.data.shape = 'RECTANGLE'; side.data.size = 3.2; side.data.size_y = 7.4; side.data.cycles.is_portal = True
# front wall behind the camera, with a wide window: soft skylight on the island's front
FW = (-3.0, 2.0, 0.35, 2.7)
box('Front wall L', RX0, FW[0], RY0 - 0.25, RY0, 0, RZ, plaster)
box('Front wall R', FW[1], RX1, RY0 - 0.25, RY0, 0, RZ, plaster)
box('Front wall low', FW[0], FW[1], RY0 - 0.25, RY0, 0, FW[2], plaster)
box('Front wall head', FW[0], FW[1], RY0 - 0.25, RY0, FW[3], RZ, plaster)
bpy.ops.object.light_add(type='AREA', location=((FW[0] + FW[1]) / 2, RY0 - 0.4, (FW[2] + FW[3]) / 2), rotation=(math.radians(90), 0, 0))
fp_ = bpy.context.active_object; fp_.name = 'Front window portal'
fp_.data.shape = 'RECTANGLE'; fp_.data.size = FW[1] - FW[0]; fp_.data.size_y = FW[3] - FW[2]; fp_.data.cycles.is_portal = True

def window_bay(name, x0, x1, z0, z1, y, bays, transoms):
    """Steel-framed glazing in the back wall: outer frame, mullions and transoms, no glass (it is blown out)."""
    t, dpt = 0.045, 0.07
    box(f'{name} frame L', x0, x0 + t, y, y + dpt, z0, z1, black)
    box(f'{name} frame R', x1 - t, x1, y, y + dpt, z0, z1, black)
    box(f'{name} frame B', x0, x1, y, y + dpt, z0, z0 + t, black)
    box(f'{name} frame T', x0, x1, y, y + dpt, z1 - t, z1, black)
    for i in range(1, bays):
        x = x0 + i * (x1 - x0) / bays
        box(f'{name} mullion {i}', x - 0.02, x + 0.02, y + 0.01, y + dpt - 0.01, z0, z1, black)
    for z in transoms:
        box(f'{name} transom {z}', x0, x1, y + 0.01, y + dpt - 0.01, z - 0.016, z + 0.016, black)
    bpy.ops.object.light_add(type='AREA', location=((x0 + x1) / 2, y + 0.3, (z0 + z1) / 2), rotation=(math.radians(-90), 0, 0))
    portal = bpy.context.active_object; portal.name = f'{name} portal'
    portal.data.shape = 'RECTANGLE'; portal.data.size = x1 - x0; portal.data.size_y = z1 - z0
    portal.data.cycles.is_portal = True

# back wall: plaster pier with a framed print, two steel window bays, then tall walnut cabinetry
WY = RY1
WA = (-3.1, -1.6); WB = (-0.42, 0.82); WZ0, WZ1 = 0.06, 2.62
box('Back wall far left', RX0, WA[0], WY, WY + 0.25, 0, RZ, plaster)
box('Back wall pier', WA[1], WB[0], WY, WY + 0.25, 0, RZ, plaster)
box('Back wall right', WB[1], RX1, WY, WY + 0.25, 0, RZ, plaster)
for x0_, x1_ in (WA, WB):
    box(f'Back wall low {x0_}', x0_, x1_, WY, WY + 0.25, 0, WZ0, plaster)
    box(f'Back wall head {x0_}', x0_, x1_, WY, WY + 0.25, WZ1, RZ, plaster)
window_bay('Window A', *WA, WZ0, WZ1, WY + 0.06, 2, (1.12, 2.1))
window_bay('Window B', *WB, WZ0, WZ1, WY + 0.06, 2, (2.1,))
box('Print frame', -1.28, -0.72, WY - 0.025, WY, 0.98, 1.72, black, bevel=0.003)
print_mat = simple_mat('Print', (0.46, 0.41, 0.34), rough=0.85)
box('Print', -1.255, -0.745, WY - 0.03, WY - 0.02, 1.005, 1.695, print_mat)
box('Print mount', -1.215, -0.785, WY - 0.032, WY - 0.029, 1.05, 1.65, simple_mat('Print ink', (0.12, 0.10, 0.085), rough=0.9))
# cabinetry run on the right
CX0, CX1 = 0.92, 1.7      # stops short so it never shades the island from the low sun
box('Tall cabinets', CX0, CX1, WY - 0.62, WY, 0.0, 2.55, walnut_dark, bevel=0.002)
planar_uv(bpy.data.objects['Tall cabinets'], 2, 0, scale=0.7)
for i in range(1, 2):
    x = CX0 + i * 0.6
    box(f'Cabinet gap {i}', x - 0.002, x + 0.002, WY - 0.625, WY - 0.6, 0.12, 2.55, black)
box('Counter run', CX0, CX1, WY - 0.66, WY - 0.6, 0.86, 0.9, simple_mat('Counter run', (0.5, 0.47, 0.42), rough=0.3))

# ---------- light: warm low sun through the open side, soft skylight from the room behind the camera ----------
bpy.ops.object.light_add(type='SUN')
sun = bpy.context.active_object; sun.name = 'Sun'
to_sun = Vector((0.80, 0.53, 0.32)).normalized()
sun.rotation_euler = to_sun.to_track_quat('Z', 'Y').to_euler()
sun.data.energy = 6.5
sun.data.angle = math.radians(3.0)
sun.data.color = (1.0, 0.8, 0.58)

bpy.ops.object.light_add(type='AREA', location=(-0.5, RY0 + 0.6, 1.5), rotation=(math.radians(90), 0, 0))
fill = bpy.context.active_object; fill.name = 'Bounce from the room'
fill.data.shape = 'RECTANGLE'; fill.data.size = 4.6; fill.data.size_y = 2.2
fill.data.energy = 110; fill.data.color = (1.0, 0.96, 0.9)
fill.visible_camera = False


# ---------- props ----------
def place(o, x, y, z=TOP_Z, rz=0.0):
    o.location = (x, y, z); o.rotation_euler.z = rz
    return o

# cream glazed stoneware bowl
stone, sn, sl = new_mat('Stoneware cream glaze')
sp = principled(sn)
mott = map_range(sn, sl, noise(sn, sl, 9, 3), 0.95, 1.04)
base = sn.new('ShaderNodeCombineColor')
for i, v in enumerate((0.74, 0.675, 0.565)): sl.new(math_node(sn, sl, 'MULTIPLY', mott, v), base.inputs[i])
fleck = speckle(sn, sl, 420, 0.06)
sl.new(mix(sn, sl, base.outputs['Color'], (0.30, 0.22, 0.15), 'MIX', math_node(sn, sl, 'MULTIPLY', fleck, 0.8)), sp.inputs['Base Color'])
sp.inputs['Roughness'].default_value = 0.34
sp.inputs['Coat Weight'].default_value = 0.35; sp.inputs['Coat Roughness'].default_value = 0.12
sl.new(bump(sn, sl, noise(sn, sl, 70, 2), 0.04, 0.0006), sp.inputs['Normal'])

BOWL = (-0.505, -0.11)
BOWL_PROFILE = [(0, 0.011), (0.045, 0.012), (0.08, 0.022), (0.107, 0.042), (0.124, 0.066), (0.133, 0.09),
                (0.135, 0.101), (0.139, 0.1045), (0.1425, 0.102), (0.1435, 0.097), (0.139, 0.072),
                (0.124, 0.044), (0.1, 0.022), (0.072, 0.009), (0.064, 0.0045), (0.061, 0.0), (0.053, 0.0),
                (0.051, 0.004), (0, 0.005)]
BR, BZ = 0.87, 0.74            # 250 mm across, 77 mm tall
bowl = lathe('Bowl', [(r * BR, z * BZ) for r, z in BOWL_PROFILE], stone, steps=128)
handmade(bowl, 0.003)
place(bowl, *BOWL)

# charcoal stoneware bottle vase
char, cn, cl = new_mat('Stoneware charcoal')
cp = principled(cn)
cm = map_range(cn, cl, noise(cn, cl, 6, 4, 0.6), 0.75, 1.25)
cc = cn.new('ShaderNodeCombineColor')
for i, v in enumerate((0.030, 0.029, 0.028)): cl.new(math_node(cn, cl, 'MULTIPLY', cm, v), cc.inputs[i])
cl.new(mix(cn, cl, cc.outputs['Color'], (0.16, 0.15, 0.14), 'MIX', math_node(cn, cl, 'MULTIPLY', speckle(cn, cl, 300, 0.05), 0.7)), cp.inputs['Base Color'])
cl.new(map_range(cn, cl, noise(cn, cl, 14, 3), 0.55, 0.78), cp.inputs['Roughness'])
cp.inputs['Sheen Weight'].default_value = 0.25; cp.inputs['Sheen Roughness'].default_value = 0.5
cl.new(bump(cn, cl, noise(cn, cl, 240, 4), 0.12, 0.0008), cp.inputs['Normal'])
VASE = (-0.27, -0.025)
VASE_H = 0.252
vase = lathe('Vase', [(0, 0.0), (0.043, 0.0), (0.0485, 0.003), (0.0505, 0.012), (0.051, 0.175), (0.0495, 0.203),
                      (0.044, 0.226), (0.034, 0.244), (0.023, 0.256), (0.0185, 0.266), (0.0175, 0.285),
                      (0.019, 0.295), (0.0175, 0.3), (0.0135, 0.2995), (0.012, 0.29), (0.0115, 0.25), (0, 0.24)],
             char, steps=96)
handmade(vase, 0.0015)
vase.scale.z = VASE_H / 0.30
place(vase, *VASE)

# spun brushed-brass tray: anisotropic, brushed in circles about its centre
brass, bn, bl = new_mat('Brushed brass')
bp = principled(bn)
bp.inputs['Base Color'].default_value = (0.80, 0.585, 0.33, 1); bp.inputs['Metallic'].default_value = 1.0
bl.new(map_range(bn, bl, noise(bn, bl, 30, 3), 0.24, 0.34), bp.inputs['Roughness'])
bp.inputs['Anisotropic'].default_value = 0.75
tan = bn.new('ShaderNodeTangent'); tan.direction_type = 'RADIAL'; tan.axis = 'Z'
bl.new(tan.outputs['Tangent'], bp.inputs['Tangent'])
TRAY = (-0.166, -0.262)
tray = lathe('Tray', [(0, 0.0004), (0.124, 0.0004), (0.128, 0.0016), (0.1325, 0.012), (0.1345, 0.0175),
                      (0.1335, 0.0188), (0.131, 0.0182), (0.1275, 0.006), (0.123, 0.0034), (0, 0.0034)], brass, subsurf=1)
place(tray, *TRAY)

porcelain = simple_mat('Porcelain', (0.84, 0.835, 0.82), rough=0.1, coat=0.6)
def cup(name, x, y, rz):
    z0 = TOP_Z + 0.0034
    saucer = lathe(name + ' saucer', [(0, 0), (0.033, 0), (0.037, 0.003), (0.05, 0.006), (0.061, 0.0115),
                                       (0.0635, 0.0145), (0.062, 0.0155), (0.047, 0.0105), (0.024, 0.0075), (0, 0.0075)], porcelain)
    place(saucer, x, y, z0)
    body = lathe(name, [(0, 0), (0.0185, 0), (0.0205, 0.004), (0.0285, 0.018), (0.0325, 0.038), (0.0335, 0.056),
                        (0.0322, 0.0575), (0.0312, 0.054), (0.0300, 0.038), (0.0262, 0.02), (0.017, 0.0105), (0, 0.0095)], porcelain)
    place(body, x, y, z0 + 0.0075)
    cu = bpy.data.curves.new(name + ' handle', 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth = 0.0034; cu.bevel_resolution = 6
    s = cu.splines.new('BEZIER'); s.bezier_points.add(2)
    for bpnt, co in zip(s.bezier_points, [(0.031, 0, 0.046), (0.051, 0, 0.034), (0.028, 0, 0.016)]):
        bpnt.co = co; bpnt.handle_left_type = bpnt.handle_right_type = 'AUTO'
    h = link(bpy.data.objects.new(name + ' handle', cu)); h.data.materials.append(porcelain)
    h.parent = body
    body.rotation_euler.z = rz
    return body

cup('Cup A', -0.126, -0.2, math.radians(-35))
cup('Cup B', -0.205, -0.305, math.radians(-55))


# ---------- leaves: real leaf scans (ambientCG Leaf001) on modelled leaf outlines ----------
LEAF_DIR = os.path.join(A, 'leaves', 'Leaf001')
def leaf_material(name, value, sat, gloss, back_lift, translucent=0.15):
    m, nodes, links = new_mat(name)
    p = principled(nodes)
    uvn = nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'UV'
    col = img(nodes, os.path.join(LEAF_DIR, 'Leaf001_2K-JPG_Color.jpg'))
    nor = img(nodes, os.path.join(LEAF_DIR, 'Leaf001_2K-JPG_NormalGL.jpg'), srgb=False)
    for n in (col, nor): links.new(uvn.outputs['UV'], n.inputs['Vector'])
    hs = nodes.new('ShaderNodeHueSaturation')
    hs.inputs['Saturation'].default_value = sat; hs.inputs['Value'].default_value = value
    links.new(col.outputs['Color'], hs.inputs['Color'])
    oi = nodes.new('ShaderNodeObjectInfo')
    jit = map_range(nodes, links, oi.outputs['Random'], 0.85, 1.12)
    hsj = nodes.new('ShaderNodeHueSaturation'); links.new(jit, hsj.inputs['Value'])
    links.new(hs.outputs['Color'], hsj.inputs['Color'])
    geo = nodes.new('ShaderNodeNewGeometry')
    front_back = mix(nodes, links, hsj.outputs['Color'], back_lift, 'MIX', geo.outputs['Backfacing'])
    links.new(front_back, p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = gloss[0]
    p.inputs['Coat Weight'].default_value = gloss[1]; p.inputs['Coat Roughness'].default_value = 0.14
    nm = nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = 0.8
    links.new(nor.outputs['Color'], nm.inputs['Color']); links.new(nm.outputs['Normal'], p.inputs['Normal'])
    tr = nodes.new('ShaderNodeBsdfTranslucent')
    links.new(mix(nodes, links, front_back, (0.25, 0.4, 0.05), 'MULTIPLY'), tr.inputs['Color'])
    ms = nodes.new('ShaderNodeMixShader'); ms.inputs['Fac'].default_value = translucent
    outn = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL')
    links.new(p.outputs['BSDF'], ms.inputs[1]); links.new(tr.outputs['BSDF'], ms.inputs[2])
    links.new(ms.outputs['Shader'], outn.inputs['Surface'])
    return m

lemon_leaf_mat = leaf_material('Lemon leaf', 0.42, 1.35, (0.3, 0.55), (0.10, 0.17, 0.035))
olive_leaf_mat = leaf_material('Olive leaf', 0.78, 0.5, (0.44, 0.12), (0.42, 0.43, 0.36), translucent=0.1)

def leaf_mesh(name, L, W, mat, shape=0.85, power=0.8, fold=0.3, curl=0.08, nl=18, nw=5, seed=0):
    """A leaf outline (widest a little below the middle, pointed tip), V-folded along the midrib and curled.
    UVs land inside the scanned leaf, so the real veins and colour variation come with it."""
    r = random.Random(seed)
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UV')
    rows, tuv = [], {}
    twist = r.uniform(-0.25, 0.25)
    for i in range(nl + 1):
        s = i / nl
        hw = max(0.5 * W * math.sin(math.pi * s ** shape) ** power, 1e-5)
        row = []
        for j in range(-nw, nw + 1):
            u = j / nw
            y = u * hw
            z = fold * abs(u) * hw + curl * L * s * s + twist * y * s
            v = bm.verts.new((s * L, y, z))
            tuv[v] = (0.25 + u * (hw / (0.5 * W)) * 0.16, 0.25 + s * 0.62)
            row.append(v)
        rows.append(row)
    for a, b in zip(rows, rows[1:]):
        for k in range(len(a) - 1):
            f = bm.faces.new((a[k], a[k + 1], b[k + 1], b[k]))
            for lp in f.loops: lp[uvl].uv = tuv[lp.vert]
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    # a short petiole
    pet = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.0011, radius2=0.0009, depth=0.012)
    pv = set(pet['verts'])
    for v in pv:
        co = v.co.copy(); v.co = Vector((co.z - 0.006, co.x, co.y))
    for f in bm.faces:
        if all(v in pv for v in f.verts):
            for lp in f.loops: lp[uvl].uv = (0.25, 0.2)
    bm.to_mesh(me); bm.free()
    for f in me.polygons: f.use_smooth = True
    o = link(bpy.data.objects.new(name, me)); o.data.materials.append(mat)
    sol = o.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.0004; sol.offset = 0
    return o

def orient(o, base, direction, up=Vector((0, 0, 1)), roll=0.0):
    d = direction.normalized()
    side = up.cross(d)
    if side.length < 1e-4: side = Vector((0, 1, 0)).cross(d)
    side.normalize(); n = d.cross(side).normalized()
    rot = Matrix((d, side, n)).transposed().to_4x4()
    o.matrix_world = Matrix.Translation(base) @ rot @ Matrix.Rotation(roll, 4, 'X')
    return o


# ---------- lemons: Poly Haven scan, settled into the bowl by a rigid-body drop ----------
lemon_src = import_gltf(os.path.join(A, 'lemon', 'lemon_2k.gltf'))[0]
lemon_src.name = 'Lemon 0'
select_only(lemon_src)
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
lemon_src.select_set(False)
ext = [max(v.co[i] for v in lemon_src.data.vertices) - min(v.co[i] for v in lemon_src.data.vertices) for i in range(3)]
s0 = 0.08 / max(ext)                                     # an 80 mm lemon
lemon_src.scale = (s0, s0, s0)
for slot in lemon_src.material_slots:
    m = slot.material; nodes, links = m.node_tree.nodes, m.node_tree.links; p = principled(nodes)
    if p.inputs['Base Color'].links:
        hs = nodes.new('ShaderNodeHueSaturation')
        hs.inputs['Hue'].default_value = 0.506; hs.inputs['Saturation'].default_value = 1.2
        hs.inputs['Value'].default_value = 2.0
        links.new(p.inputs['Base Color'].links[0].from_socket, hs.inputs['Color'])
        links.new(hs.outputs['Color'], p.inputs['Base Color'])
    # a soft waxy sheen: with a glossy coat every pore caught the window and the peel read as sugared
    if p.inputs['Roughness'].links:
        links.new(map_range(nodes, links, p.inputs['Roughness'].links[0].from_socket, 0.42, 0.7), p.inputs['Roughness'])
    for n in nodes:
        if n.type == 'NORMAL_MAP': n.inputs['Strength'].default_value = 0.45
    p.inputs['Specular IOR Level'].default_value = 0.4
lemons = [lemon_src]
for i in range(1, 8):
    l = lemon_src.copy(); l.name = f'Lemon {i}'; link(l); lemons.append(l)
starts = [(0.0, 0.0, 0.05), (0.06, 0.03, 0.11), (-0.055, 0.045, 0.17), (-0.04, -0.055, 0.23),
          (0.05, -0.05, 0.29), (0.0, 0.06, 0.35), (0.01, -0.01, 0.41), (-0.015, 0.015, 0.47)]
for l, (dx, dy, dz) in zip(lemons, starts):
    l.location = (BOWL[0] + dx, BOWL[1] + dy, TOP_Z + dz)
    l.rotation_euler = Euler((math.radians(rng.uniform(75, 105)), rng.uniform(-0.4, 0.4), rng.uniform(0, 6.28)))

bpy.ops.rigidbody.world_add()
rw = scene.rigidbody_world; rw.point_cache.frame_start = 1; rw.point_cache.frame_end = 180
rw.substeps_per_frame = 30; rw.solver_iterations = 20
def rb(o, kind, shape):
    select_only(o)
    bpy.ops.rigidbody.object_add(); o.rigid_body.type = kind; o.rigid_body.collision_shape = shape
    o.rigid_body.friction = 0.8; o.rigid_body.restitution = 0.05
    o.rigid_body.linear_damping = 0.4; o.rigid_body.angular_damping = 0.6
    o.rigid_body.collision_margin = 0.0005
    o.select_set(False)
rb(bowl, 'PASSIVE', 'MESH')
for l in lemons: rb(l, 'ACTIVE', 'CONVEX_HULL')
bpy.ops.ptcache.bake_all(bake=True)
scene.frame_set(180)
settled = {l.name: l.matrix_world.copy() for l in lemons}
bpy.ops.ptcache.free_bake_all()
for l in lemons:
    select_only(l); bpy.ops.rigidbody.object_remove(); l.matrix_world = settled[l.name]; l.select_set(False)
select_only(bowl); bpy.ops.rigidbody.object_remove(); bowl.select_set(False)
bpy.ops.rigidbody.world_remove()
scene.frame_set(1)
for l in lemons:   # every lemon must end up resting in the bowl
    d = (Vector(l.location[:2]) - Vector(BOWL)).length
    assert d < 0.13 and TOP_Z < l.location.z < TOP_Z + 0.22, (l.name, tuple(l.location))

# three glossy lemon leaves on a short twig, tucked in on the bowl's left and reaching out over the rim
dg = bpy.context.evaluated_depsgraph_get()
def rest_z(x, y):
    zs = []
    for dx, dy in ((0, 0), (0.012, 0), (-0.012, 0), (0, 0.012), (0, -0.012)):
        hit, loc, *_ = scene.ray_cast(dg, Vector((x + dx, y + dy, TOP_Z + 0.6)), Vector((0, 0, -1)))
        if hit: zs.append(loc.z)
    return max(zs) if zs else TOP_Z + 0.08
RIM_Z, RIM_R = TOP_Z + 0.105 * BZ, 0.143 * BR
bases = []
for i, (ang, reach, L) in enumerate([(184, 0.06, 0.112), (212, 0.058, 0.104), (238, 0.054, 0.096)]):
    a = math.radians(ang)
    dxy = Vector((math.cos(a), math.sin(a)))
    bx, by = BOWL[0] + dxy.x * reach, BOWL[1] + dxy.y * reach
    bz = rest_z(bx, by) + 0.004
    run = RIM_R - reach                              # horizontal distance to the rim
    tilt = max(math.atan2(RIM_Z + 0.006 - bz, run), math.radians(-14))
    lf = leaf_mesh(f'Lemon leaf {i}', L, L * 0.42, lemon_leaf_mat, fold=0.32, curl=-0.07, seed=10 + i)
    orient(lf, Vector((bx, by, bz)), Vector((dxy.x * math.cos(tilt), dxy.y * math.cos(tilt), math.sin(tilt))),
           roll=rng.uniform(-0.3, 0.3))
    bases.append(Vector((bx, by, bz)) - Vector((dxy.x, dxy.y, 0)) * 0.012)
twig = bpy.data.curves.new('Lemon twig', 'CURVE'); twig.dimensions = '3D'; twig.bevel_depth = 0.0016; twig.bevel_resolution = 3
sp_ = twig.splines.new('POLY')
inner = Vector((BOWL[0] - 0.03, BOWL[1] - 0.035, rest_z(BOWL[0] - 0.03, BOWL[1] - 0.035) - 0.004))
pts = [inner, bases[1], bases[0]]
sp_.points.add(len(pts) - 1)
for pnt, co in zip(sp_.points, pts): pnt.co = (*co, 1)
tw = link(bpy.data.objects.new('Lemon twig', twig)); tw.data.materials.append(simple_mat('Green stem', (0.07, 0.11, 0.03), rough=0.5))
print('LEMON_LEAF_BASES', [tuple(round(c, 3) for c in b) for b in bases])


# ---------- olive branch in the vase ----------
stem_mat = simple_mat('Olive wood', (0.10, 0.095, 0.075), rough=0.7)
def bez(p0, p1, p2, p3, t):
    u = 1 - t
    return p0 * u ** 3 + p1 * 3 * u * u * t + p2 * 3 * u * t * t + p3 * t ** 3

def twig_curve(name, ctrl, r0, r1, n=36):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 1.0; cu.bevel_resolution = 3
    sp = cu.splines.new('POLY'); sp.points.add(n - 1)
    pts = [bez(*ctrl, k / (n - 1)) for k in range(n)]
    for k, (pnt, co) in enumerate(zip(sp.points, pts)):
        pnt.co = (*co, 1); pnt.radius = r0 + (r1 - r0) * k / (n - 1)
    o = link(bpy.data.objects.new(name, cu)); o.data.materials.append(stem_mat)
    return pts

mouth = Vector((VASE[0], VASE[1], TOP_Z + VASE_H))
TWIGS = [  # control points relative to the vase mouth; they lean back and to the right, toward the light
    [(0, 0, -0.06), (0.014, 0.005, 0.06), (0.09, 0.045, 0.125), (0.2, 0.095, 0.155)],
    [(0, 0, -0.06), (-0.005, 0.009, 0.065), (-0.03, 0.035, 0.145), (-0.09, 0.055, 0.2)],
    [(0, 0, -0.06), (0.012, -0.007, 0.045), (0.1, -0.025, 0.08), (0.225, -0.035, 0.085)],
    [(0, 0, -0.06), (0.007, 0.012, 0.05), (0.06, 0.085, 0.115), (0.1, 0.17, 0.145)],
    [(0, 0, -0.06), (-0.006, -0.004, 0.06), (-0.05, -0.03, 0.1), (-0.12, -0.05, 0.11)],
]
leaf_n = 0
def olive_leaf(p, ld, scale=1.0):
    global leaf_n
    leaf_n += 1
    L = rng.uniform(0.056, 0.08) * scale
    o = leaf_mesh(f'Olive leaf {leaf_n}', L, L * rng.uniform(0.19, 0.25), olive_leaf_mat,
                  shape=0.95, power=0.6, fold=0.2, curl=rng.uniform(-0.14, 0.06), nl=14, nw=3, seed=100 + leaf_n)
    orient(o, p, ld.normalized(), roll=rng.uniform(-0.7, 0.7))
for ti, ctrl in enumerate(TWIGS):
    cv = [mouth + Vector(c) for c in ctrl]
    pts = twig_curve(f'Olive twig {ti}', cv, 0.0021, 0.0007)
    n = len(pts)
    k, node = int(n * 0.4) + ti, rng.randint(0, 1)
    while k < n - 2:
        p = pts[k]; d = (pts[k + 1] - pts[k - 1]).normalized()
        a0 = d.cross(Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))).normalized()
        b0 = d.cross(a0).normalized()
        phi = node * math.pi / 2 + rng.uniform(-0.4, 0.4)
        axis = a0 * math.cos(phi) + b0 * math.sin(phi)
        for side in (-1, 1):
            spread = math.radians(rng.uniform(26, 50))
            ld = d * math.cos(spread) + axis * side * math.sin(spread)
            ld.z -= rng.uniform(0.05, 0.32)         # leaves droop a little under their own weight
            olive_leaf(p, ld, 0.85 if k > n - 8 else 1.0)
        node += 1
        k += rng.choice((3, 4, 5))
    tip = pts[-1]; d = (pts[-1] - pts[-3]).normalized()
    olive_leaf(tip, d + Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 0.1)), 0.7)
print('OLIVE_LEAVES', leaf_n)


# ---------- linen napkin, folded and draped over the front edge (cloth sim) ----------
linen, nn, nl_ = new_mat('Linen, oatmeal')
np_ = principled(nn)
nuv = nn.new('ShaderNodeUVMap'); nuv.uv_map = 'UVMap'
nmp = nn.new('ShaderNodeMapping'); nmp.inputs['Scale'].default_value = (0.85, 2.5, 1)
nl_.new(nuv.outputs['UV'], nmp.inputs['Vector'])
def ntex(suffix, srgb):
    n = img(nn, os.path.join(A, 'linen', f'rough_linen_{suffix}_2k.jpg'), srgb)
    nl_.new(nmp.outputs['Vector'], n.inputs['Vector']); return n
nd = ntex('diff', True)
bw = nn.new('ShaderNodeRGBToBW'); nl_.new(nd.outputs['Color'], bw.inputs['Color'])   # the scan is dyed blue: keep its weave, not its colour
lum = map_range(nn, nl_, bw.outputs['Val'], 0.62, 1.3, 0.3, 0.6)
lc = nn.new('ShaderNodeCombineColor')
for i, v in enumerate((0.5, 0.44, 0.355)): nl_.new(math_node(nn, nl_, 'MULTIPLY', lum, v), lc.inputs[i])
nl_.new(lc.outputs['Color'], np_.inputs['Base Color'])
np_.inputs['Roughness'].default_value = 0.88
np_.inputs['Sheen Weight'].default_value = 0.7; np_.inputs['Sheen Roughness'].default_value = 0.45
nnor = ntex('nor_gl', False); nnm = nn.new('ShaderNodeNormalMap'); nnm.inputs['Strength'].default_value = 0.9
nl_.new(nnor.outputs['Color'], nnm.inputs['Color'])
crinkle = noise(nn, nl_, 60, 6, 0.62)                # washed linen: fine creases on top of the weave
nl_.new(bump(nn, nl_, crinkle, 0.5, 0.0012, nnm.outputs['Normal']), np_.inputs['Normal'])

NAP_W, NAP_L, NAP_OVER = 0.19, 0.48, 0.24
NAP_X, NAP_ANG = 0.1, math.radians(10)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=34, y_subdivisions=88, size=1)
nap = bpy.context.active_object; nap.name = 'Napkin'
nap.scale = (NAP_W, NAP_L, 1); bpy.ops.object.transform_apply(scale=True)
# The rest shape is rumpled: the cloth is longer than the flat footprint it falls onto, so it buckles
# into soft creases the way washed linen does. The back end, where it is held, starts flat.
for v in nap.data.vertices:
    x, y = v.co.x, v.co.y
    fade = min(1.0, max(0.0, (NAP_L / 2 - 0.05 - y) / 0.1))
    q = Vector((x * 21, y * 21, 0.37))
    amp = 0.0055 + 0.0035 * mnoise.noise(Vector((1.3, y * 9, 0.2)))
    pleat = amp * math.sin(2 * math.pi * x / 0.07 + 1.2 * mnoise.noise(Vector((0.4, y * 7, 2.1))))
    v.co.z = fade * (pleat + 0.0035 * mnoise.noise(q) + 0.002 * mnoise.noise(q * 2.6 + Vector((5, 1, 0))))
    v.co.x += 0.006 * mnoise.noise(q * 0.45 + Vector((9, 2, 4)))   # hand-folded edges are never straight
    end = min(1.0, (NAP_L / 2 - abs(y)) / 0.03)                       # round the corners off
    v.co.x *= 1 - 0.12 * (1 - end) ** 2
pin = nap.vertex_groups.new(name='pin')
pin.add([v.index for v in nap.data.vertices if v.co.y > NAP_L / 2 - 0.04], 1.0, 'REPLACE')
nap.rotation_euler.z = NAP_ANG
nap.location = (NAP_X, Y0 - NAP_OVER + NAP_L / 2, TOP_Z + 0.004)
col = top.modifiers.new('collision', 'COLLISION')
top.collision.thickness_outer = 0.0018; top.collision.cloth_friction = 12; top.collision.damping = 0.6
cl_ = nap.modifiers.new('cloth', 'CLOTH')
cs = cl_.settings
cs.quality = 12; cs.mass = 0.12; cs.air_damping = 2.0
cs.tension_stiffness = 25; cs.compression_stiffness = 25; cs.shear_stiffness = 12; cs.bending_stiffness = 1.2
cs.bending_model = 'ANGULAR'
cs.vertex_group_mass = 'pin'
cl_.collision_settings.use_self_collision = True
cl_.collision_settings.distance_min = 0.0018; cl_.collision_settings.self_distance_min = 0.0015
cl_.point_cache.frame_start = 1; cl_.point_cache.frame_end = 150
for f in range(1, 151): scene.frame_set(f)
dg = bpy.context.evaluated_depsgraph_get()
nap_eval = nap.evaluated_get(dg)
draped = bpy.data.meshes.new_from_object(nap_eval)
nap.modifiers.clear(); old = nap.data; nap.data = draped; bpy.data.meshes.remove(old)
nap.vertex_groups.clear()
top.modifiers.remove(top.modifiers['collision'])
scene.frame_set(1)
nap.data.materials.clear(); nap.data.materials.append(linen)
for f in nap.data.polygons: f.use_smooth = True
sub = nap.modifiers.new('sub', 'SUBSURF'); sub.levels = sub.render_levels = 2
for nm_, basis, size, amt in (('rumple', 'IMPROVED_PERLIN', 0.045, 0.0018),):
    t = bpy.data.textures.new('Napkin ' + nm_, 'CLOUDS'); t.noise_basis = basis; t.noise_scale = size; t.noise_depth = 1
    dm = nap.modifiers.new(nm_, 'DISPLACE'); dm.texture = t; dm.strength = amt; dm.mid_level = 0.0
    dm.texture_coords = 'OBJECT'
sol = nap.modifiers.new('folded thickness', 'SOLIDIFY'); sol.thickness = 0.0032; sol.offset = 1.0
soft = nap.modifiers.new('soft edges', 'SUBSURF'); soft.levels = soft.render_levels = 1
zs = [(nap.matrix_world @ v.co).z for v in nap.data.vertices]
print('NAPKIN_Z', round(min(zs), 3), round(max(zs), 3))
assert min(zs) < TOP_Z - 0.12, 'napkin did not drape over the edge'
assert max(zs) < TOP_Z + 0.03, 'napkin is floating'

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SRC, 'scene.blend'))
print('SCENE_OK', len(scene.objects), 'objects')
