// =====================================================================
// Yard Spike, parametric  (yard-spike-parametric.scad)  v5
// Prints standing up, connector down on the plate. No supports.
// Derivative of Cobo's "Configurable Spike" (CC BY-NC).
//
// Square or round connector, variable spine count and thickness,
// selectable tip profile. With Support_free on, no facet anywhere on
// the part overhangs more than 45 degrees, so nothing bridges and
// nothing needs support.
//
// PRINT NOTES
//   Material : PETG or ASA outdoors. PLA softens in sun, goes brittle.
//   Adhesion : tall part, small footprint, use a brim.
//   Walls    : the spine cross section is nearly all perimeter, so add
//              perimeters rather than infill. 4 to 5 is plenty.
//   Tip      : slow the last 15 mm so the tip has time to solidify.
//
// PRINT MODES
//   Support_free = true   every face stays within 45 degrees. Nothing
//                         bridges, nothing needs support, and the flutes
//                         ramp closed under the collar, tie band and grip
//                         rings. Costs about 3 percent more plastic on a
//                         bare spike, 5 to 7 with a tie band and rings.
//   Support_free = false  the original shape. The plates bridge the flutes,
//                         roughly 120 mm2 per plate at stock size, which
//                         most printers handle fine. Slightly lighter and
//                         the flutes run full length.
//
// CUSTOMIZER FIELDS
//   Every dimension carries a [min:step:max] range with a fractional step,
//   which is what makes the field accept decimals. OpenSCAD and MakerWorld
//   both decide int vs float from the value and step, not from how the
//   number is written, so a bare 15 gives a whole-numbers-only field.
//   Spines, Grip_rings and Roundness stay integer on purpose: they are
//   counts. A 0 in Spine_thickness or Core_diameter means "work it out
//   from Connector_size".
//
// THE ORIGINAL SHAPE
//   Support_free=false, Spines=4, Spine_thickness=0, Spine_rotation=45,
//   Tip_style="cone", Lead_in_chamfer=0, Collar_fillet=0, Tie_band=false,
//   Grip_rings=0, Screw_hole=0 reproduces Cobo's model. Add Roundness=8,
//   which matches the faceting the original gets from OpenSCAD's defaults,
//   and the two meshes agree to the triangle. There is a saved preset for it.
// =====================================================================

include <BOSL2/std.scad>

/* [Fit] */
// What the spike plugs into
Connector_shape = "square"; // [square:Square post, circle:Round tube]
// mm. Across the flats for a square post, the diameter for round tube. Measure the INSIDE of the tube.
Connector_size = 15; // [4:0.05:120]
// mm. How far the connector reaches into the post or tube.
Connector_depth = 15; // [4:0.05:80]
// mm. Shrinks the connector alone for a slip fit. 0.2 to 0.4 suits most tubing.
Fit_clearance = 0; // [0:0.01:3]

/* [Printing] */
// Keeps every face within 45 degrees, so nothing bridges and nothing needs support. Off is the original shape.
Support_free = true;
// mm. Chamfer on the leading end so the connector starts into a tube easily.
Lead_in_chamfer = 0.8; // [0:0.05:8]
// mm. Solid pad at the leading end. Your bed contact, and the strike face if you tap the spike in.
End_cap_thickness = 2; // [0.4:0.05:15]
// Facets on round features. Higher is smoother and slower to render.
Roundness = 64; // [8:1:256]

/* [Spike] */
// mm. Total length from the underside of the collar to the point, collar included.
Spike_length = 107; // [24:0.05:400]
// mm. Straight section between the collar and the start of the taper.
Spike_base_length = 5; // [0:0.05:60]
// Ridges running the length of the spike. 0 makes it solid. 2 to 8 is the useful range.
Spines = 4; // [0:1:16]
// mm. Thickness of each spine across the flats. 0 uses the stock proportion.
Spine_thickness = 0; // [0:0.05:30]
// degrees. Rotates the spine pattern. 45 puts four spines on the corners of a square connector.
Spine_rotation = 45; // [0:0.5:360]
// mm. Central rod the spines hang off and the tip grows from. 0 means one third of Connector_size.
Core_diameter = 0; // [0:0.05:60]

/* [Tip] */
// Cone is the stock taper. Ogive is a bullet nose, stiffer behind the point. Chisel ends on an edge and is the toughest.
Tip_style = "cone"; // [cone:Cone, ogive:Ogive, chisel:Chisel]
// mm. Length of the tip section. Longer is pointier.
Tip_length = 15; // [1:0.05:90]
// mm. Diameter at the point, or edge thickness for the chisel. Under 1.5 is fragile on a 0.4 nozzle.
Tip_diameter = 2; // [0.4:0.05:30]

/* [Grip] */
// Solid band across the middle of the connector. Ties the spines together so they cannot splay.
Tie_band = true;
// mm. Thickness of that band. Grows on its own if it has to carry a screw hole.
Tie_band_thickness = 2; // [0.4:0.05:30]
// Rings that stand proud of the connector and bite the tube wall. 0 turns them off.
Grip_rings = 0; // [0:1:8]
// mm. How far each ring stands proud. Real interference is this minus Fit_clearance.
Grip_ring_height = 0.3; // [0:0.01:3]
// mm. Thickness of each ring, measured along the spike.
Grip_ring_thickness = 1.6; // [0.4:0.05:15]
// mm. Cross hole through the tie band for a screw or nail through the tube wall. 0 turns it off.
Screw_hole = 0; // [0:0.05:20]

