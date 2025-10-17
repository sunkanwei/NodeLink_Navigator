import bpy, gpu, ctypes
from gpu_extras.batch import batch_for_shader
from math import sin, cos, pi, sqrt
from collections import deque
from itertools import chain
from .lang_dict import LANG_DICT

from .colors import get_node_border_color

def _tri_strip_polyline(pts, width):
    n = len(pts)
    if n < 2:
        return None
    hw = width * 0.5
    out = []
    for i in range(n):
        if i == 0:
            x0, y0 = pts[0]; x1, y1 = pts[1]
            tx, ty = x1 - x0, y1 - y0
        elif i == n - 1:
            x0, y0 = pts[-2]; x1, y1 = pts[-1]
            tx, ty = x1 - x0, y1 - y0
        else:
            x0, y0 = pts[i - 1]; x1, y1 = pts[i + 1]
            tx, ty = x1 - x0, y1 - y0
        L = (tx * tx + ty * ty) ** 0.5 or 1.0
        nx, ny = -ty / L * hw, tx / L * hw
        x, y = pts[i]
        out.extend([(x - nx, y - ny), (x + nx, y + ny)])
    return out

def _tri_strip_polygon(pts, width):
    n = len(pts)
    if n < 3:
        return None
    hw = width * 0.5
    out = []
    for i in range(n):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[(i + 1) % n]
        tx, ty = x1 - x0, y1 - y0
        L = (tx * tx + ty * ty) ** 0.5 or 1.0
        nx, ny = -ty / L * hw, tx / L * hw
        x, y = pts[i]
        out.extend([(x - nx, y - ny), (x + nx, y + ny)])
    return out


line_thickness = 2.0

class StructBase(ctypes.Structure):
    _subclasses=[]; __annotations__={}
    def __init_subclass__(cls): cls._subclasses.append(cls)
    @staticmethod
    def _init_structs():
        ft=type(lambda:None)
        for cls in StructBase._subclasses:
            fields=[]
            for k,v in cls.__annotations__.items():
                if isinstance(v,ft): v=v()
                fields.append((k,v))
            if fields: cls._fields_=fields
            cls.__annotations__.clear()
        StructBase._subclasses.clear()

class BNodeSocketRuntimeHandle(StructBase):
    _pad0: ctypes.c_char*8; declaration: ctypes.c_void_p; changed_flag: ctypes.c_uint32
    total_inputs: ctypes.c_short; _pad1: ctypes.c_char*2; location: ctypes.c_float*2
class BNodeStack(StructBase):
    vec: ctypes.c_float*4; min: ctypes.c_float; max: ctypes.c_float
    data: ctypes.c_void_p; hasinput: ctypes.c_short; hasoutput: ctypes.c_short
    datatype: ctypes.c_short; sockettype: ctypes.c_short; is_copy: ctypes.c_short
    external: ctypes.c_short; _pad: ctypes.c_char*4
class BNodeSocket(StructBase):
    next: ctypes.c_void_p; prev: ctypes.c_void_p; prop: ctypes.c_void_p
    identifier: ctypes.c_char*64; name: ctypes.c_char*64; storage: ctypes.c_void_p
    in_out: ctypes.c_short; typeinfo: ctypes.c_void_p; idname: ctypes.c_char*64
    default_value: ctypes.c_void_p; _pad: ctypes.c_char*4; label: ctypes.c_char*64
    description: ctypes.c_char*64; short_label: ctypes.c_char*64
    default_attribute_name: ctypes.POINTER(ctypes.c_char); to_index: ctypes.c_int
    link: ctypes.c_void_p; ns: BNodeStack; runtime: ctypes.POINTER(BNodeSocketRuntimeHandle)
StructBase._init_structs()

def rounded_rect(l,b,r,t,rad,seg=8):
    v=[]
    for i in range(seg+1): a=-pi/2+(i/seg)*(pi/2);v.append((r-rad+cos(a)*rad,b+rad+sin(a)*rad))
    for i in range(seg+1): a=(i/seg)*(pi/2);v.append((r-rad+cos(a)*rad,t-rad+sin(a)*rad))
    for i in range(seg+1): a=pi/2+(i/seg)*(pi/2);v.append((l+rad+cos(a)*rad,t-rad+sin(a)*rad))
    for i in range(seg+1): a=pi+(i/seg)*(pi/2);v.append((l+rad+cos(a)*rad,b+rad+sin(a)*rad))
    v.append(v[0]);return v

