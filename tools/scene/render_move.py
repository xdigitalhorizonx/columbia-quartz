# Renders the homepage camera move from scene.blend (made by build_scene.py). It is one continuous shot
# in three legs, with a hold at the end of each, where the page stops and shows a 4K still:
#   move   frames   0-119  straight down over the island, craning down to its mitred front edge (hold 119)
#   glide  frames 120-191  across the aisle to the sink run in Calacatta LX Noir                (hold 191)
#   pull   frames 192-287  pulling back and up to show the whole kitchen                       (hold 287)
#   blender -b <src>/scene.blend --python tools/scene/render_move.py -- --cam wide --res 1920x1080 \
#           --frames 0-287 --samples 256 --out <dir>
# --cam wide (16:9) or tall (9:16, its own framing). --frames takes "a-b" or "a,b,c" (global frame numbers),
# so "--frames 0,119,191,287" renders the four stills. --notes prints where the island's front edge and the
# name-tag anchors land in the hold frames (for NOTES in home.js); add --only-notes 1 to skip rendering.
import bpy, json, math, os, sys
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
opt = {argv[i][2:]: argv[i + 1] for i in range(0, len(argv) - 1, 2)}
CAM = opt.get('cam', 'wide')
W, H = map(int, opt.get('res', '960x540').split('x'))
SAMPLES = int(opt.get('samples', '256'))
OUT = opt.get('out', os.path.join(os.path.dirname(bpy.data.filepath), 'renders', CAM))
LEGS = (('move', 120), ('glide', 72), ('pull', 96))
TOTAL = sum(n for _, n in LEGS)
HOLDS = (0, 119, 191, 287)
spec = opt.get('frames', f'0-{TOTAL - 1}')
FRAMES = list(range(int(spec.split('-')[0]), int(spec.split('-')[1]) + 1)) if '-' in spec else [int(x) for x in spec.split(',')]