/* [Collar] */
// mm. Thickness of the collar plate that stops against the end of the post or tube.
Collar_thickness = 2; // [0.4:0.05:20]
// mm. How far the collar stands proud of the connector, per side.
Collar_lip = 1; // [0:0.05:20]
// mm. Fillet where the spike meets the collar. Highest stress point on the part.
Collar_fillet = 1; // [0:0.05:20]

/* [Hidden] */
$fn = Roundness;

// ---- derived -------------------------------------------------------
Is_round     = (Connector_shape == "circle");
Plug         = Connector_size - Fit_clearance;
Core         = Core_diameter > 0 ? Core_diameter : Connector_size / 3;
Spine_w      = Spine_thickness > 0 ? Spine_thickness : sqrt(2) * (Core / 2 - 0.5);
Taper_top    = Connector_size / 5;
Collar_out   = Connector_size + 2 * max(Collar_lip, Collar_fillet);
// Chamfer has to reach the ACTUAL plug face, not nominal Connector_size, or a
// clearance fit leaves an unsupported ledge under the collar.
Collar_step  = (Collar_out - Plug) / 2;
Collar_h     = Support_free ? max(Collar_thickness, 2 * Collar_step) : Collar_thickness;
Collar_ch    = min(Collar_step, Collar_h / 2);
Fillet       = min(Collar_fillet, max(Collar_lip, Collar_fillet));
Core_height  = Spike_length - Collar_h - Tip_length;
Taper_height = Core_height - Spike_base_length - 1;
Band_height  = Screw_hole > 0 ? max(Tie_band_thickness, Screw_hole + 2.4) : Tie_band_thickness;
Band_z       = Connector_depth / 2;
Grip_ring_size     = Plug + 2 * Grip_ring_height;
Total_h      = Connector_depth + Spike_length;
Weld         = min(0.05, Collar_h / 4);  // overlap at the collar joints
Reach        = Connector_size * 3;
Tip_angle    = 2 * atan((Core - Tip_diameter) / 2 / Tip_length);

if (Collar_h > Collar_thickness)
    echo(str("NOTE: collar thickened from ", Collar_thickness, " to ", Collar_h,
             " mm so its underside stays fully supported at this clearance."));
echo(str("Tip included angle: ", Tip_angle, " deg   Spine thickness: ", Spine_w, " mm   Core: ", Core, " mm"));

// ---- guards --------------------------------------------------------
assert(Connector_size > 0, "Connector_size must be greater than 0.");
assert(Plug > 2, str("Fit_clearance (", Fit_clearance, ") is too large for Connector_size (", Connector_size, ")."));
assert(Connector_depth > End_cap_thickness + Band_height + 1,
       str("Connector_depth (", Connector_depth, ") is too short for End_cap_thickness + Tie_band_thickness. Raise Connector_depth or lower them."));
assert(Taper_height > 0,
       str("Spike_length (", Spike_length, ") is too short. It must be more than Collar_thickness + Spike_base_length + Tip_length + 1 = ",
           Collar_h + Spike_base_length + Tip_length + 1, "."));
assert(Spines != 1, "Spines must be 0 for a solid spike, or 2 or more.");
assert(Spine_w > 0.8, str("Spine_thickness (", Spine_w, ") is thinner than a sane extrusion. Raise it or raise Core_diameter."));
assert(Spine_w < Connector_size, "Spine_thickness cannot exceed Connector_size.");
assert(Tip_diameter < Core, str("Tip_diameter must be under the core diameter (", Core, ")."));
assert(Tip_length > 0, "Tip_length must be greater than 0.");
assert(Lead_in_chamfer < Connector_depth / 2, "Lead_in_chamfer is too large for Connector_depth.");
assert(Grip_ring_thickness > 2 * Grip_ring_height, "Grip_ring_thickness must be more than twice Grip_ring_height.");
assert(Screw_hole == 0 || Tie_band, "Screw_hole needs Tie_band turned on, it is drilled through the band.");
assert(Screw_hole < Plug / 2, "Screw_hole is too large for the connector.");

// ---- build ---------------------------------------------------------
difference() {
    spike();
    if (Screw_hole > 0)
        up(-Connector_depth / 2 + Band_z)
            teardrop(d = Screw_hole, l = Reach);
}

// Built from the leading end up, then dropped so the connector centre
// sits on the origin, same placement as the earlier versions.
module spike() {
    down(Connector_depth / 2)
    union() {
        if (Spines > 0)
            intersection() {
                fluted_part();
                spine_mask();
            }
        else
            fluted_part();

        collar();
        core_and_tip();

        if (Spines > 0 && Tie_band)
            up(Band_z) prism(Plug, Band_height);

