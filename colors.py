import bpy, re, colorsys

SAT_BOOST = 0.6
VAL_BOOST = 0.85
MIN_SAT = 0.65
MIN_VAL = 0.25

def _theme():
    return bpy.context.preferences.themes[0].node_editor

def _to_rgba(c):
    return (c[0], c[1], c[2], 1.0)

def _safe_get(name, fallback=(0.8,0.8,0.8,1.0)):
    t = _theme()
    col = getattr(t, name, None)
    return _to_rgba(col) if col is not None else fallback

def _boost(col):
    r,g,b,a = col
    h,s,v = colorsys.rgb_to_hsv(r,g,b)
    s = min(1.0, max(MIN_SAT, s + SAT_BOOST*(1.0 - s)))
    v = min(1.0, max(MIN_VAL, v + VAL_BOOST*(1.0 - v)))
    r,g,b = colorsys.hsv_to_rgb(h,s,v)
    return (r,g,b,a)

THEME_KEYS = {
    "GROUP": "group_node",
    "FRAME": "frame_node",
    "LAYOUT": "layout_node",
    "INPUT": "input_node",
    "OUTPUT": "output_node",
    "SHADER": "shader_node",
    "GEOMETRY": "geometry_node",
    "TEXTURE": "texture_node",
    "COLOR": "color_node",
    "VECTOR": "vector_node",
    "CONVERTER": "converter_node",
    "FILTER": "filter_node",
}

EXACT_KEY = {
    "ShaderNodeMapping": "vector_node",
    "ShaderNodeTexCoord": "input_node",
    "ShaderNodeTexImage": "texture_node",
    "ShaderNodeBump": "vector_node",
    "ShaderNodeNormalMap": "vector_node",
    "ShaderNodeRGB": "color_node",
    "ShaderNodeHueSaturation": "color_node",
    "ShaderNodeMix": "color_node",
    "ShaderNodeValToRGB": "color_node",
    "ShaderNodeVectorMath": "vector_node",
    "ShaderNodeMath": "converter_node",
    "ShaderNodeClamp": "converter_node",
    "ShaderNodeSeparateRGB": "converter_node",
    "ShaderNodeCombineRGB": "converter_node",
    "ShaderNodeSeparateXYZ": "vector_node",
    "ShaderNodeCombineXYZ": "vector_node",
    "ShaderNodeGroup": "group_node",
    "NodeGroup": "group_node",
    "NodeFrame": "frame_node",
    "NodeReroute": "layout_node",
    "GeometryNodeGroup": "group_node",
    "CompositorNodeGroup": "group_node",
    "CompositorNodeComposite": "output_node",
    "CompositorNodeViewer": "output_node",
    "CompositorNodeImage": "input_node",
}

_COMPO_PAT = {
    "OUTPUT": re.compile(r"(Composite|Viewer|Output)", re.I),
    "INPUT": re.compile(r"(Image|RLayers|Render|Mask|Movie|Input)", re.I),
    "FILTER": re.compile(r"(Filter|Blur|Denoise|Glare|Defocus|Bilateral)", re.I),
    "COLOR": re.compile(r"(Color|Hue|Saturation|Gamma|Exposure|Levels|Balance|Curves|MixRGB)", re.I),
    "CONVERTER": re.compile(r"(Math|Convert|AlphaOver|ZCombine|SetAlpha|RGBToBW|Premul)", re.I),
    "VECTOR": re.compile(r"(Vector|Translate|Rotate|Scale|Transform|Displace|Map)", re.I),
    "GROUP": re.compile(r"(Group)", re.I),
    "LAYOUT": re.compile(r"(Reroute)", re.I),
    "FRAME": re.compile(r"(Frame)", re.I),
}

def _key_shader(bid):
    if "Output" in bid: return "output_node"
    if "Bsdf" in bid or "BSDF" in bid or "Emission" in bid or "Principled" in bid: return "shader_node"
    if bid.startswith("ShaderNodeTex"): return "texture_node"
    if "Vector" in bid or bid.startswith("ShaderNodeVector"): return "vector_node"
    if "Hue" in bid or "RGB" in bid or "Color" in bid: return "color_node"
    if "Group" in bid: return "group_node"
    if "Reroute" in bid: return "layout_node"
    if "Frame" in bid: return "frame_node"
    return "shader_node"

def _key_geo(bid):
    if "Group" in bid: return "group_node"
    if "Reroute" in bid: return "layout_node"
    if "Frame" in bid: return "frame_node"
    return "geometry_node"

def _key_comp(bid, name):
    for k, pat in _COMPO_PAT.items():
        if pat.search(bid) or pat.search(name or ""):
            return THEME_KEYS[k]
    return "converter_node"

def get_node_border_color(node, cache):
    if getattr(node, "use_custom_color", False):
        c = node.color; return _boost((c[0], c[1], c[2], 1.0))
    bid = node.bl_idname
    if bid in cache: return cache[bid]
    if bid in EXACT_KEY:
        key = EXACT_KEY[bid]
    elif bid.startswith("ShaderNode"):
        key = _key_shader(bid)
    elif bid.startswith("GeometryNode"):
        key = _key_geo(bid)
    elif bid.startswith("CompositorNode"):
        key = _key_comp(bid, getattr(node, "name", ""))
    else:
        key = "shader_node"
    col = _boost(_safe_get(key, (0.8,0.8,0.8,1.0)))
    cache[bid] = col
    return col