TOP_Z, EDGE, Y0 = 0.92, 0.10, -0.55
RX0 = -3.25
# Leg 1. Start: straight down from 2.6 m over the counter (pivot p0). End: a counter-height view of the front
# edge from D metres out and h above the top, looking down `pitch1` degrees, with the lens shifted (as an
# architectural photographer would) so the front edge sits at y1 (fraction of frame height, from the bottom).
PATHS = {
    'wide': dict(p0=(-0.64, -0.27), r0=2.6, f0=50, p1=(-0.18, Y0), D=2.7, h=0.634, f1=70, pitch1=8.0, y1=0.405),
    'tall': dict(p0=(-0.34, -0.33), r0=2.6, f0=58, p1=(-0.45, Y0), D=2.7, h=0.634, f1=100, pitch1=8.0, y1=0.41),
}
# Legs 2 and 3 end on these views: camera position, the point it looks at, lens, vertical lens shift (the
# camera stays near level so verticals stay vertical, as an architectural photographer works), f-stop, and
# the point in focus when it is not the one looked at. Wide ends on a three-quarter view of the whole room;
# tall pulls straight back from the sink to look down the island at the sink wall, which suits a 9:16 frame.
SHOTS = {
    'wide': dict(sink=dict(loc=(-1.35, -1.75, 1.6), at=(-3.1, -0.45, 1.41), lens=35, shift=-0.07, fstop=5.6),
                 kitchen=dict(loc=(1.3, -3.9, 2.2), at=(-1.7, 1.0, 1.75), lens=20, shift=-0.16, fstop=8.0)),
    'tall': dict(sink=dict(loc=(-1.6, -1.45, 1.6), at=(-3.15, -0.35, 1.38), lens=26, shift=-0.06, fstop=5.6),
                 kitchen=dict(loc=(2.2, -0.15, 2.15), at=(-3.0, -0.4, 0.75), lens=26, fstop=8.0,
                              focus=(-0.5, -0.35, 0.92), via=(1.5, -0.95, 2.1))),
}
# Name tags point at a spot on each stone at each hold: (tag, world point).
TAGS = {
    'wide': {119: [('gold', (0.32, -0.32, TOP_Z))], 191: [('noir', (RX0 + 0.02, -0.82, TOP_Z + 0.3))],
             287: [('gold', (0.4, -0.2, TOP_Z)), ('noir', (RX0 + 0.45, -1.4, TOP_Z))]},
    'tall': {119: [('gold', (-0.31, -0.46, TOP_Z))], 191: [('noir', (RX0 + 0.02, -0.75, TOP_Z + 0.3))],
             287: [('gold', (0.0, 0.25, TOP_Z)), ('noir', (RX0 + 0.4, 0.45, TOP_Z))]},
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

def aim(d):
    """Camera euler (no roll) looking along d: rx tips it from straight down, rz turns it about Z."""
    d = d.normalized()
    return math.acos(max(-1.0, min(1.0, -d.z))), math.atan2(-d.x, d.y)

def apply(s):
    cam.location = s['loc']
    cam.rotation_euler = (s['rx'], 0, s['rz'])
    cam_data.lens = s['lens']; cam_data.shift_y = s['shift']
    cam_data.dof.focus_distance = s['focus']; cam_data.dof.aperture_fstop = s['fstop']
    bpy.context.view_layer.update()

SHIFT1 = 0.0
def move(t):
    """Leg 1, as a camera state."""
    e = lerp(90.0, E1, t)
    r = lerp(P['r0'], R1, t)
    piv = Vector((lerp(P['p0'][0], P['p1'][0], t), lerp(P['p0'][1], P['p1'][1], t), TOP_Z))
    rise = (E1 - P['pitch1']) * t * t
    er = math.radians(e)
    loc = piv + r * Vector((0, -math.cos(er), math.sin(er)))
    focus = piv + Vector((0, 0.2 * t, 0))         # ends on the objects just behind the edge
    return dict(loc=loc, rx=math.radians(90 - (e - rise)), rz=0.0, lens=loglerp(P['f0'], P['f1'], t),
                shift=SHIFT1 * t * t, focus=(focus - loc).length, fstop=loglerp(N0, N1, t))

def shot(name):
    s = SHOTS[CAM][name]
    loc, at = Vector(s['loc']), Vector(s['at'])
    rx, rz = aim(at - loc)
    focus = (Vector(s.get('focus', s['at'])) - loc).length
    return dict(loc=loc, rx=rx, rz=rz, lens=s['lens'], shift=s.get('shift', 0.0), focus=focus, fstop=s['fstop'])

def blend(a, b, t, path):
    """A state between two views: position along a Bezier `path` (its two inner control points), the view
    turning by angle (never rolling), lens and aperture eased in log space."""
    p0, p1, p2, p3 = a['loc'], path[0], path[1], b['loc']
    u = 1 - t
    loc = p0 * u ** 3 + p1 * 3 * u * u * t + p2 * 3 * u * t * t + p3 * t ** 3
    drz = (b['rz'] - a['rz'] + math.pi) % (2 * math.pi) - math.pi
    return dict(loc=loc, rx=lerp(a['rx'], b['rx'], t), rz=a['rz'] + drz * t, lens=loglerp(a['lens'], b['lens'], t),
                shift=lerp(a['shift'], b['shift'], t), focus=loglerp(a['focus'], b['focus'], t),
                fstop=loglerp(a['fstop'], b['fstop'], t))

def solve_shift():
    """Lens shift that puts the island's front edge at y1 at the end of leg 1 (projection is linear in shift)."""
    global SHIFT1
    edge = Vector((P['p1'][0], Y0, TOP_Z))
    def y_at(s):
        global SHIFT1
        SHIFT1 = s; apply(move(1.0))
        return world_to_camera_view(scene, cam, edge).y
    a, b = y_at(0.0), y_at(0.1)
    SHIFT1 = 0.1 * (P['y1'] - a) / (b - a)
    return SHIFT1

solve_shift()
ISLAND, SINK_V, KITCHEN = move(1.0), shot('sink'), shot('kitchen')

def fwd(s):
    return Vector((-math.sin(s['rz']) * math.sin(s['rx']), math.cos(s['rz']) * math.sin(s['rx']), -math.cos(s['rx'])))

# glide: a gentle arc across the aisle. pull: straight back along the sink view first, then up and round,
# arriving backwards along the last view; `via` (tall) keeps the camera in front of the island, not over it.
GLIDE = (ISLAND['loc'].lerp(SINK_V['loc'], 0.35) + Vector((0.15, -0.25, 0.0)), SINK_V['loc'].lerp(ISLAND['loc'], 0.3))
VIA = SHOTS[CAM]['kitchen'].get('via')
PULL = (SINK_V['loc'] - fwd(SINK_V) * 0.9, Vector(VIA) if VIA else KITCHEN['loc'] + fwd(KITCHEN) * 0.6)

def state(k):
    if k <= 119: return move(k / 119)
    if k <= 191: return blend(ISLAND, SINK_V, (k - 119) / 72, GLIDE)     # evenly spaced: the page eases each leg
    return blend(SINK_V, KITCHEN, (k - 191) / 96, PULL)

def pose(k):
    apply(state(k))
    # the ceiling and its downlights hide from the camera while it is above them (leg 1)
    for o in scene.objects:
        if o.name.startswith('Ceiling'):
            o.visible_camera = k > 119

print('SHIFT1', round(SHIFT1, 4), 'E1', round(E1, 2), 'R1', round(R1, 3))

if 'notes' in opt:
    def proj(k, pts):
        pose(k)
        return [[round(q.x, 4), round(1 - q.y, 4)] for q in (world_to_camera_view(scene, cam, Vector(p)) for p in pts)]
    edge = {x: proj(119, [(x, Y0, TOP_Z), (x, Y0, TOP_Z - EDGE / 2), (x, Y0, TOP_Z - EDGE)])
            for x in map(float, opt['notes'].split(','))}
    tags = {str(k): {name: proj(k, [p])[0] for name, p in v} for k, v in TAGS[CAM].items()}
    print('NOTES', json.dumps({'cam': CAM, 'edge': edge, 'tags': tags}))
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
    pose(f)
    scene.render.filepath = os.path.join(OUT, f'{f:03d}.png')
    bpy.ops.render.render(write_still=True)
    print('FRAME_DONE', f, flush=True)
print('RENDER_OK', CAM, len(FRAMES))
