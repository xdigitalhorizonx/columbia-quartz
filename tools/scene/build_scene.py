# Builds the Columbia Quartz hero scene in Blender (Cycles) and saves scene.blend in the source folder.
#   blender -b --factory-startup --python tools/scene/build_scene.py -- --src C:/dev/columbia-quartz-source/3d
# <src> holds assets/ (CC0 scans and textures, see README) and tex/ (Columbia's slab photos, upscaled 4x).
# Units are metres, Z up. The island runs along X; its front edge (-Y) faces the camera at the end of the
# first move. The sink run in Calacatta LX Noir lines the left wall (-X), facing the island across the aisle.
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

def seat(o, z, sink=0.0002):
    """Rest an object on the surface at height z. Wobble and subdivision move its lowest point, and even a
    half-millimetre gap lets light in underneath and kills the contact shadow."""
    bpy.context.view_layer.update()
    ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    zmin = min((ev.matrix_world @ v.co).z for v in ev.data.vertices)
    o.location.z += z - zmin - sink
    bpy.context.view_layer.update()
    return o

def fmix(nodes, links, a, b, fac):
    n = nodes.new('ShaderNodeMix'); n.data_type = 'FLOAT'
    for s, v in ((inp(n, 'A_Float'), a), (inp(n, 'B_Float'), b), (inp(n, 'Factor_Float'), fac)):
        if isinstance(v, (int, float)): s.default_value = v
        else: links.new(v, s)
    return out(n, 'Result_Float')

def obj_axis(nodes, links, axis='Z'):
    tc = nodes.new('ShaderNodeTexCoord'); sep = nodes.new('ShaderNodeSeparateXYZ')
    links.new(tc.outputs['Object'], sep.inputs[0])
    return sep.outputs[axis]

def band(nodes, links, v, lo, hi):
    """0 below lo, 1 above hi, smooth in between."""
    n = nodes.new('ShaderNodeMapRange'); n.interpolation_type = 'SMOOTHSTEP'
    n.inputs['From Min'].default_value = lo; n.inputs['From Max'].default_value = hi
    links.new(v, n.inputs['Value'])
    return n.outputs['Result']

def throw_rings(nodes, links, pitch, distortion=2.5):
    """Throwing rings: the faint ridges a potter's fingers leave, one every `pitch` metres of height."""
    w = nodes.new('ShaderNodeTexWave'); w.wave_type = 'BANDS'; w.bands_direction = 'Z'
    w.inputs['Scale'].default_value = 0.3142 / pitch
    w.inputs['Distortion'].default_value = distortion; w.inputs['Detail'].default_value = 1.5
    tc = nodes.new('ShaderNodeTexCoord'); links.new(tc.outputs['Object'], w.inputs['Vector'])
    return w.outputs['Fac']

def spun_lines(nodes, links, scale):
    """Spun-metal brushing: fine concentric lines, as 1D noise of the distance from the object's Z axis."""
    tc = nodes.new('ShaderNodeTexCoord'); sep = nodes.new('ShaderNodeSeparateXYZ')
    links.new(tc.outputs['Object'], sep.inputs[0])
    xy = nodes.new('ShaderNodeCombineXYZ')
    links.new(sep.outputs['X'], xy.inputs['X']); links.new(sep.outputs['Y'], xy.inputs['Y'])
    r = nodes.new('ShaderNodeVectorMath'); r.operation = 'LENGTH'; links.new(xy.outputs[0], r.inputs[0])
    n = nodes.new('ShaderNodeTexNoise'); n.noise_dimensions = '1D'
    n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = 3.0
    links.new(r.outputs['Value'], n.inputs['W'])
    return n.outputs['Fac']

IMP = os.path.join(A, 'imperf')
def imperf(nodes, links, asset, kind, tile, box=False, rot=0.0, off=(0.0, 0.0, 0.0)):
    """A scanned imperfection mask (ambientCG fingerprints, smears, scratches) at `tile` metres per repeat,
    projected in object space: flat from above, or boxed for objects that curve."""
    n = img(nodes, os.path.join(IMP, asset, f'{asset}_2K-JPG_{kind}.jpg'), srgb=False)
    tc = nodes.new('ShaderNodeTexCoord'); mp = nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (1 / tile,) * 3
    mp.inputs['Rotation'].default_value = (0, 0, rot); mp.inputs['Location'].default_value = off
    links.new(tc.outputs['Object'], mp.inputs['Vector']); links.new(mp.outputs['Vector'], n.inputs['Vector'])
    if box: n.projection = 'BOX'; n.projection_blend = 0.3
    return out(n, 'Color')

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