        if (Grip_rings > 0)
            for (i = [1 : Grip_rings])
                up(Connector_depth * i / (Grip_rings + 1) - Grip_ring_thickness / 2)
                    prism(Grip_ring_size, Grip_ring_thickness, chamfer1 = Grip_ring_height, chamfer2 = Grip_ring_height);
    }
}

// Everything the spines get cut out of: connector, base, taper.
module fluted_part() {
    prism(Plug, Connector_depth, chamfer1 = Lead_in_chamfer);
    // Base starts a hair inside the collar for the same welding reason.
    up(Connector_depth + Collar_h - Weld) {
        prism(Connector_size, Spike_base_length + Weld, rounding1 = -Fillet);
        up(Spike_base_length + Weld) taper(Connector_size, Taper_top, Taper_height);
    }
}

// Keeps the solid cap at the leading end, plus one blade per spine.
module spine_mask() {
    prism(Reach, End_cap_thickness);
    for (i = [0 : Spines - 1])
        zrot(Spine_rotation + i * 360 / Spines)
            cuboid([Reach, Spine_w, Total_h + 2], anchor = LEFT + BOTTOM);

    // Every horizontal plate needs solid material under it or it bridges
    // the flutes. These 45 degree ramps close the flutes just below each one.
    if (Support_free) {
        ramp(Connector_depth);
        if (Tie_band) ramp(Band_z);
        if (Grip_rings > 0)
            for (i = [1 : Grip_rings])
                ramp(Connector_depth * i / (Grip_rings + 1) - Grip_ring_thickness / 2);
    }
}

// Cone or pyramid flaring up to full plug size at top_z, walls at 45 deg.
module ramp(top_z) {
    h = Plug / 2;
    up(top_z - h) taper(0.01, Plug, h);
    // carry on at full size a hair past the plate, so the two solids
    // overlap instead of meeting on exactly one plane
    up(top_z) prism(Plug, Weld);
}

module collar() {
    up(Connector_depth) prism(Collar_out, Collar_h, chamfer1 = Collar_ch);
}

// The core runs a little way down into the collar. That weld keeps the
// union of collar, spines and core a single solid whatever the collar
// thickness works out to. It is entirely inside the collar, so it does
// not change a single outside surface.
module core_and_tip() {
    up(Connector_depth + Collar_h - Weld) {
        cyl(d = Core, h = Core_height + Weld, anchor = BOTTOM);
        up(Core_height + Weld) tip();
    }
}

// cone   straight taper, the stock profile. Sharpest for a given length.
// ogive  bullet nose. Same length and point diameter, more section behind
//        the point, so stiffer, but the last few mm are blunter.
// chisel wedge. Ends on an edge, so the final layer has roughly 3x the
//        area of a cone point, which is the usual FDM failure spot.
module tip() {
    R  = Core / 2;
    rt = Tip_diameter / 2;
    if (Tip_style == "ogive")
        rotate_extrude() polygon(concat([[0, 0]], ogive_profile(R, rt, Tip_length), [[0, Tip_length]]));
    else if (Tip_style == "chisel")
        hull() {
            cyl(d = Core, h = 0.02, anchor = BOTTOM);
            up(Tip_length - 0.02) cuboid([Core, Tip_diameter, 0.02], anchor = BOTTOM);
        }
    else
        cyl(d1 = Core, d2 = Tip_diameter, h = Tip_length, anchor = BOTTOM);
}

// Tangent ogive: arc leaves the core vertically and lands on the point.
function ogive_profile(R, rt, L, n = 32) =
    let(
        a   = R - rt,
        rho = (a * a + L * L) / (2 * a),
        cx  = R - rho
    )
    [for (i = [0 : n]) let(z = L * i / n) [max(cx + sqrt(max(rho * rho - z * z, 0)), 0), z]];

// Straight section, square or round, sitting on z = 0.
// A negative rounding1 makes an outward fillet at the bottom.
module prism(size, h, chamfer1 = 0, rounding1 = 0, chamfer2 = 0) {
    c1 = chamfer1 == 0 ? undef : chamfer1;
    c2 = chamfer2 == 0 ? undef : chamfer2;
    r1 = rounding1 == 0 ? undef : rounding1;
    if (Is_round)
        cyl(d = size, h = h, chamfer1 = c1, chamfer2 = c2, rounding1 = r1, anchor = BOTTOM);
    else if (r1 != undef)
        cuboid([size, size, h], rounding = r1, edges = BOTTOM, anchor = BOTTOM);
    else if (c1 != undef && c2 != undef)
        cuboid([size, size, h], chamfer = c1, edges = [TOP, BOTTOM], anchor = BOTTOM);
    else if (c1 != undef)
        cuboid([size, size, h], chamfer = c1, edges = BOTTOM, anchor = BOTTOM);
    else
        cuboid([size, size, h], anchor = BOTTOM);
}

// Tapered section, cone or pyramid, sitting on z = 0.
module taper(size1, size2, h) {
    if (Is_round)
        cyl(d1 = size1, d2 = size2, h = h, anchor = BOTTOM);
    else
        prismoid(size1 = [size1, size1], size2 = [size2, size2], h = h, anchor = BOTTOM);
}
