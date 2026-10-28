# Renders the plan-to-elevation camera move from scene.blend (made by build_scene.py).
#   blender -b <src>/scene.blend --python tools/scene/render_move.py -- --cam wide --res 1920x1080 \
#           --count 120 --frames 0-119 --samples 384 --out <dir>
# --cam wide (16:9) or tall (9:16, its own framing). --frames takes "a-b" or "a,b,c"; frame k sits at
# t = k / (count - 1) along the move, so "--count 2 --frames 0,1" renders the two endpoint stills.
# --notes x1,x2,... prints where points on the front edge land in the last frame (for NOTES in home.js).
import bpy, json, math, os, sys
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
opt = {argv[i][2:]: argv[i + 1] for i in range(0, len(argv) - 1, 2)}
CAM = opt.get('cam', 'wide')
W, H = map(int, opt.get('res', '960x540').split('x'))
COUNT = int(opt.get('count', '120'))
SAMPLES = int(opt.get('samples', '384'))
OUT = opt.get('out', os.path.join(os.path.dirname(bpy.data.filepath), 'renders', CAM))
spec = opt.get('frames', f'0-{COUNT - 1}')
FRAMES = list(range(int(spec.split('-')[0]), int(spec.split('-')[1]) + 1)) if '-' in spec else [int(x) for x in spec.split(',')]

TOP_Z, EDGE, Y0 = 0.92, 0.10, -0.55
# Start: straight down from 2.6 m over the counter (pivot p0). End: a counter-height view of the front edge
# from D metres out and h above the top, looking down `pitch1` degrees, with the lens shifted (as an
# architectural photographer would) so the front edge sits at y1 (fraction of frame height, from the bottom).
PATHS = {
    'wide': dict(p0=(-0.64, -0.27), r0=2.6, f0=50, p1=(-0.18, Y0), D=2.7, h=0.634, f1=70, pitch1=8.0, y1=0.405),
    'tall': dict(p0=(-0.22, -0.33), r0=2.6, f0=58, p1=(-0.43, Y0), D=2.7, h=0.634, f1=110, pitch1=8.0, y1=0.41),
}
P = PATHS[CAM]
E1 = math.degrees(math.atan2(P['h'], P['D']))
R1 = math.hypot(P['D'], P['h'])
N0, N1 = 11.0, 5.6            # aperture: deep focus from above, softer background at counter height

def lerp(a, b, t):
    return a + (b - a) * t

def loglerp(a, b, t):
    return math.exp(lerp(math.log(a), math.log(b), t))

scene = bpy.context.scene
cam_data = bpy.data.cameras.new('Cam'); cam_data.sensor_width = 36; cam_data.sensor_fit = 'AUTO'
cam_data.clip_start = 0.05; cam_data.clip_end = 60
cam_data.dof.use_dof = True; cam_data.dof.aperture_blades = 7; cam_data.dof.aperture_rotation = 0.3
cam = bpy.data.objects.new('Cam', cam_data); scene.collection.objects.link(cam); scene.camera = cam
scene.render.resolution_x, scene.render.resolution_y = W, H
scene.render.resolution_percentage = 100

SHIFT1 = 0.0
def pose(t):
    e = lerp(90.0, E1, t)
    r = lerp(P['r0'], R1, t)
    piv = Vector((lerp(P['p0'][0], P['p1'][0], t), lerp(P['p0'][1], P['p1'][1], t), TOP_Z))
    rise = (E1 - P['pitch1']) * t * t
    er = math.radians(e)
    cam.location = piv + r * Vector((0, -math.cos(er), math.sin(er)))
    cam.rotation_euler = (math.radians(90 - (e - rise)), 0, 0)
    cam_data.lens = loglerp(P['f0'], P['f1'], t)
    cam_data.shift_y = SHIFT1 * t * t
    focus = piv + Vector((0, 0.2 * t, 0))         # ends on the objects just behind the edge
    cam_data.dof.focus_distance = (focus - cam.location).length
    cam_data.dof.aperture_fstop = loglerp(N0, N1, t)
    bpy.context.view_layer.update()
    return piv

def solve_shift():
    """Lens shift that puts the front edge at y1 in the last frame (projection is linear in shift)."""
    global SHIFT1
    edge = Vector((P['p1'][0], Y0, TOP_Z))
    def y_at(s):
        global SHIFT1
        SHIFT1 = s; pose(1.0)
        return world_to_camera_view(scene, cam, edge).y
    a, b = y_at(0.0), y_at(0.1)
    SHIFT1 = 0.1 * (P['y1'] - a) / (b - a)
    pose(1.0)
    return SHIFT1

solve_shift()
print('SHIFT1', round(SHIFT1, 4), 'E1', round(E1, 2), 'R1', round(R1, 3))

if 'notes' in opt:
    pose(1.0)
    pts = {}
    for x in map(float, opt['notes'].split(',')):
        q = [world_to_camera_view(scene, cam, Vector((x, Y0, z))) for z in (TOP_Z, TOP_Z - EDGE / 2, TOP_Z - EDGE)]
        pts[x] = [round(q[0].x, 4)] + [round(1 - p.y, 4) for p in q]   # x, then y from the top: top/mid/bottom of the edge
    print('NOTES', json.dumps({'cam': CAM, 'edge': pts}))
    if opt.get('only-notes'):
        sys.exit(0)

scene.cycles.samples = SAMPLES
scene.render.use_persistent_data = True           # only the camera moves: keep the BVH between frames
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
for d in prefs.devices: d.use = d.type == 'OPTIX'
scene.cycles.device = 'GPU'
os.makedirs(OUT, exist_ok=True)
for f in FRAMES:
    pose(f / (COUNT - 1))
    scene.render.filepath = os.path.join(OUT, f'{f:03d}.png')
    bpy.ops.render.render(write_still=True)
    print('FRAME_DONE', f, flush=True)
print('RENDER_OK', CAM, len(FRAMES))