# ---------- quartz: Columbia's real slab photos (Calacatta LX Gold island, LX Noir perimeter) ----------
def quartz_mat(name, path, deep=0.75, lift=(1.13, 1.12, 1.1), sat=1.25):
    slab = bpy.data.images.load(path)
    m, qn, ql = new_mat(name)
    qp = principled(qn)
    qt = qn.new('ShaderNodeTexImage'); qt.image = slab; qt.interpolation = 'Cubic'; qt.extension = 'MIRROR'
    quv = qn.new('ShaderNodeUVMap'); quv.uv_map = 'UV'; ql.new(quv.outputs['UV'], qt.inputs['Vector'])
    grain = map_range(qn, ql, noise(qn, ql, 2400, 2), 0.975, 1.0)        # resin-bound grain, below the vein scale
    cloud = map_range(qn, ql, noise(qn, ql, 3.0, 3), 0.985, 1.01)         # faint cloudiness of the batch
    g = qn.new('ShaderNodeCombineColor')
    gm = math_node(qn, ql, 'MULTIPLY', grain, cloud)
    for i in range(3): ql.new(gm, g.inputs[i])
    dp = mix(qn, ql, qt.outputs['Color'], qt.outputs['Color'], 'MULTIPLY', deep)
    lf = mix(qn, ql, dp, lift, 'MULTIPLY')
    qhs = qn.new('ShaderNodeHueSaturation'); qhs.inputs['Saturation'].default_value = sat
    ql.new(lf, qhs.inputs['Color'])
    ql.new(mix(qn, ql, qhs.outputs['Color'], g.outputs['Color'], 'MULTIPLY'), qp.inputs['Base Color'])
    wipe = noise(qn, ql, 1.6, 6, 0.62)                                    # polish is never perfectly even
    smear = imperf(qn, ql, 'SurfaceImperfections003', 'Opacity', 0.9)   # wipe marks, seen only in reflections
    rough = map_range(qn, ql, wipe, 0.035, 0.11, 0.35, 0.75)
    ql.new(math_node(qn, ql, 'ADD', rough, math_node(qn, ql, 'MULTIPLY', smear, 0.06)), qp.inputs['Roughness'])
    qp.inputs['IOR'].default_value = 1.54
    qp.inputs['Specular IOR Level'].default_value = 0.55
    peel = noise(qn, ql, 55, 2)                                           # the faint orange peel of a polished face
    bev = qn.new('ShaderNodeBevel'); bev.inputs['Radius'].default_value = 0.0015; bev.samples = 6
    ql.new(bump(qn, ql, peel, 0.025, 0.0004, bev.outputs['Normal']), qp.inputs['Normal'])
    return m, slab

quartz, slab_img = quartz_mat('Quartz LX Gold', os.path.join(TEX, 'slab-lx-gold-tex.png'))
SLAB_H = SLAB_W * slab_img.size[1] / slab_img.size[0]

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

RX0, RX1, RY0, RY1, RZ = -3.25, 2.3, -4.1, 3.2, 3.05
SINK = (RX0 + 0.335, -0.35)          # sink basin centre, in the run along the left wall
# left wall, with a steel-framed window over the sink (its sill is the backsplash ledge, see the sink run)
WIN_Y, WIN_Z = (SINK[1] - 0.62, SINK[1] + 0.62), (TOP_Z + 0.62, 2.66)
box('Wall left low', RX0 - 0.2, RX0, RY0, RY1, 0, WIN_Z[0], plaster)
box('Wall left head', RX0 - 0.2, RX0, RY0, RY1, WIN_Z[1], RZ, plaster)
box('Wall left front', RX0 - 0.2, RX0, RY0, WIN_Y[0], WIN_Z[0], WIN_Z[1], plaster)
box('Wall left back', RX0 - 0.2, RX0, WIN_Y[1], RY1, WIN_Z[0], WIN_Z[1], plaster)
ceil = box('Ceiling', RX0, RX1 + 0.07, RY0, RY1 + 0.25, RZ, RZ + 0.2, plaster)
ceil.visible_camera = False          # the plan camera sits above ceiling height; render_move.py shows it later
# the right side of the room is open glazing (out of shot): the low sun comes in from there
bpy.ops.object.light_add(type='AREA', location=(RX1 + 0.4, -0.45, 1.6), rotation=(0, math.radians(90), 0))
side = bpy.context.active_object; side.name = 'Side glazing portal'
side.data.shape = 'RECTANGLE'; side.data.size = 3.2; side.data.size_y = 7.4; side.data.cycles.is_portal = True
# its steel frame: a mullion stands only where its shadow misses the island's top and front edge in the
# first move (the low sun comes through here), so the last bay is a wide lift-and-slide panel
for y in (-2.6, -1.05, 0.5, 2.95):
    box(f'Side glazing mullion {y}', RX1, RX1 + 0.07, y - 0.025, y + 0.025, 0.0, RZ, black)
box('Side glazing sill', RX1, RX1 + 0.07, RY0, RY1, 0.0, 0.05, black)
box('Side glazing head', RX1, RX1 + 0.07, RY0, RY1, RZ - 0.06, RZ, black)
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

# ---------- light: warm low sun through the open side, soft skylight from the room behind the camera ----------
bpy.ops.object.light_add(type='SUN')
sun = bpy.context.active_object; sun.name = 'Sun'
to_sun = Vector((0.80, 0.53, 0.32)).normalized()
sun.rotation_euler = to_sun.to_track_quat('Z', 'Y').to_euler()
sun.data.energy = 6.5
sun.data.angle = math.radians(0.8)       # real sun is 0.53 deg: crisp at the contact, softening with distance
sun.data.color = (1.0, 0.8, 0.58)

bpy.ops.object.light_add(type='AREA', location=(-0.5, RY0 + 0.6, 1.5), rotation=(math.radians(90), 0, 0))
fill = bpy.context.active_object; fill.name = 'Bounce from the room'
fill.data.shape = 'RECTANGLE'; fill.data.size = 4.6; fill.data.size_y = 2.2
fill.data.energy = 70; fill.data.color = (1.0, 0.96, 0.9)   # enough to read the shade side, not to flatten it
fill.visible_camera = False


# ---------- props ----------
def place(o, x, y, z=TOP_Z, rz=0.0):
    o.location = (x, y, z); o.rotation_euler.z = rz
    return o

