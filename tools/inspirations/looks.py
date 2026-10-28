"""Content for the Inspirations page: one entry per room, in page order.

build_page.py turns this into inspirations/index.html. Edit copy here, then rebuild:
    python tools/inspirations/build_page.py

pin = where the surface marker sits on the photo, as % of width/height.
"""

SLABS = {
    "lx-gold":         ("Calacatta LX Gold", "No. 01"),
    "lx-classic":      ("Calacatta LX Classic", "No. 02"),
    "lx-supreme":      ("Calacatta LX Supreme", "No. 03"),
    "lx-noir":         ("Calacatta LX Noir", "No. 04"),
    "steel":           ("Calacatta Steel", "No. 05"),
    "classic-gold":    ("Calacatta Classic Gold", "No. 06"),
    "classic-arctic":  ("Calacatta Classic Arctic", "No. 07"),
    "classic-supreme": ("Calacatta Classic Supreme", "No. 08"),
    "classic-silver":  ("Calacatta Classic Silver", "No. 09"),
    "classic-pearl":   ("Calacatta Classic Pearl", "No. 10"),
}

CHAPTERS = [
    {
        "id": "kitchens", "no": "I.", "tone": "paper",
        "title": "The <em>kitchens</em>",
        "intro": "Seven kitchens, from a 1920s farmhouse to a post-and-beam modern. Same idea every time: pick the slab first, then build the room around it.",
    },
    {
        "id": "baths", "no": "II.", "tone": "ink",
        "title": "The <em>baths</em>",
        "intro": "Quartz earns its place in a bathroom. It never needs sealing, shrugs off soap and steam, and large slabs mean far fewer grout lines to scrub.",
    },
    {
        "id": "beyond", "no": "III.", "tone": "paper",
        "title": "Beyond <em>the kitchen</em>",
        "intro": "Laundry rooms, pantries, fireplaces. Anywhere a surface takes a beating and still has to look good.",
    },
]