def get_node_bounds_px(node,v2d,ui):
    ax, ay = node.location.x, node.location.y; p = node.parent
    while p: ax += p.location.x; ay += p.location.y; p = p.parent
    min_x = ax * ui; max_x = min_x + node.dimensions.x; max_y = ay * ui; min_y = max_y - node.dimensions.y
    x1, y1 = v2d.view_to_region(min_x, min_y, clip=False); x2, y2 = v2d.view_to_region(max_x, max_y, clip=False)
    l, r = sorted((x1, x2)); b, t = sorted((y1, y2))
    if node.hide: offset = -6 * ui; t -= offset; b -= offset
    return l, b, r, t

def get_socket_pos_px(self, socket, v2d):
    ptr = socket.as_pointer()
    if ptr in self._sock_cache: return self._sock_cache[ptr]
    pos = None
    try:
        if socket.enabled:
            s = BNodeSocket.from_address(ptr)
            if s.runtime:
                loc = s.runtime.contents.location
                pos = v2d.view_to_region(loc[0], loc[1], clip=False)
    except: pass
    self._sock_cache[ptr] = pos
    return pos

def bezier_verts_from_link(link, v2d, ui_scale):
    fs, ts = link.from_socket, link.to_socket
    try:
        if not (fs.enabled and ts.enabled): return None
        s_from = BNodeSocket.from_address(fs.as_pointer())
        s_to = BNodeSocket.from_address(ts.as_pointer())
        if not (s_from.runtime and s_to.runtime): return None
        loc_from, loc_to = s_from.runtime.contents.location, s_to.runtime.contents.location
        x1_view, y1_view, x2_view, y2_view = loc_from[0], loc_from[1], loc_to[0], loc_to[1]
    except: return None
    dx_view = x2_view - x1_view; dy_view = y2_view - y1_view
    try: curveness = bpy.context.preferences.themes[0].node_editor.noodle_curving / 10.0
    except: curveness = 0.5
    handle_dist_view = dx_view * curveness if dx_view >= 0 else sqrt(dx_view**2 + dy_view**2) * curveness
    p0, p1 = (x1_view, y1_view), (x1_view + handle_dist_view, y1_view)
    p2, p3 = (x2_view - handle_dist_view, y2_view), (x2_view, y2_view)
    approx_len = abs(dx_view) + abs(dy_view)
    segs = max(8, min(64, int(approx_len / 15)))
    view_verts = [None] * (segs + 1)
    for i in range(segs + 1):
        t = i / float(segs); inv_t = 1.0 - t
        a=inv_t**3; b=3*inv_t**2*t; c=3*inv_t*t**2; d=t**3
        x = a*p0[0] + b*p1[0] + c*p2[0] + d*p3[0]
        y = a*p0[1] + b*p1[1] + c*p2[1] + d*p3[1]
        view_verts[i] = (x, y)
    v2r = v2d.view_to_region
    return [v2r(p[0], p[1], clip=False) for p in view_verts]

def collect_full_path_info(start_socket):
    links, targets = set(), set()
    if not start_socket: return links, targets, None
    current_socket, visited_sockets = start_socket, {start_socket}
    while True:
        if not current_socket.is_output:
            if current_socket.is_linked: current_socket = current_socket.links[0].from_socket
            else: break
        if current_socket.node.bl_idname == 'NodeReroute':
            reroute_input = current_socket.node.inputs[0]
            if reroute_input.is_linked:
                next_socket = reroute_input.links[0].from_socket
                if next_socket in visited_sockets: break
                visited_sockets.add(next_socket); current_socket = next_socket
            else: break
        else: break
    ultimate_source_socket, ultimate_source_node = current_socket, current_socket.node
    q, visited_downstream = deque([ultimate_source_socket]), set()
    while q:
        s = q.popleft()
        if s in visited_downstream: continue
        visited_downstream.add(s)
        for lk in s.links:
            links.add(lk); ts = lk.to_socket
            if ts.node.bl_idname == 'NodeReroute':
                if ts.node.outputs: q.append(ts.node.outputs[0])
            else: targets.add(ts.node)
    return links, targets, ultimate_source_node

def find_ultimate_source(input_socket):
    if not input_socket.is_linked: return None, None
    from_socket = input_socket.links[0].from_socket; visited = {from_socket}
    while from_socket.node.bl_idname == 'NodeReroute':
        if not from_socket.node.inputs[0].is_linked: break
        next_socket = from_socket.node.inputs[0].links[0].from_socket
        if next_socket in visited: return None, None
        from_socket = next_socket; visited.add(from_socket)
    return from_socket, from_socket.node

def find_ultimate_targets(output_socket):
    targets = []; q, visited = deque([output_socket]), set()
    while q:
        s = q.popleft()
        if s in visited: continue
        visited.add(s)
        for link in s.links:
            to_socket = link.to_socket
            if to_socket.node.bl_idname == 'NodeReroute':
                if to_socket.node.outputs: q.append(to_socket.node.outputs[0])
            else: targets.append(to_socket)
    return targets