def stoneware(name, glaze, raw, rim_z, foot_z, rough=(0.28, 0.46), speck=0.085, coat=0.1, ring_pitch=0.0055):
    """Wheel-thrown glazed stoneware, the way it feels in the hand: a satin glaze with iron specks and
    pinholes over faint throwing rings, breaking to toasted clay where it runs thin over the rim, and an
    unglazed, gritty foot. Heights are in the object's own space (its base at z = 0)."""
    m, n, l = new_mat(name)
    p = principled(n)
    z = obj_axis(n, l, 'Z')
    mott = map_range(n, l, noise(n, l, 9, 3), 0.91, 1.05)
    base = n.new('ShaderNodeCombineColor')
    for i, v in enumerate(glaze): l.new(math_node(n, l, 'MULTIPLY', mott, v), base.inputs[i])
    thin = math_node(n, l, 'MULTIPLY', band(n, l, z, rim_z - 0.011, rim_z - 0.002), map_range(n, l, noise(n, l, 40, 3), 0.45, 1.0))
    col = mix(n, l, base.outputs['Color'], tuple(c * 0.92 for c in raw), 'MIX', thin)
    fleck = speckle(n, l, 420, speck)
    col = mix(n, l, col, (0.30, 0.22, 0.15), 'MIX', math_node(n, l, 'MULTIPLY', fleck, 0.8))
    pin = speckle(n, l, 900, 0.025)                                      # pinholes where gas escaped the glaze
    foot = math_node(n, l, 'SUBTRACT', 1.0, band(n, l, z, foot_z, foot_z + 0.0012))
    grit = map_range(n, l, noise(n, l, 700, 2), 0.82, 1.08)
    rc = n.new('ShaderNodeCombineColor')
    for i, v in enumerate(raw): l.new(math_node(n, l, 'MULTIPLY', grit, v), rc.inputs[i])
    l.new(mix(n, l, col, rc.outputs['Color'], 'MIX', foot), p.inputs['Base Color'])
    gr = map_range(n, l, noise(n, l, 5, 3), *rough)
    gr = math_node(n, l, 'ADD', gr, math_node(n, l, 'MULTIPLY', thin, 0.15))
    l.new(fmix(n, l, gr, 0.9, foot), p.inputs['Roughness'])
    h = math_node(n, l, 'MULTIPLY', throw_rings(n, l, ring_pitch, 4.0), 1.0)
    h = math_node(n, l, 'ADD', h, math_node(n, l, 'MULTIPLY', noise(n, l, 160, 3), 0.35))    # orange peel
    h = math_node(n, l, 'ADD', h, math_node(n, l, 'MULTIPLY', fleck, 0.5))
    h = math_node(n, l, 'SUBTRACT', h, math_node(n, l, 'MULTIPLY', pin, 0.8))
    h = math_node(n, l, 'ADD', h, math_node(n, l, 'MULTIPLY', foot, math_node(n, l, 'MULTIPLY', grit, 1.5)))
    l.new(bump(n, l, h, 0.3, 0.0004), p.inputs['Normal'])
    p.inputs['Coat Weight'].default_value = coat; p.inputs['Coat Roughness'].default_value = 0.2
    return m

# cream glazed stoneware bowl
BOWL = (-0.505, -0.11)
BOWL_PROFILE = [(0, 0.011), (0.045, 0.012), (0.08, 0.022), (0.107, 0.042), (0.124, 0.066), (0.133, 0.09),
                (0.135, 0.101), (0.139, 0.1045), (0.1425, 0.102), (0.1435, 0.097), (0.139, 0.072),
                (0.124, 0.044), (0.1, 0.022), (0.072, 0.009), (0.064, 0.0045), (0.061, 0.0), (0.053, 0.0),
                (0.051, 0.004), (0, 0.005)]
BR, BZ = 0.87, 0.74            # 250 mm across, 77 mm tall
stone = stoneware('Stoneware cream glaze', (0.74, 0.675, 0.565), (0.56, 0.44, 0.32), 0.1045 * BZ, 0.0045 * BZ)
bowl = lathe('Bowl', [(r * BR, z * BZ) for r, z in BOWL_PROFILE], stone, steps=128)
handmade(bowl, 0.003)
place(bowl, *BOWL)
seat(bowl, TOP_Z)