LOOKS = [
    # ---------------- kitchens ----------------
    dict(id="farmhouse-kitchen", pin=(62, 60), chapter="kitchens", layout="side", slab="classic-gold", ar="3 / 2",
         title="The Updated <em>Farmhouse</em>",
         text="Warm white shaker doors, unlacquered brass and a wide oak floor: the farmhouse kitchen, grown up. "
              "Classic Gold's soft gold veins pick up the brass and keep an all-white kitchen from feeling cold.",
         notes=["Run the same slab up the wall behind the range. It reads calmer than tile and wipes clean in one pass.",
                "Choose a warm white paint, not a blue-white, so the gold veining looks intentional.",
                "Let unlacquered brass age. Its patina and the veining warm up together."],
         edge="Eased square, 3 cm", pairs="Warm white paint, unlacquered brass, white oak",
         alt="Farmhouse kitchen with a Calacatta Classic Gold quartz island, rush-seat oak stools and warm white shaker cabinets"),
    dict(id="after-dark-kitchen", pin=(66, 70), chapter="kitchens", layout="wide", slab="steel", ar="16 / 9",
         title="After <em>Dark</em>",
         text="Matte black cabinetry needs a surface with nerve. Steel's broad gray veins hold their own against it, "
              "and a mitred waterfall end lets them pour straight down to the floor.",
         notes=["Ask for the veins to continue across the mitre, so the island reads as one solid block.",
                "In a dark kitchen the white stone becomes the light. Keep the counters clear and let it work.",
                "Smoked oak and black leather warm up the contrast without adding color."],
         edge="Mitred waterfall", pairs="Matte black, smoked oak, black hardware",
         alt="Matte black kitchen with a Calacatta Steel quartz waterfall island and full-height backsplash on a rainy day"),
    dict(id="quiet-minimal-kitchen", pin=(40, 46), chapter="kitchens", layout="side", flip=True, slab="lx-classic", ar="3 / 2",
         title="Quiet <em>Minimal</em>",
         text="When the cabinetry is handleless oak, the counter should almost disappear. "
              "LX Classic's misty, barely-there veining gives you the depth of stone without any noise.",
         notes=["Go thin. A 2 cm slab with a square edge keeps the profile crisp.",
                "Carry the counter up as the backsplash to get rid of grout lines.",
                "Keep three things on the counter, not ten. Minimal is mostly restraint."],
         edge="Square, 2 cm", pairs="Rift white oak, lime plaster, brushed steel",
         alt="Minimal oak kitchen with a thin Calacatta LX Classic quartz countertop and backsplash beside a tall loft window"),
    dict(id="estate-kitchen", pin=(52, 45), chapter="kitchens", layout="pair", slab="lx-supreme", ar="4 / 5",
         title="The Estate <em>Kitchen</em>",
         text="A formal kitchen built around the range. LX Supreme's cloudy gray movement reads like Statuario marble, "
              "so one tall slab behind the range becomes the centerpiece.",
         notes=["Place the slab's strongest movement behind the range. See your slab before it's cut.",
                "Soft gray-green paint and polished nickel let the stone stay the star.",
                "Glass-front uppers on each side keep a big alcove from feeling heavy."],
         edge="Eased, 3 cm", pairs="French gray-green, polished nickel, herringbone oak",
         alt="Traditional range alcove with a full-height Calacatta LX Supreme quartz backsplash behind a navy range"),
    dict(id="city-galley-kitchen", pin=(22, 64), chapter="kitchens", layout="pair", slab="classic-silver", ar="4 / 5",
         title="City <em>Galley</em>",
         text="In a narrow pre-war galley every surface counts. Classic Silver's fine linear veining, "
              "run lengthwise, pulls the eye down the room and makes it feel longer.",
         notes=["Run linear veins along a galley, never across it. Across, they chop the room up.",
                "Sage green and brass soften a bright counter in an older building.",
                "Open shelves on one side only keep a narrow room from closing in."],
         edge="Eased, 3 cm", pairs="Sage green, brass, walnut, white hex tile",
         alt="Narrow galley kitchen with sage green cabinets and Calacatta Classic Silver quartz countertops"),
    dict(id="coastal-kitchen", pin=(36, 62), chapter="kitchens", layout="side", slab="classic-pearl", ar="3 / 2",
         title="Coastal <em>Light</em>",
         text="A light kitchen doesn't need a white counter. Classic Pearl's warm greige sits easily beside limed oak "
              "and limewash, and hides everyday crumbs far better than bright white.",
         notes=["Warm neutrals forgive. Pearl hides water spots and crumbs better than stark white.",
                "A short backsplash ledge holds the oil and salt and lets the plaster wall breathe.",
                "Lean on texture: limewash, linen, handmade ceramics. It keeps a pale room from going flat."],
         edge="Eased, 3 cm", pairs="Limed oak, limewash, unlacquered brass",
         alt="Relaxed coastal kitchen with limed oak cabinets and warm greige Calacatta Classic Pearl quartz counters"),
    dict(id="midcentury-kitchen", pin=(66, 63), chapter="kitchens", layout="wide", slab="lx-noir", ar="16 / 9",
         title="Mid-Century <em>Walnut</em>",
         text="Walnut, terrazzo and a beamed ceiling ask for something graphic. "
              "LX Noir's bold charcoal veins bring the drama of a vintage marble without the upkeep.",
         notes=["Bold stone needs simple doors. Slab-front walnut lets the veining lead.",
                "Repeat the black once or twice, in stools or a light, so the veins feel connected.",
                "Go big on the island. A long run shows off the full sweep of the vein."],
         edge="Mitred waterfall, 3 cm", pairs="Walnut, terrazzo, black accents",
         alt="Mid-century walnut kitchen under a wood beamed ceiling with a Calacatta LX Noir quartz island"),
    # ---------------- baths ----------------
    dict(id="primary-bath", pin=(16, 50), chapter="baths", layout="side", slab="classic-arctic", ar="3 / 2",
         title="The Primary <em>Bath</em>",
         text="A primary bath should feel like an exhale. Classic Arctic's bright white and fine hairline veins keep a long "
              "double vanity crisp, and a tall quartz backsplash means no grout behind the taps.",
         notes=["Take the quartz up the wall behind the faucets: one surface, nothing to scrub.",
                "Fluted oak adds texture so an all-white bath doesn't feel clinical.",
                "Wall-mounted faucets leave the counter clear and quick to wipe."],
         edge="Eased, 3 cm", pairs="Fluted white oak, brushed nickel, limewash",
         alt="Primary bathroom with a floating fluted oak double vanity and a Calacatta Classic Arctic quartz top and backsplash"),
    dict(id="powder-room", pin=(48, 68), chapter="baths", layout="pair", slab="lx-gold", ar="4 / 5",
         title="The Jewel-Box <em>Powder Room</em>",
         text="The smallest room in the house is the place to be bold. A floating vanity built from mitred LX Gold, "
              "against deep green plaster, turns a powder room into a jewel box.",
         notes=["Mitred corners let the gold veins wrap the box, so it looks carved from one block.",
                "Dark walls make white stone glow. Green, ink or oxblood all suit gold veining.",
                "A small room needs little stone, so a statement slab is an easy splurge."],
         edge="Mitred box", pairs="Forest green plaster, unlacquered brass",
         alt="Small powder room with deep green plaster walls and a floating mitred Calacatta LX Gold quartz vanity"),
    dict(id="spa-shower", pin=(36, 52), chapter="baths", layout="pair", slab="classic-supreme", ar="4 / 5",
         title="The Slab <em>Shower</em>",
         text="Full quartz slabs on the shower walls mean almost no grout lines, and a bench and niche cut from the "
              "same stone make the whole shower look built, not tiled.",
         notes=["Quartz is non-porous, so slab walls resist mildew and never need sealing.",
                "Plan the niche during slab layout so the veining runs through it.",
                "A curbless entry and one glass panel let the stone read wall to wall."],
         edge="Eased", pairs="Brushed brass, matte gray mosaic",
         alt="Walk-in shower lined with Calacatta Classic Supreme quartz slabs, with a floating bench and long niche"),
    # ---------------- beyond ----------------
    dict(id="laundry-room", pin=(60, 52), chapter="beyond", layout="side", slab="classic-silver", ar="3 / 2",
         title="Laundry &amp; <em>Mudroom</em>",
         text="The hardest-working room deserves a surface that shrugs off detergent, wet boots and folding marathons. "
              "A counter over the machines turns a laundry closet into a real workroom.",
         notes=["Run one counter over front-loaders for a full-length folding surface.",
                "Pick a patterned white. Fine veining hides lint and water marks.",
                "Blue-gray cabinets and black hardware forgive scuffs from everyday traffic."],
         edge="Eased, 3 cm", pairs="Blue-gray paint, matte black, terracotta tile",
         alt="Laundry room with blue-gray cabinets and Calacatta Classic Silver quartz counters over a washer and dryer"),
    dict(id="butlers-pantry", pin=(70, 48), chapter="beyond", layout="tall", flip=True, slab="lx-gold", ar="4 / 5",
         title="The Butler&rsquo;s <em>Pantry</em>",
         text="Between the kitchen and the dining room, a butler's pantry makes coffee in the morning and drinks at night. "
              "LX Gold with inky blue cabinets and bronze glass doors makes it feel like a small bar.",
         notes=["Quartz resists coffee rings, red wine and lemon, which is why it beats marble at a bar.",
                "Glass-front uppers show off glassware and keep a narrow room open.",
                "Take the slab up the back wall. Splashes wipe straight off."],
         edge="Eased, 3 cm", pairs="Inky blue, aged brass, dark bronze",
         alt="Butler's pantry with inky blue cabinets, glass-front uppers and a Calacatta LX Gold quartz counter and backsplash"),
    dict(id="fireplace-surround", pin=(50, 36), chapter="beyond", layout="side", slab="lx-supreme", ar="3 / 2",
         title="The Fireplace <em>Wall</em>",
         text="Quartz isn't only for kitchens and baths. A floor-to-ceiling LX Supreme surround with a floating hearth bench "
              "gives a modern fireplace the presence of carved marble.",
         notes=["Use quartz for the surround, not the firebox. Follow your fireplace's heat clearances.",
                "Book-match the slabs so the veining flows across the seams.",
                "A cantilevered hearth doubles as extra seating by the fire."],
         edge="Mitred hearth bench", pairs="White oak built-ins, boucle, wool",
         alt="Living room fireplace wall clad in Calacatta LX Supreme quartz with a floating hearth bench and oak shelves"),
]