def draw_callback_px(self, context):
    if not self.active: return
    area=self.active_area; region=context.region
    if not area or context.area!=area or not region or region.type!='WINDOW': return
    self._sock_cache.clear()
    v2d=region.view2d; ui=context.preferences.system.ui_scale
    if not (tree := getattr(context.space_data,"edit_tree",None)): return
    md, bs = (20.0 * ui)**2, None
    mx, my = self.mouse_pos
    margin = 30.0 * ui
    candidate_sockets = []
    for node in tree.nodes:
        l, b, r, t = get_node_bounds_px(node, v2d, ui)
        if mx >= l - margin and mx <= r + margin and my >= b - margin and my <= t + margin:
             candidate_sockets.extend(s for s in chain(node.inputs, node.outputs) if s.is_linked)
    for s in candidate_sockets:
        if (p := get_socket_pos_px(self, s, v2d)):
            d = (p[0] - mx)**2 + (p[1] - my)**2
            if d < md: md, bs = d, s
    self.start_socket = bs
    if not bs: self.links_chain.clear(); self.chain_targets.clear(); return
    self.links_chain, self.chain_targets, ultimate_source_node = collect_full_path_info(bs)
    if not self.links_chain: return
    sh = self._shader
    gpu.state.blend_set("ALPHA"); sh.bind()
    nodes_to_draw = list(self.chain_targets)
    if ultimate_source_node: nodes_to_draw.append(ultimate_source_node)
    if nodes_to_draw:
        for nd in nodes_to_draw:
            if nd and nd.bl_idname != 'NodeReroute':
                l,b,r,t = get_node_bounds_px(nd, v2d, ui)
                col = get_node_border_color(nd, self._color_cache)
                verts = rounded_rect(l, b, r, t, 10)
                sh.uniform_float("color", col)
                if bpy.app.version < (5, 0, 0):
                    strip = _tri_strip_polygon(verts, 5.0 * ui)
                    if strip:
                        batch_for_shader(sh, 'TRI_STRIP', {"pos": strip}).draw(sh)
                else:
                    gpu.state.line_width_set(max(1, 2 * ui))
                    batch_for_shader(sh, 'LINE_STRIP', {"pos": verts}).draw(sh)
    sh.uniform_float("color", (1, 1, 1, 1))
    for lk in self.links_chain:
        if (verts := bezier_verts_from_link(lk, v2d, ui)):
            if bpy.app.version < (5, 0, 0):
                strip = _tri_strip_polyline(verts, max(3.0, line_thickness * ui))
                if strip:
                    batch_for_shader(sh, 'TRI_STRIP', {"pos": strip}).draw(sh)
            else:
                gpu.state.line_width_set(line_thickness * ui)
                batch_for_shader(sh, 'LINE_STRIP', {"pos": verts}).draw(sh)
    gpu.state.blend_set("NONE")



class CCC_OT_jump_to_node(bpy.types.Operator):
    bl_idname="ccc.jump_to_node"; bl_label="Jump to Node"; bl_options={'REGISTER','UNDO'}
    node_name:bpy.props.StringProperty()
    def execute(self,context):
        if context.area.type=='NODE_EDITOR' and (tree := context.space_data.edit_tree):
            if (node := tree.nodes.get(self.node_name)):
                bpy.ops.node.select_all(action='DESELECT'); node.select=True; tree.nodes.active=node
                bpy.ops.node.view_selected('INVOKE_DEFAULT')
                frame = tree.nodes.new("NodeFrame"); frame.label = "Jump Target"
                frame.name = "TEMP_FRAME_FOR_HIGHLIGHT"; frame.location = (node.location.x-40, node.location.y-40)
                frame.width = node.dimensions.x + 80; frame.height = node.dimensions.y + 80; node.parent = frame
                def _remove_frame():
                    if (f := tree.nodes.get("TEMP_FRAME_FOR_HIGHLIGHT")):
                        for n in tree.nodes:
                            if n.parent == f: n.parent = None
                        tree.nodes.remove(f)
                    return None
                bpy.app.timers.register(_remove_frame, first_interval=1.0)
        return {'FINISHED'}