# charcoal stoneware bottle vase: a dry, gritty matte glaze
char, cn, cl = new_mat('Stoneware charcoal')
cp = principled(cn)
cz = obj_axis(cn, cl, 'Z')
cm = map_range(cn, cl, noise(cn, cl, 6, 4, 0.6), 0.75, 1.25)
cc = cn.new('ShaderNodeCombineColor')
for i, v in enumerate((0.030, 0.029, 0.028)): cl.new(math_node(cn, cl, 'MULTIPLY', cm, v), cc.inputs[i])
grog = speckle(cn, cl, 300, 0.05)
cfoot = math_node(cn, cl, 'SUBTRACT', 1.0, band(cn, cl, cz, 0.004, 0.0055))
ccol = mix(cn, cl, cc.outputs['Color'], (0.16, 0.15, 0.14), 'MIX', math_node(cn, cl, 'MULTIPLY', grog, 0.7))
cl.new(mix(cn, cl, ccol, (0.2, 0.17, 0.14), 'MIX', cfoot), cp.inputs['Base Color'])
cl.new(fmix(cn, cl, map_range(cn, cl, noise(cn, cl, 14, 3), 0.55, 0.8), 0.92, cfoot), cp.inputs['Roughness'])
cp.inputs['Sheen Weight'].default_value = 0.25; cp.inputs['Sheen Roughness'].default_value = 0.5
ch = math_node(cn, cl, 'MULTIPLY', throw_rings(cn, cl, 0.007, 6.0), 0.35)
ch = math_node(cn, cl, 'ADD', ch, noise(cn, cl, 240, 4))
ch = math_node(cn, cl, 'ADD', ch, math_node(cn, cl, 'MULTIPLY', grog, 0.8))
cl.new(bump(cn, cl, ch, 0.2, 0.0008), cp.inputs['Normal'])
VASE = (-0.27, -0.025)
VASE_H = 0.252
vase = lathe('Vase', [(0, 0.0), (0.043, 0.0), (0.0485, 0.003), (0.0505, 0.012), (0.051, 0.175), (0.0495, 0.203),
                      (0.044, 0.226), (0.034, 0.244), (0.023, 0.256), (0.0185, 0.266), (0.0175, 0.285),
                      (0.019, 0.295), (0.0175, 0.3), (0.0135, 0.2995), (0.012, 0.29), (0.0115, 0.25), (0, 0.24)],
             char, steps=96)
handmade(vase, 0.0015)
vase.scale.z = VASE_H / 0.30
place(vase, *VASE)
seat(vase, TOP_Z)

def brass_mat(name, spun):
    """Brushed brass that has been handled: fine brushing (in circles if spun), fingerprints that dull the
    sheen, a few hairline scratches and slightly uneven tone."""
    m, n, l = new_mat(name)
    p = principled(n)
    prints = imperf(n, l, 'Fingerprints002', 'Opacity', 0.2, box=not spun, rot=0.7)
    scratch = imperf(n, l, 'Scratches005', 'Opacity', 0.35, box=not spun, off=(0.3, 0.1, 0))
    tone = map_range(n, l, noise(n, l, 6, 3), 0.92, 1.04)
    bc = n.new('ShaderNodeCombineColor')
    for i, v in enumerate((0.80, 0.585, 0.33)): l.new(math_node(n, l, 'MULTIPLY', tone, v), bc.inputs[i])
    l.new(mix(n, l, bc.outputs['Color'], (0.62, 0.47, 0.29), 'MIX', math_node(n, l, 'MULTIPLY', prints, 0.35)), p.inputs['Base Color'])
    p.inputs['Metallic'].default_value = 1.0
    if spun:
        lines = spun_lines(n, l, 2600)
        tan = n.new('ShaderNodeTangent'); tan.direction_type = 'RADIAL'; tan.axis = 'Z'
        l.new(tan.outputs['Tangent'], p.inputs['Tangent'])
        l.new(map_range(n, l, prints, 0.75, 0.25), p.inputs['Anisotropic'])     # oil from a thumb hides the brushing
    else:
        lines = noise(n, l, 1400, 3)
    r = map_range(n, l, noise(n, l, 30, 3), 0.24, 0.32)
    r = math_node(n, l, 'ADD', r, math_node(n, l, 'MULTIPLY', lines, 0.06))
    r = math_node(n, l, 'ADD', r, math_node(n, l, 'MULTIPLY', prints, 0.25))
    r = math_node(n, l, 'ADD', r, math_node(n, l, 'MULTIPLY', scratch, 0.12))
    l.new(r, p.inputs['Roughness'])
    h = math_node(n, l, 'ADD', math_node(n, l, 'MULTIPLY', lines, 0.6), math_node(n, l, 'MULTIPLY', scratch, -0.8))
    l.new(bump(n, l, h, 0.12, 0.0002), p.inputs['Normal'])
    return m

# spun brushed-brass tray: anisotropic, brushed in circles about its centre
brass = brass_mat('Brushed brass, spun', spun=True)
TRAY = (-0.166, -0.262)
tray = lathe('Tray', [(0, 0.0), (0.124, 0.0), (0.128, 0.0012), (0.1325, 0.012), (0.1345, 0.0175),
                      (0.1335, 0.0188), (0.131, 0.0182), (0.1275, 0.006), (0.123, 0.003), (0, 0.003)], brass, subsurf=1)
place(tray, *TRAY)
seat(tray, TOP_Z)
TRAY_TOP = TOP_Z + 0.0028

# porcelain: glossy glaze with a faint orange peel, over an unglazed foot ring
porcelain, pn_, pl_ = new_mat('Porcelain')
pp_ = principled(pn_)
pz = obj_axis(pn_, pl_, 'Z')
pfoot = math_node(pn_, pl_, 'SUBTRACT', 1.0, band(pn_, pl_, pz, 0.0012, 0.0024))
pl_.new(mix(pn_, pl_, (0.84, 0.835, 0.82), (0.74, 0.72, 0.68), 'MIX', pfoot), pp_.inputs['Base Color'])
psm = imperf(pn_, pl_, 'SurfaceImperfections003', 'Opacity', 0.25, box=True)
pr = math_node(pn_, pl_, 'ADD', map_range(pn_, pl_, noise(pn_, pl_, 20, 2), 0.06, 0.11), math_node(pn_, pl_, 'MULTIPLY', psm, 0.08))
pl_.new(fmix(pn_, pl_, pr, 0.6, pfoot), pp_.inputs['Roughness'])
pp_.inputs['Coat Weight'].default_value = 0.6; pp_.inputs['Coat Roughness'].default_value = 0.04
ph = math_node(pn_, pl_, 'ADD', noise(pn_, pl_, 420, 3), math_node(pn_, pl_, 'MULTIPLY', pfoot, noise(pn_, pl_, 1500, 2)))
pl_.new(bump(pn_, pl_, ph, 0.025, 0.0002), pp_.inputs['Normal'])

