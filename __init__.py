bl_info = {
    "name": "NodeLink Navigator",
    "author": "Sunkanwei",
    "version": (1, 9, 0),
    "blender": (5, 0, 0),
    "location": "Node Editor  •  Press 'C'",
    "description": "Highlight node categories using theme-aware colors and jump between connected nodes.",
    "doc_url": "",
    "tracker_url": "",
    "license": "GPL-3.0-or-later", 
    "support": "COMMUNITY",
    "category": "Node",
}

import bpy
from bpy.types import AddonPreferences
from . import operators
from .lang_dict import LANG_DICT

addon_keymaps = {}

def find_user_keyconfig(key):
    if key not in addon_keymaps:
        return None
    km, kmi = addon_keymaps[key]
    wm = bpy.context.window_manager
    kc_user = wm.keyconfigs.user
    if km.name not in kc_user.keymaps:
        return kmi
    prop_ids = [p.identifier for p in kmi.properties.bl_rna.properties if p.identifier not in {"bl_rna", "rna_type"}]
    for item in kc_user.keymaps[km.name].keymap_items:
        if kmi.idname == item.idname and all(getattr(kmi.properties, pid) == getattr(item.properties, pid) for pid in prop_ids):
            return item
    return kmi

class CCC_AddonPreferences(AddonPreferences):
    bl_idname = __name__

    def get_system_language():
        lang = bpy.context.preferences.view.language
        if "zh" in lang.lower():
            return "zh_HANS"
        return "en"

    language: bpy.props.EnumProperty(
        name="Language",
        description="Select plugin language",
        items=[
            ('en', "English", ""),
            ('zh_HANS', "简体中文", "")
        ],
        default=get_system_language()
    )

    def draw(self, context):
        layout = self.layout
        from .lang_dict import LANG_DICT
        kmi = find_user_keyconfig('CCC_MODAL_KEYMAP')
        lang = getattr(context.preferences.addons[__name__].preferences, "language", "en")
        if "zh" in lang.lower():
            lang = "zh_HANS"
        else:
            lang = "en"
        t = LANG_DICT.get(lang, LANG_DICT["en"])
        layout.prop(self, "language", text="Language / 语言")
        if kmi:
            layout.prop(kmi, 'type', text=t["highlighter_hotkey"], full_event=True)
        else:
            layout.label(text=t["hotkey_not_initialized"])


classes = (
    operators.CCC_OT_jump_to_node,
    operators.CCC_MT_pie_menu,
    operators.CCC_OT_modal_link_highlighter,
    CCC_AddonPreferences
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.ccc_upstreams = bpy.props.StringProperty()
    bpy.types.WindowManager.ccc_downstreams = bpy.props.StringProperty()
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='Node Editor', space_type='NODE_EDITOR')
        kmi = km.keymap_items.new(operators.CCC_OT_modal_link_highlighter.bl_idname, 'C', 'PRESS')
        addon_keymaps['CCC_MODAL_KEYMAP'] = (km, kmi)

def unregister():
    if addon_keymaps:
        for km, kmi in addon_keymaps.values():
            try:
                km.keymap_items.remove(kmi)
            except:
                pass
        addon_keymaps.clear()
    for n in ["ccc_upstreams", "ccc_downstreams"]:
        if hasattr(bpy.types.WindowManager, n):
            delattr(bpy.types.WindowManager, n)
    for c in reversed(classes):
        try:
            bpy.utils.unregister_class(c)
        except:
            pass

if __name__ == "__main__":
    register()
