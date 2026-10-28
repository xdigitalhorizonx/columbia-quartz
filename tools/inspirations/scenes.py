"""Scene prompts for the Inspirations page.

    python tools/inspirations/scenes.py jobs.json [takes] [id,id,...]

Writes a job list for generate.py (Nano Banana Pro, real slab photo as the stone reference)."""
import json, sys

STYLE = ("Light: {light} All ceiling lights, pendants and sconces are switched off; natural falloff into the corners, realistic soft shadows. "
         "Camera: full-frame DSLR, {lens} lens, vertical lines kept straight, f/8, deep focus, neutral white balance, true-to-life muted color, fine natural sensor grain. "
         "It must look like an unretouched real photograph taken by a professional interior photographer for a remodeling portfolio, not a 3D render: "
         "no glowing lights, no lens flare, no shallow-depth bokeh, no oversaturation, no warm orange grading, no perfectly symmetrical staging, no people, no text, no logos, no brand names.")

SCENES = {
 "farmhouse-kitchen": dict(slab="classic-gold", ar="3:2", lens="24mm at chest height",
   light="soft overcast daylight from the window on the left.",
   body="Interior photograph of a real, recently remodeled family kitchen in a 1920s house. "
        "The large kitchen island and the perimeter countertops are polished engineered quartz that exactly matches the stone in the reference image: a white ground with fine, branching warm-gold and beige veins. "
        "Island counter is 3 cm thick with an eased square edge; three simple oak counter stools with woven rush seats are tucked under the overhang. "
        "Cabinets are inset shaker doors painted a soft warm white, with unlacquered brass knobs and cup pulls that have a slight patina. "
        "Wide-plank white oak floor, a vintage runner rug in faded rust and indigo, a farmhouse fireclay sink under a window with simple linen cafe curtains. "
        "Lived-in, restrained styling: a well-used end-grain cutting board, a ceramic crock of wooden spoons near the range, a bowl of pears, a folded tea towel over the oven handle."),
 "after-dark-kitchen": dict(slab="steel", ar="16:9", lens="24mm at chest height, standing a little to the right of the island",
   light="soft overcast daylight from a big window wall on the left on a grey rainy day; low-key, moody exposure with deep but readable shadows.",
   body="Interior photograph of a real, recently completed modern kitchen in a contemporary Pacific Northwest home. "
        "Matte black flat-panel cabinetry with slim recessed finger pulls runs full height along the back wall, including a panelled refrigerator. "
        "A long island with a mitred waterfall end, and a full-height backsplash slab behind the cooktop, both in polished engineered quartz that exactly matches the stone in the reference image: a bright white ground with soft, broad, cool-gray linear veins. "
        "On the waterfall end the veins continue unbroken from the top surface down across the mitred corner. "
        "Wide smoked-oak floor planks, three counter stools in black leather with walnut legs, a matte black faucet, dark fir trees outside the window. "
        "Sparse styling: two stacked stoneware plates, a glass carafe of water, a stoneware jug with a few eucalyptus stems."),
 "quiet-minimal-kitchen": dict(slab="lx-classic", ar="3:2", lens="35mm at counter height",
   light="soft, diffused north-facing daylight from a large window on the right.",
   body="Interior photograph of a calm minimalist kitchen in a renovated city loft. "
        "Handleless rift-sawn white oak cabinetry with flush doors and a shadow-gap toe kick. "
        "A thin 2 cm countertop and a full-height backsplash in polished engineered quartz that exactly matches the stone in the reference image: a soft warm white with only very faint, misty gray veining, so it reads almost solid. "
        "An undermount sink with a slim brushed-steel faucet, warm gray microcement floor, white lime-plaster walls, one open oak niche holding three handmade stoneware cups. "
        "Very little on the counter: a turned wooden bowl with two lemons, a ceramic oil bottle, a folded linen tea towel."),
 "estate-kitchen": dict(slab="lx-supreme", ar="4:5", lens="35mm, camera placed slightly off-center to the right of the range",
   light="daylight from a tall window just out of frame on the left, gentle and directional.",
   body="Interior photograph of a classic, formal kitchen in a large traditional house. "
        "A range alcove: a cream plaster range hood with a gently curved base above a professional range with a deep navy enamel finish and brass knobs. "
        "Behind the range, a single full-height backsplash slab, and the countertops on both sides, in polished engineered quartz that exactly matches the stone in the reference image: a white ground with soft, cloudy gray movement and fine darker gray veins, like Statuario marble. "
        "Inset cabinetry painted a soft French gray-green, polished nickel bin pulls and latches, glass-front upper cabinets holding white ironstone pitchers. "
        "Herringbone oak floor. Lived-in details: a copper saucepan on a burner, a marble mortar with a pestle, a small bunch of rosemary on the counter."),
 "city-galley-kitchen": dict(slab="classic-silver", ar="4:5", lens="24mm, standing at the open end of the galley looking down its length",
   light="daylight from the window at the far end of the galley.",
   body="Interior photograph of a narrow galley kitchen in a renovated pre-war city apartment with a high ceiling and original crown molding. "
        "Lower cabinets on both sides painted deep sage green with slim brass bar pulls; on the left wall, open walnut shelves with everyday white dishes and drinking glasses. "
        "The countertops are polished engineered quartz that exactly matches the stone in the reference image: a white ground with fine, parallel, linear gray veins; the veins run along the length of the counters. "
        "A tall double-hung window at the far end with an old cast-iron radiator below it. Small white hexagon mosaic floor with a little original wear. "
        "Lived-in styling: a moka pot on the gas stove, a bowl of clementines, a small vintage radio, a dish rack with two drying glasses."),
 "coastal-kitchen": dict(slab="classic-pearl", ar="3:2", lens="28mm at chest height",
   light="pale, hazy coastal morning daylight from a large window, soft and cool.",
   body="Interior photograph of a light, relaxed kitchen in a coastal Northern California house. "
        "Simple slab-door cabinets in limed white oak, two open shelves of pale handmade ceramics, warm-white limewash walls with visible brush texture. "
        "Countertops and a short 10 cm backsplash ledge are polished engineered quartz that exactly matches the stone in the reference image: a warm greige-taupe ground with soft, cloudy, subtle veining. "
        "A deep apron sink with an unlacquered brass bridge faucet, a window that looks onto dune grass under a gray sky, pale oak floor. "
        "Styling: a sourdough loaf on a linen-covered board, a bowl of figs, a stoneware pitcher of dried grasses."),
 "midcentury-kitchen": dict(slab="lx-noir", ar="16:9", lens="24mm at chest height",
   light="soft daylight through tall glass doors to a garden on the left.",
   body="Interior photograph of a mid-century modern kitchen renovation in a 1960s post-and-beam house. "
        "Walnut slab-front cabinets with long, slim walnut pulls, a tongue-and-groove wood ceiling with exposed beams, a row of clerestory windows, a warm terrazzo floor. "
        "A long island and the perimeter counters are polished engineered quartz that exactly matches the stone in the reference image: a bright white ground with bold, thick charcoal-black veins with soft gray edges, very dramatic. "
        "Two molded plywood counter stools. Restrained styling: a teak serving bowl, a glass vase with a single olive branch, a stack of cookbooks."),
 "primary-bath": dict(slab="classic-arctic", ar="3:2", lens="24mm at chest height",
   light="soft morning daylight from a window with sheer linen curtains on the right.",
   body="Interior photograph of a calm, recently remodeled primary bathroom. "
        "A long floating double vanity in fluted white oak, with a 3 cm polished engineered quartz top and a full-height quartz slab wall behind it, both exactly matching the stone in the reference image: a bright white ground with thin, sharp, dark-gray hairline veins. "
        "Two rectangular undermount sinks, wall-mounted brushed nickel faucets, two round mirrors with thin metal frames. "
        "Pale limewash walls, large-format warm stone-look floor tile, the end of a freestanding white tub just visible at the right edge. "
        "Styling: a rolled white towel, a small amber glass bottle, one stem of greenery in a bud vase."),
 "powder-room": dict(slab="lx-gold", ar="4:5", lens="28mm, standing in the doorway, camera slightly to the left of center",
   light="soft daylight from a small frosted window on the right side wall.",
   body="Interior photograph of a small jewel-box powder room in a renovated older home. "
        "A floating vanity box built entirely from polished engineered quartz slab with mitred corners, exactly matching the stone in the reference image: a white ground with fine warm champagne-gold and taupe veins that wrap continuously around the mitred corners. "
        "An undermount oval sink and a wall-mounted unlacquered brass faucet. "
        "Walls in deep forest-green lime plaster with visible trowel texture, an antique round mirror in a thin brass frame, a brass wall sconce, a linen hand towel on a brass ring. "
        "Floor of small black-and-white marble basketweave mosaic."),
 "spa-shower": dict(slab="classic-supreme", ar="4:5", lens="24mm, shot from outside the glass panel",
   light="soft daylight from a high horizontal window inside the shower.",
   body="Interior photograph of a walk-in shower in a remodeled primary bathroom. "
        "The shower walls are lined with large polished engineered quartz slabs with only one or two tight seams, exactly matching the stone in the reference image: a white ground with soft gray web-like veining. "
        "A floating built-in bench and a long horizontal wall niche made from the same quartz. "
        "Curbless entry with a linear drain, a fixed frameless clear glass panel, a brushed brass rain head and thermostatic valve, floor in small matte gray mosaic tile. "
        "A folded waffle towel on the bench; a bar of soap and a glass bottle in the niche."),
 "laundry-room": dict(slab="classic-silver", ar="3:2", lens="24mm at chest height",
   light="daylight from a window above the utility sink.",
   body="Interior photograph of a hardworking laundry and mudroom in a family home. "
        "A front-load washer and dryer side by side under a continuous polished engineered quartz countertop used for folding, which, along with the countertop over the sink cabinet, exactly matches the stone in the reference image: a white ground with fine, parallel, linear gray veins. "
        "A deep undermount stainless utility sink with a matte black bridge faucet, cabinets painted a muted blue-gray with black cup pulls, terracotta tile floor. "
        "Wall hooks holding a canvas tote and a dog leash; a wicker basket of folded towels on the counter, a bottle of detergent in amber glass."),
 "butlers-pantry": dict(slab="lx-gold", ar="4:5", lens="28mm at chest height",
   light="soft daylight from a doorway on the left.",
   body="Interior photograph of a butler's pantry and coffee station between a kitchen and a dining room in a traditional house. "
        "Glass-front upper cabinets with thin dark-bronze frames holding stemware and coffee cups, lower cabinets painted deep inky blue with aged brass knobs. "
        "The countertop and a full-height backsplash are polished engineered quartz that exactly matches the stone in the reference image: a white ground with fine warm champagne-gold and taupe veins. "
        "A small bar sink with a brass faucet, a plain unbranded stainless espresso machine, a wooden tray holding a glass decanter, a bowl of lemons. Dark stained oak floor."),
 "fireplace-surround": dict(slab="lx-supreme", ar="3:2", lens="28mm at seated eye height",
   light="soft afternoon daylight from two windows on the right.",
   body="Interior photograph of a living room in a renovated contemporary home, focused on the fireplace wall. "
        "A clean modern fireplace opening framed by a floor-to-ceiling surround and a low cantilevered hearth bench in polished engineered quartz that exactly matches the stone in the reference image: a white ground with soft, cloudy gray movement and fine darker gray veins; the veins flow continuously across the slab joints. "
        "The fire is not lit. Built-in white oak shelves on both sides with a few books and ceramics, a cream boucle sofa partly in frame, a wool rug, a stack of split birch logs beside the hearth."),
}

if __name__ == "__main__":
    takes = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    only = sys.argv[3].split(",") if len(sys.argv) > 3 else None
    jobs = []
    for sid, s in SCENES.items():
        if only and sid not in only:
            continue
        prompt = s["body"] + " " + STYLE.format(light=s["light"], lens=s["lens"])
        for t in range(takes):
            jobs.append({"id": f"{sid}-{t + 1}", "model": "google/nano-banana-pro",
                         "input": {"prompt": prompt, "image_input": [f"@slab:{s['slab']}"],
                                   "aspect_ratio": s["ar"], "resolution": "2K", "output_format": "png"}})
    json.dump(jobs, open(sys.argv[1], "w"), indent=1)
    print(len(jobs), "jobs")