def cup(name, x, y, rz):
    saucer = lathe(name + ' saucer', [(0, 0), (0.033, 0), (0.037, 0.003), (0.05, 0.006), (0.061, 0.0115),
                                       (0.0635, 0.0145), (0.062, 0.0155), (0.047, 0.0105), (0.024, 0.0075), (0, 0.0075)], porcelain)
    place(saucer, x, y, TRAY_TOP)
    seat(saucer, TRAY_TOP)
    body = lathe(name, [(0, 0), (0.0185, 0), (0.0205, 0.004), (0.0285, 0.018), (0.0325, 0.038), (0.0335, 0.056),
                        (0.0322, 0.0575), (0.0312, 0.054), (0.0300, 0.038), (0.0262, 0.02), (0.017, 0.0105), (0, 0.0095)], porcelain)
    place(body, x, y, saucer.location.z + 0.0075)
    seat(body, saucer.location.z + 0.0072)
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
_sn = stem_mat.node_tree.nodes; _sl = stem_mat.node_tree.links      # fine, fissured bark
_sl.new(bump(_sn, _sl, noise(_sn, _sl, 900, 4, 0.7), 0.35, 0.0003), principled(_sn).inputs['Normal'])
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
slub = nn.new('ShaderNodeTexNoise'); slub.inputs['Scale'].default_value = 1.0; slub.inputs['Detail'].default_value = 2.0
smp = nn.new('ShaderNodeMapping'); smp.inputs['Scale'].default_value = (110, 5, 1)   # slubs: thicker runs of one thread
nl_.new(nmp.outputs['Vector'], smp.inputs['Vector']); nl_.new(smp.outputs['Vector'], slub.inputs['Vector'])
nl_.new(mix(nn, nl_, lc.outputs['Color'], map_range(nn, nl_, slub.outputs['Fac'], 0.9, 1.08, 0.3, 0.7), 'MULTIPLY'), np_.inputs['Base Color'])
np_.inputs['Roughness'].default_value = 0.88
np_.inputs['Sheen Weight'].default_value = 0.7; np_.inputs['Sheen Roughness'].default_value = 0.45
nnor = ntex('nor_gl', False); nnm = nn.new('ShaderNodeNormalMap'); nnm.inputs['Strength'].default_value = 1.4
nl_.new(nnor.outputs['Color'], nnm.inputs['Color'])
weave = bump(nn, nl_, ntex('disp', False).outputs['Color'], 0.5, 0.0004, nnm.outputs['Normal'])   # the weave stands up in raking light
crinkle = noise(nn, nl_, 60, 6, 0.62)                # washed linen: fine creases on top of the weave
nl_.new(bump(nn, nl_, crinkle, 0.25, 0.0012, weave), np_.inputs['Normal'])

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
    q = Vector((x * 21, y * 21, 1.37))
    amp = 0.004 + 0.0025 * mnoise.noise(Vector((1.3, y * 9, 0.2)))
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
    dm = nap.modifiers.new(nm_, 'DISPLACE'); dm.texture = t; dm.strength = amt; dm.mid_level = 0.5
    dm.texture_coords = 'OBJECT'
sol = nap.modifiers.new('folded thickness', 'SOLIDIFY'); sol.thickness = 0.0028; sol.offset = 1.0
nap.location += Vector((0, 0.0015, -0.0015))   # the sim keeps cloth 1.8 mm off the stone; let it lie on it
soft = nap.modifiers.new('soft edges', 'SUBSURF'); soft.levels = soft.render_levels = 1
zs = [(nap.matrix_world @ v.co).z for v in nap.data.vertices]
print('NAPKIN_Z', round(min(zs), 3), round(max(zs), 3))
assert min(zs) < TOP_Z - 0.12, 'napkin did not drape over the edge'
assert max(zs) < TOP_Z + 0.03, 'napkin is floating'


# ---------- the sink run: Calacatta LX Noir on walnut, along the left wall ----------
noir, noir_img = quartz_mat('Quartz LX Noir', os.path.join(TEX, 'slab-lx-noir-x4.png'), deep=0.2, lift=(1.05, 1.05, 1.05), sat=1.0)
NOIR_W = 3.2
NOIR_H = NOIR_W * noir_img.size[1] / noir_img.size[0]
NOIR_OFF = (2.45, 0.7)            # the slab mirrors (a bookmatched second slab) at Y 0.75, between sink and cooktop
LT, RUN_D = 0.03, 0.62            # 30 mm perimeter tops, 620 mm deep
RUN_Y0, RUN_Y1 = -2.5, 2.35
RUN_X1 = RX0 + RUN_D
SINK_SX, SINK_SY, SINK_R = 0.42, 0.74, 0.028   # undermount opening: across, along the run, corner radius
COOK = (RX0 + 0.3, 1.45)
FRONT_X = RX0 + 0.58              # cabinet door faces

def noir_uv(x, y):
    """Along the run is the slab's length, out from the wall its height."""
    return ((y + NOIR_OFF[0]) / NOIR_W, (x - RX0 + NOIR_OFF[1]) / NOIR_H)

