r"""Can the player really walk through every doorway / up every step?  Starts PIE once, teleports the pawn in front of each
passage, holds 'move forward' and measures how far it got.  UE 5.9+ (InputToolset.ApplyInput, Enhanced Input).

  python ue_walk_check.py <tests.json> [--action /Game/Input/Actions/IA_Move.IA_Move] [--secs 1.2] [--min 1.5]

tests.json (model metres; model (x, y, z) -> UE (100 x, -100 y, 100 z)):
  [{"id": "west door", "start": [x, y, z], "head": [hx, hy], "alt": [x, y, z]}, ...]
  start = about 1 m before the passage, z = floor + 1 m (the pawn drops onto the floor); head = walking direction;
  alt (optional) = start on the far side, tried with the opposite heading when the first try fails (the first start
  may sit on furniture; stepping down always works, stepping up may exceed the step height).
Pass = advanced at least --min metres along the heading.  Generate the list from the model's parameters (every door bay
of every wall); for sliding doors of 2 / 4 leaves aim at the centre of the OPEN half, not of the bay.
The level must be open and not in PIE; PIE is stopped at the end."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue_py import call, run
TP = '''
import math
gw = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(); p = unreal.GameplayStatics.get_player_pawn(gw, 0)
x, y, z, hx, hy = @ARGS@
p.set_actor_location(unreal.Vector(100 * x, -100 * y, 100 * z), False, True); yaw = math.degrees(math.atan2(-hy, hx))
p.get_controller().set_control_rotation(unreal.Rotator(roll=0, pitch=-10, yaw=yaw)); p.character_movement.set_editor_property("velocity", unreal.Vector(0, 0, 0))
True
'''
POS = '''
gw = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(); l = unreal.GameplayStatics.get_player_pawn(gw, 0).get_actor_location()
[round(l.x / 100, 2), round(-l.y / 100, 2), round(l.z / 100, 2)]
'''
if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    def opt(name, default):
        if name in a:
            i = a.index(name); v = a[i + 1]; del a[i:i + 2]; return v
        return default
    action = opt("--action", "/Game/Input/Actions/IA_Move.IA_Move"); secs = float(opt("--secs", 1.2)); need = float(opt("--min", 1.5))
    tests = json.load(open(a[0], encoding="utf-8"))
    def walk(start, head):
        run(TP.replace("@ARGS@", repr((*start, *head)))); time.sleep(0.8); p0 = run(POS)
        call("InputToolset.InputToolset", "ApplyInput", {"entries": [{"action": {"refPath": action}, "value": {"x": 0, "y": 1, "z": 0}}], "durationSeconds": secs})
        time.sleep(0.4); p1 = run(POS); return p0, p1, (p1[0] - p0[0]) * head[0] + (p1[1] - p0[1]) * head[1]
    try: call("EditorToolset.EditorAppToolset", "StopPIE", {})
    except Exception: pass
    call("EditorToolset.EditorAppToolset", "StartPIE", {}); time.sleep(2); res = []
    try:
        for t in tests:
            p0, p1, adv = walk(t["start"], t["head"]); ok = adv >= need
            if not ok and t.get("alt"): p0, p1, adv = walk(t["alt"], (-t["head"][0], -t["head"][1])); ok = adv >= need
            res.append(ok); print("%-22s %s -> %s  advance %.2f  %s" % (t["id"], p0, p1, adv, "ok" if ok else "BLOCKED"), flush=True)
    finally:
        call("EditorToolset.EditorAppToolset", "StopPIE", {})
    print("passed %d of %d" % (sum(res), len(res)))