class CCC_MT_pie_menu(bpy.types.Menu):
    bl_idname = "CCC_MT_pie_menu"; bl_label = "Connection Jumper"
    def draw(self, context):
        layout = self.layout; pie = layout.menu_pie(); wm = context.window_manager
        if not (tree := context.space_data.edit_tree): return
        prefs = bpy.context.preferences.addons[__package__].preferences
        lang = getattr(prefs, "language", bpy.context.preferences.view.language)
        if "zh" in lang.lower():
            lang = "zh_HANS"
        else:
            lang = "en"
        from .lang_dict import LANG_DICT
        t = LANG_DICT.get(lang, LANG_DICT["en"])
        left_box = pie.box(); left_col = left_box.column(align=True); left_col.label(text=t["sources"])
        left_ops = left_col.column(align=True); left_ops.alert = True
        if (upstreams := getattr(wm, "ccc_upstreams", "")):
            for item in upstreams.split("|"):
                nn, ss = item.split("::", 1)
                if (nd := tree.nodes.get(nn)):
                    op = left_ops.operator(CCC_OT_jump_to_node.bl_idname, text=f"{nd.label or nd.name} -> {ss}")
                    op.node_name = nn; left_ops.scale_x = 2.0; left_ops.scale_y = 2.0
        else: left_ops.label(text=t["none"], icon='NONE')
        right_box = pie.box(); right_col = right_box.column(align=True); right_col.label(text=t["targets"])
        right_ops = right_col.column(align=True); right_ops.alert = True
        if (downstreams := getattr(wm, "ccc_downstreams", "")):
            for item in downstreams.split("|"):
                nn, ss = item.split("::", 1)
                if (nd := tree.nodes.get(nn)):
                    op = right_ops.operator(CCC_OT_jump_to_node.bl_idname, text=f"{nd.label or nd.name} -> {ss}")
                    op.node_name = nn; right_ops.scale_x = 2.0; right_ops.scale_y = 2.0
        else: right_ops.label(text=t["none"], icon='NONE')


class CCC_OT_modal_link_highlighter(bpy.types.Operator):
    bl_idname="node.ccc_modal_link_highlighter";bl_label="CCC Link Highlighter"
    def modal(self,context,event):
        if not self.active or not context.area or context.area!=self.active_area: self.cleanup(context); return {'CANCELLED'}
        current_mouse_pos = (event.mouse_region_x, event.mouse_region_y)
        if event.type == 'MOUSEMOVE':
            dx = current_mouse_pos[0] - self.last_mouse_pos[0]
            dy = current_mouse_pos[1] - self.last_mouse_pos[1]
            if (dx*dx + dy*dy) > 4.0:
                self.mouse_pos = current_mouse_pos
                self.last_mouse_pos = current_mouse_pos
                context.area.tag_redraw()
            else:
                self.mouse_pos = current_mouse_pos
        if event.type=='LEFTMOUSE' and event.value=='PRESS' and self.start_socket:
            wm, active_node = context.window_manager, self.start_socket.node
            upstreams = [f"{n.name}::{s.name}" for s_in in active_node.inputs if (res := find_ultimate_source(s_in)) and (s:=res[0]) and (n:=res[1])]
            downstreams = [f"{ts.node.name}::{ts.name}" for s_out in active_node.outputs for ts in find_ultimate_targets(s_out)]
            wm.ccc_upstreams = "|".join(dict.fromkeys(upstreams))
            wm.ccc_downstreams = "|".join(dict.fromkeys(downstreams))
            bpy.ops.wm.call_menu_pie(name=CCC_MT_pie_menu.bl_idname)
            self.cleanup(context); return {'FINISHED'}
        if event.type in {'RIGHTMOUSE','ESC'}: self.cleanup(context); return {'CANCELLED'}
        return {'PASS_THROUGH'}

    def invoke(self,context,event):
        v={'ShaderNodeTree','CompositorNodeTree','GeometryNodeTree'}
        if context.area.type=='NODE_EDITOR' and context.space_data.tree_type in v:
            self.active=True; self.start_socket=None
            self.mouse_pos=(event.mouse_region_x,event.mouse_region_y); self.last_mouse_pos = self.mouse_pos
            self.active_area=context.area; self._sock_cache = {}; self._color_cache = {}
            self.links_chain, self.chain_targets = set(), set()
            self._shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            self._draw_handle = bpy.types.SpaceNodeEditor.draw_handler_add(draw_callback_px,(self,context),'WINDOW','POST_PIXEL')
            context.window_manager.modal_handler_add(self); context.area.tag_redraw(); return {'RUNNING_MODAL'}
        return {'CANCELLED'}
        
    def cleanup(self,context):
        if getattr(self,"active",False):
            self.active=False
            if hasattr(self, '_draw_handle') and self._draw_handle:
                bpy.types.SpaceNodeEditor.draw_handler_remove(self._draw_handle,'WINDOW')
            if context.area: context.area.tag_redraw()