def unfold_uv(o, uvfun, top_z):
    """Faces that are not flat take the slab from where they would lie if folded up into the top, so an edge,
    the sink cut-out and the backsplash carry the same veins on, as when they are cut from one slab."""
    me = o.data; uv = me.uv_layers.get('UV') or me.uv_layers.new(name='UV')
    for poly in me.polygons:
        n = poly.normal
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if abs(n.z) > 0.5: uv.data[li].uv = uvfun(co.x, co.y)
            else:
                drop = top_z - co.z
                uv.data[li].uv = uvfun(co.x + n.x * drop, co.y + n.y * drop)

def smooth_by_angle(o, deg=35):
    select_only(o)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(deg))
    o.select_set(False)

def rounded_prism(name, cx, cy, sx, sy, r, z0, z1, seg=12, cap_top=True):
    pts = []
    for qx, qy, a0 in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        ccx, ccy = cx + qx * (sx / 2 - r), cy + qy * (sy / 2 - r)
        for k in range(seg + 1):
            a = math.radians(a0 + 90 * k / seg)
            pts.append((ccx + r * math.cos(a), ccy + r * math.sin(a)))
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bot = [bm.verts.new((x, y, z0)) for x, y in pts]
    top_ = [bm.verts.new((x, y, z1)) for x, y in pts]
    bm.faces.new(list(reversed(bot)))
    if cap_top: bm.faces.new(top_)
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        bm.faces.new((bot[i], bot[j], top_[j], top_[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    return link(bpy.data.objects.new(name, me))

def cyl(name, x, y, z0, z1, r, mat, n=48):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=n, radius1=r, radius2=r, depth=z1 - z0)
    bm.to_mesh(me); bm.free()
    o = link(bpy.data.objects.new(name, me)); o.location = (x, y, (z0 + z1) / 2); o.data.materials.append(mat)
    smooth_by_angle(o, 40)
    return o

def tube(name, pts, radius, mat):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = radius; cu.bevel_resolution = 6
    cu.use_fill_caps = True
    s = cu.splines.new('BEZIER'); s.bezier_points.add(len(pts) - 1); s.resolution_u = 24
    for bpt, co in zip(s.bezier_points, pts): bpt.co = co; bpt.handle_left_type = bpt.handle_right_type = 'AUTO'
    o = link(bpy.data.objects.new(name, cu)); o.data.materials.append(mat)
    return o

# counter, with the undermount opening cut through it
run_top = box('Run counter', RX0, RUN_X1, RUN_Y0, RUN_Y1, TOP_Z - LT, TOP_Z, noir)
cut = rounded_prism('Sink cut', SINK[0], SINK[1], SINK_SX, SINK_SY, SINK_R, TOP_Z - LT - 0.01, TOP_Z + 0.01)
bo = run_top.modifiers.new('sink', 'BOOLEAN'); bo.object = cut; bo.operation = 'DIFFERENCE'; bo.solver = 'EXACT'
apply_all(run_top); bpy.data.objects.remove(cut)
unfold_uv(run_top, noir_uv, TOP_Z)
smooth_by_angle(run_top)
# backsplash and its ledge, which is also the window sill: the veins fold up from the counter onto them
bs = box('Backsplash', RX0, RX0 + 0.02, RUN_Y0, RUN_Y1, TOP_Z, TOP_Z + 0.6, noir)
unfold_uv(bs, noir_uv, TOP_Z)
ledge = box('Backsplash ledge', RX0, RX0 + 0.07, RUN_Y0, RUN_Y1, TOP_Z + 0.6, WIN_Z[0], noir)
unfold_uv(ledge, lambda x, y: noir_uv(x - 0.64, y), WIN_Z[0])
for o in (run_top, bs, ledge):
    e = o.modifiers.new('ease', 'BEVEL'); e.width = 0.0018; e.segments = 3; e.limit_method = 'ANGLE'

# brushed stainless basin under the opening; the stone overhangs it by a few millimetres
steel, stn, stl = new_mat('Brushed stainless')
stp = principled(stn)
stp.inputs['Base Color'].default_value = (0.6, 0.6, 0.59, 1); stp.inputs['Metallic'].default_value = 1.0
spots = imperf(stn, stl, 'SurfaceImperfections003', 'Opacity', 0.3, box=True)    # dried water marks
srgh = map_range(stn, stl, imperf(stn, stl, 'Metal009', 'Roughness', 0.35, box=True), 0.2, 0.36)
stl.new(math_node(stn, stl, 'ADD', srgh, math_node(stn, stl, 'MULTIPLY', spots, 0.14)), stp.inputs['Roughness'])
snm = stn.new('ShaderNodeNormalMap'); snm.inputs['Strength'].default_value = 0.35
stl.new(imperf(stn, stl, 'Metal009', 'NormalGL', 0.35, box=True), snm.inputs['Color']); stl.new(snm.outputs['Normal'], stp.inputs['Normal'])
BASIN_Z = TOP_Z - LT - 0.21
basin = rounded_prism('Sink basin', SINK[0], SINK[1], SINK_SX + 0.008, SINK_SY + 0.008, SINK_R + 0.004,
                      BASIN_Z, TOP_Z - LT - 0.0005, cap_top=False)
basin.data.materials.append(steel)
bv = basin.modifiers.new('round', 'BEVEL'); bv.width = 0.016; bv.segments = 5; bv.limit_method = 'ANGLE'
sw = basin.modifiers.new('wall', 'SOLIDIFY'); sw.thickness = 0.0012; sw.offset = 1.0
apply_all(basin); smooth_by_angle(basin)
dark_metal = simple_mat('Drain', (0.05, 0.05, 0.05), rough=0.4, metal=0.8)
DR = (SINK[0] - 0.02, SINK[1] + 0.2)
cyl('Drain flange', *DR, BASIN_Z, BASIN_Z + 0.0025, 0.044, steel)
cyl('Drain strainer', *DR, BASIN_Z + 0.0025, BASIN_Z + 0.003, 0.034, dark_metal)
cyl('Drain knob', *DR, BASIN_Z + 0.003, BASIN_Z + 0.01, 0.007, steel)

# gooseneck faucet in brushed brass, behind the basin
fbrass = brass_mat('Brushed brass', spun=False)
FX, FY = RX0 + 0.07, SINK[1]
seat(cyl('Faucet base', FX, FY, TOP_Z, TOP_Z + 0.007, 0.031, fbrass), TOP_Z)
cyl('Faucet column', FX, FY, TOP_Z + 0.006, TOP_Z + 0.2, 0.0185, fbrass)
tube('Faucet spout', [(FX, FY, TOP_Z + 0.19), (FX, FY, TOP_Z + 0.31), (FX + 0.055, FY, TOP_Z + 0.375),
                      (FX + 0.15, FY, TOP_Z + 0.345), (FX + 0.19, FY, TOP_Z + 0.27), (FX + 0.195, FY, TOP_Z + 0.245)], 0.011, fbrass)
cyl('Faucet aerator', FX + 0.195, FY, TOP_Z + 0.226, TOP_Z + 0.246, 0.0118, fbrass)
tube('Faucet lever', [(FX, FY + 0.012, TOP_Z + 0.15), (FX + 0.01, FY + 0.06, TOP_Z + 0.172), (FX + 0.016, FY + 0.092, TOP_Z + 0.185)], 0.0045, fbrass)

# cabinets: walnut slab fronts with 3 mm gaps, a recessed pull channel under the stone, black toe kick
for ya, yb, zb in ((RUN_Y0 + 0.02, -0.75, TOP_Z - LT), (-0.75, 0.05, BASIN_Z - 0.01), (0.05, RUN_Y1 - 0.02, TOP_Z - LT)):
    box('Run carcass', RX0, FRONT_X - 0.02, ya, yb, 0.1, zb, walnut_dark)     # hollow under the basin
box('Run toe kick', RX0, FRONT_X - 0.075, RUN_Y0 + 0.02, RUN_Y1 - 0.02, 0.0, 0.1, black)
for nm, ya, yb in (('front', RUN_Y0, RUN_Y0 + 0.02), ('back', RUN_Y1 - 0.02, RUN_Y1)):
    planar_uv(box(f'Run end panel {nm}', RX0, FRONT_X, ya, yb, 0.0, TOP_Z - LT, walnut_dark, bevel=0.0015), 2, 0, scale=0.7, off=(0.2, 0.5))
CH, GAP = 0.045, 0.003
ZT = TOP_Z - LT - CH
box('Run pull channel', FRONT_X - 0.035, FRONT_X - 0.019, RUN_Y0 + 0.02, RUN_Y1 - 0.02, ZT, TOP_Z - LT, black)
UNITS = [(RUN_Y0 + 0.02, -1.55, (0.1, 0.42, 0.64, ZT), 1),    # drawers
         (-1.55, -0.75, (0.1, ZT), 1),                        # dishwasher panel
         (-0.75, 0.05, (0.1, ZT), 2),                         # sink base, a pair of doors
         (0.05, 0.85, (0.1, 0.42, 0.64, ZT), 1),
         (0.85, 2.05, (0.1, 0.5, ZT), 1),                     # pan drawers under the cooktop
         (2.05, RUN_Y1 - 0.02, (0.1, ZT), 1)]
k = 0
for ya, yb, rows, cols in UNITS:
    w = (yb - ya) / cols
    for c in range(cols):
        for za, zb in zip(rows, rows[1:]):
            o = box(f'Run front {k}', FRONT_X - 0.02, FRONT_X, ya + c * w + GAP / 2, ya + (c + 1) * w - GAP / 2,
                    za + GAP / 2, zb - GAP / 2, walnut_dark, bevel=0.0012)
            off = (rng.uniform(0, 1), rng.uniform(0, 1))
            if zb - za > 0.4: planar_uv(o, 2, 1, scale=0.7, off=off)      # doors: grain runs up
            else: planar_uv(o, 1, 2, scale=0.7, off=off)                  # drawers: grain runs across
            k += 1

# flush induction cooktop: black glass, with the smudges glass always has
glass, gn, gl = new_mat('Black glass')
gp = principled(gn)
gp.inputs['Base Color'].default_value = (0.006, 0.006, 0.007, 1)
gprint = imperf(gn, gl, 'Fingerprints002', 'Opacity', 0.25, rot=1.1)
gsm = imperf(gn, gl, 'SurfaceImperfections003', 'Opacity', 0.5)
gl.new(math_node(gn, gl, 'ADD', math_node(gn, gl, 'MULTIPLY', gprint, 0.22), math_node(gn, gl, 'MULTIPLY', gsm, 0.08)), gp.inputs['Roughness'])
gp.inputs['IOR'].default_value = 1.52
box('Cooktop', COOK[0] - 0.255, COOK[0] + 0.255, COOK[1] - 0.29, COOK[1] + 0.29, TOP_Z, TOP_Z + 0.005, glass, bevel=0.0015)

def window_side(name, y0, y1, z0, z1, x, bays):
    """Steel-framed window in the left wall (the frames sit 60 mm into the reveal), no glass."""
    t, dpt = 0.045, 0.07
    box(f'{name} frame front', x - dpt, x, y0, y0 + t, z0, z1, black)
    box(f'{name} frame back', x - dpt, x, y1 - t, y1, z0, z1, black)
    box(f'{name} frame sill', x - dpt, x, y0, y1, z0, z0 + t, black)
    box(f'{name} frame head', x - dpt, x, y0, y1, z1 - t, z1, black)
    for i in range(1, bays):
        y = y0 + i * (y1 - y0) / bays
        box(f'{name} mullion {i}', x - dpt + 0.01, x - 0.01, y - 0.02, y + 0.02, z0, z1, black)
    bpy.ops.object.light_add(type='AREA', location=(x - 0.3, (y0 + y1) / 2, (z0 + z1) / 2), rotation=(0, math.radians(-90), 0))
    portal = bpy.context.active_object; portal.name = f'{name} portal'
    portal.data.shape = 'RECTANGLE'; portal.data.size = z1 - z0; portal.data.size_y = y1 - y0
    portal.data.cycles.is_portal = True
window_side('Window C', WIN_Y[0], WIN_Y[1], WIN_Z[0], WIN_Z[1], RX0 - 0.06, 2)

# by the sink: a stoneware soap pump, a worn walnut board leaning on the backsplash, a lidded crock
pump_glaze = stoneware('Stoneware pump', (0.7, 0.665, 0.6), (0.56, 0.44, 0.32), 0.17, 0.003, speck=0.04)
pump = lathe('Soap pump', [(0, 0.0), (0.03, 0.0), (0.034, 0.004), (0.036, 0.02), (0.036, 0.13), (0.033, 0.152),
                           (0.022, 0.164), (0.014, 0.168), (0.013, 0.172), (0, 0.172)], pump_glaze)
handmade(pump, 0.0008)
place(pump, RX0 + 0.11, SINK[1] - 0.53)
seat(pump, TOP_Z)
PZ = pump.location.z + 0.172
cyl('Soap pump collar', RX0 + 0.11, SINK[1] - 0.53, PZ - 0.004, PZ + 0.008, 0.0135, fbrass)
cyl('Soap pump stem', RX0 + 0.11, SINK[1] - 0.53, PZ + 0.008, PZ + 0.03, 0.004, fbrass)
tube('Soap pump nozzle', [(RX0 + 0.11, SINK[1] - 0.53, PZ + 0.03), (RX0 + 0.125, SINK[1] - 0.53, PZ + 0.035), (RX0 + 0.145, SINK[1] - 0.53, PZ + 0.031)], 0.0042, fbrass)

board = import_gltf(os.path.join(A, 'props', 'wooden_cutting_board', 'wooden_cutting_board_2k.gltf'))[0]
board.name = 'Cutting board'
lean = math.radians(13)            # the board's face, tipped back against the backsplash
board.matrix_world = Matrix(((0, -math.sin(lean), math.cos(lean), RX0 + 0.02 + 0.123 * math.sin(lean)),
                             (1, 0, 0, SINK[1] + 0.66),
                             (0, math.cos(lean), math.sin(lean), TOP_Z + 0.123 * math.cos(lean)),
                             (0, 0, 0, 1)))
seat(board, TOP_Z)
crock = import_gltf(os.path.join(A, 'props', 'ceramic_pot', 'ceramic_pot_2k.gltf'))[0]
crock.name = 'Crock'
crock.scale = (0.42, 0.42, 0.42); crock.rotation_euler.z = math.radians(-25)
crock.location = (RX0 + 0.2, SINK[1] + 1.12, TOP_Z)
seat(crock, TOP_Z)

# brass bar pulls on the tall pantry doors, either side of the door gap
for x in (CX0 + 0.6 - 0.035, CX0 + 0.6 + 0.035):
    for z in (0.95, 1.55):
        tube(f'Pantry pull stand {x:.3f} {z}', [(x, WY - 0.62, z), (x, WY - 0.645, z)], 0.005, fbrass)
    tube(f'Pantry pull {x:.3f}', [(x, WY - 0.645, 0.93), (x, WY - 0.645, 1.57)], 0.0065, fbrass)

# recessed downlights (off: it is daytime). Named "Ceiling ..." so they hide with the ceiling from above.
trim = simple_mat('Downlight trim', (0.78, 0.77, 0.75), rough=0.35)
lens = simple_mat('Downlight lens', (0.2, 0.2, 0.2), rough=0.15)
for i, (x, y) in enumerate([(-2.95, -1.7), (-2.95, -0.35), (-2.95, 1.0), (-2.95, 2.1), (-0.95, -1.5), (0.55, -1.5), (-0.95, 1.5), (0.55, 1.5)]):
    for o in (cyl(f'Ceiling light {i}', x, y, RZ - 0.003, RZ, 0.046, trim), cyl(f'Ceiling light lens {i}', x, y, RZ - 0.0034, RZ - 0.003, 0.033, lens)):
        o.visible_camera = False

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SRC, 'scene.blend'))
print('SCENE_OK', len(scene.objects), 'objects')
