"""
Procedural room model for the FYP demo / thesis figures.

Builds a simple single-room scene with the three controlled appliances (light,
fan, TV) plus furniture that motivates the four activity profiles (bed -> B,
desk+chair -> A, open floor -> T/C) and a marker for the mounted-phone camera.
Objects are named so you can select and tweak them in Blender afterwards.

Run headless (no GUI needed):
    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python blender/room_model.py

Outputs (next to this script):
    room_model.blend     open + refine in Blender
    room_preview.png     quick render for slides / the dashboard

ponytail: primitives + flat colors only. Add real materials/lighting in the GUI
if a nicer render is needed - this is a layout, not an arch-viz.
"""

import os

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))


def reset_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                  bpy.data.cameras):
        for b in list(block):
            block.remove(b)


def mat(name, rgba):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
    return m


def box(name, loc, dims, rgba):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.active_object
    o.name = name
    o.dimensions = dims                      # (x, y, z) in metres
    o.data.materials.append(mat(name, rgba))
    return o


def cyl(name, loc, radius, depth, rgba):
    bpy.ops.mesh.primitive_cylinder_add(location=loc, radius=radius, depth=depth)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat(name, rgba))
    return o


# colours (RGBA 0-1)
GREY   = (0.80, 0.80, 0.80, 1)
WALL   = (0.90, 0.88, 0.84, 1)
BLUE   = (0.20, 0.35, 0.70, 1)
WOOD   = (0.55, 0.38, 0.22, 1)
BLACK  = (0.05, 0.05, 0.05, 1)
YELLOW = (1.00, 0.85, 0.30, 1)
WHITE  = (0.95, 0.95, 0.95, 1)
RED    = (0.80, 0.10, 0.10, 1)

ROOM_W, ROOM_D, ROOM_H = 5.0, 4.0, 2.8       # x, y, z metres


def build():
    reset_scene()

    # shell: floor, roof, back + two side walls. FRONT (-y) is left OPEN so the
    # interior is visible, like a doll's-house cutaway.
    box("Floor",      (0, 0, 0),                 (ROOM_W, ROOM_D, 0.05), GREY)
    box("Roof",       (0, 0, ROOM_H),            (ROOM_W, ROOM_D, 0.08), WALL)
    box("Wall_Back",  (0,  ROOM_D / 2, ROOM_H / 2), (ROOM_W, 0.05, ROOM_H), WALL)
    box("Wall_Left",  (-ROOM_W / 2, 0, ROOM_H / 2), (0.05, ROOM_D, ROOM_H), WALL)
    box("Wall_Right", ( ROOM_W / 2, 0, ROOM_H / 2), (0.05, ROOM_D, ROOM_H), WALL)

    # bed against the LEFT wall; a lying person faces +x toward the TV
    box("Bed",    (-1.75, 0, 0.30),   (1.2, 2.0, 0.5), BLUE)     # lying -> B
    box("Pillow", (-1.75, 0.80, 0.58), (1.0, 0.35, 0.18), WHITE)

    # desk + chair against the BACK wall; laptop on the desk -> sitting -> A
    box("Desk",       (1.3, 1.60, 0.75),  (1.3, 0.6, 0.06), WOOD)
    box("Desk_Leg_L", (0.75, 1.60, 0.37), (0.06, 0.5, 0.75), WOOD)
    box("Desk_Leg_R", (1.85, 1.60, 0.37), (0.06, 0.5, 0.75), WOOD)
    box("Chair",      (1.3, 0.95, 0.45),  (0.5, 0.5, 0.05), BLACK)
    box("Chair_Back", (1.3, 0.72, 0.70),  (0.5, 0.05, 0.5), BLACK)
    box("Laptop_Base",   (1.3, 1.60, 0.80), (0.34, 0.24, 0.02), BLACK)
    box("Laptop_Screen", (1.3, 1.73, 0.92), (0.34, 0.02, 0.22), BLACK)

    # --- the controlled appliances (pins 9/10/11 = light/fan/tv, + AC spare) ---
    # TV on the RIGHT wall, facing the bed so you can watch it lying down
    box("Appliance_TV", (ROOM_W / 2 - 0.05, 0, 1.30), (0.06, 1.1, 0.65), BLACK)
    # ceiling fan: hub + a blade bar
    cyl("Appliance_Fan", (0, 0, ROOM_H - 0.14), 0.18, 0.12, GREY)
    box("Appliance_Fan_Blade", (0, 0, ROOM_H - 0.16), (1.5, 0.18, 0.02), WHITE)
    # two ceiling lamps, each with a real light below it
    for i, x in enumerate((-1.2, 1.2)):
        box(f"Appliance_Light_{i + 1}", (x, -0.5, ROOM_H - 0.10),
            (0.35, 0.35, 0.10), YELLOW)
        bpy.ops.object.light_add(type="AREA", location=(x, -0.5, ROOM_H - 0.25))
        lamp = bpy.context.active_object
        lamp.data.energy, lamp.data.size = 120, 0.5
    # AC mounted high on the BACK wall
    box("Appliance_AC", (-1.2, ROOM_D / 2 - 0.13, 2.30), (0.9, 0.22, 0.35), WHITE)

    # camera-mount marker (mounted iPhone 12) in a front ceiling corner
    box("CameraMount", (ROOM_W / 2 - 0.15, -ROOM_D / 2 + 0.15, ROOM_H - 0.25),
        (0.12, 0.12, 0.12), RED)

    # interior fill + sun angled in through the open front
    bpy.ops.object.light_add(type="AREA", location=(0, 0, ROOM_H - 0.25))
    bpy.context.active_object.data.energy = 220
    bpy.context.active_object.data.size = 3.0
    bpy.ops.object.light_add(type="SUN", location=(0, -6, 5))
    bpy.context.active_object.data.energy = 2.5
    bpy.context.active_object.rotation_euler = (0.5, 0, 0)

    # camera at the open FRONT, looking in: sees the bed (left) and TV (right).
    # wide lens so the full 5 m-wide cutaway fits (ceiling fan/lamps + roof too).
    bpy.ops.object.empty_add(location=(0, 0.8, 1.4))
    target = bpy.context.active_object
    target.name = "CamTarget"
    bpy.ops.object.camera_add(location=(0, -5.6, 2.1))
    cam = bpy.context.active_object
    cam.data.lens = 20
    con = cam.constraints.new("TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    bpy.context.scene.camera = cam


def render():
    scene = bpy.context.scene
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.filepath = os.path.join(HERE, "room_preview.png")
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "room_model.blend"))
    render()
    print("wrote room_model.blend and room_preview.png in", HERE)
