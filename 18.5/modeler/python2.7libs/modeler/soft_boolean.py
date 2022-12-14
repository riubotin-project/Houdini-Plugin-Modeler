import hou
from modeler import ui, geo_utils


def panel(sb):
    with hou.RedrawBlock() as rb:
        try:
            sop = hou.node(sb.evalParm("panel_path"))
            pwd = geo_utils.ancestor_object(sop)
            pwd.destroy()
            sb.parm("panel_path").set("")
        except:
            a, b, c = _sb_inputs(sb)
            parent = sb.parent()
            
            geo = parent.parent().createNode("geo", "sb_panel")
            geo.parmTuple("p").set(sb.geometry().boundingBox().center())

            a_merge = geo.createNode("object_merge")
            a_merge.setParms({ "objpath1": a.path(), "xformtype": 1 })
        
            b_merge = geo.createNode("object_merge")
            b_merge.setParms({ "objpath1": b.path(), "xformtype": 1 })
            
            new_sb = hou.copyNodesTo([sb], geo)[0]
            
            new_sb.setHardLocked(False)
            new_sb.setInput(0, a_merge)
            new_sb.setInput(1, b_merge)

            new_sb.setParms({ "type": 1, "mode": 0, "allow_panel": False})
            sb.setParms({ "type": 2, "mode": 0 })

            sb.parm("panel_path").set(new_sb.path())
            
            new_sb.setDisplayFlag(True)
            new_sb.setRenderFlag(True)

            geo.layoutChildren()
            geo.moveToGoodPosition()
            sb.setCurrent(True, True)
            hou.ui.paneTabOfType(hou.paneTabType.SceneViewer).enterCurrentNodeState()
            ui.home_selected()

def panel_link(sb):
    try:
        sop = hou.node(sb.evalParm("panel_path"))
        pwd = geo_utils.ancestor_object(sop)
    
        # LINK
        if sop.userData("__panel_linked__") is None:
            sb_path = sb.path()
            sop.setUserData("__panel_linked__", "")
            
            for parm in sb.parms():
                parm_name = parm.name()
                
                if isinstance(parm.parmTemplate(), hou.ButtonParmTemplate) or parm_name in ("allow_panel", "type", "mode", "edit_fillet_toggle", "panel_path"):
                    continue
                
                sop.parm(parm_name).setExpression('ch("{}/{}")'.format(sb_path, parm_name))

        # UNLINK
        else:
            sop.destroyUserData("__panel_linked__")
            for parm in sb.parms():
                parm_name = parm.name()
                sop.parm(parm_name).deleteAllKeyframes()

    except:
        pass

def panel_set_material(sb):
    try:
        panel = hou.node(sb.evalParm("panel_path"))
    except:
        return

    panel_parent = geo_utils.ancestor_object(panel)
    
    # UNSET
    if panel_parent.evalParm("shop_materialpath"):
        panel_parent.parm("shop_materialpath").set("")

    # SET
    else:
        sb_parent = geo_utils.ancestor_object(sb)
        panel_parent.parm("shop_materialpath").set(sb_parent.evalParm("shop_materialpath"))

def _auto_subdivide(sop):
    if sop.geometry().intrinsicValue("primitivecount") < 500:
        sop = sop.createOutputNode("subdivide", "sb_auto_subdivide1")
        sop.setUserData("sb_auto_subdivide", "")
        sop.setParms({ "fvarlinear": 1, "iterations": 3 })
    return sop

def action(sb_sop):
    number = sb_sop.evalParm("actions")

    if number == 0:
        primary_quality(sb_sop, 1)

    elif number == 1:
        primary_quality(sb_sop, -1)

    elif number == 2:
        select()

    elif number == 3:
        edit_cutter(sb_sop)

    elif number == 4:
        swap()

    elif number == 5:
        simplify_all()

    elif number == 6:
        radius()

    elif number == 7:
        transfer(sb_sop)
    
    else:
        finish()

    sb_sop.parm("actions").set(-1)

def _after_edit_callback(event_type, **kwargs):
    with hou.RedrawBlock() as rb:
        sb = kwargs["node"]
        sb.removeAllEventCallbacks()
        sb.setDisplayFlag(True)
        sb.setCurrent(True, True)
        conns = sb.inputConnectors()
        if conns[0]:
            src = conns[0][0].inputNode()
            src.setTemplateFlag(False)
            src.setSelectableTemplateFlag(False)
        if __sb_edit_is_cutter_quality:
            pwd = geo_utils.ancestor_object(sb)
            pwd.parm("viewportlod").set(0)
        hou.ui.paneTabOfType(hou.paneTabType.SceneViewer).enterCurrentNodeState()

        for geo in ___sb_edit_hidden_geos:
            try:
                geo.setDisplayFlag(True)
            except:
                pass

def edit_cutter(sb):
    conns = sb.inputConnectors()
    if conns[0] and conns[1]:
        with hou.RedrawBlock() as rb:
            global ___sb_edit_hidden_geos, __sb_edit_is_cutter_quality
            __sb_edit_is_cutter_quality = sb.evalParm("cutter_quality") > 0
            src = conns[0][0].inputNode()
            cutter = conns[1][0].inputNode()
            cutter.setDisplayFlag(True)
            cutter.setCurrent(True, True)
            pwd = geo_utils.ancestor_object(sb)
            pwd.parm("viewportlod").set(5)
            src.setTemplateFlag(True)
            src.setSelectableTemplateFlag(False)
            hou.ui.paneTabOfType(hou.paneTabType.SceneViewer).enterCurrentNodeState()
            sb.addEventCallback((hou.nodeEventType.AppearanceChanged,), _after_edit_callback)

            ___sb_edit_hidden_geos = []
            for geo in hou.nodeType(geo_utils._obj_category, "geo").instances():
                if geo == pwd:
                    continue
                elif geo.isDisplayFlagSet():
                    geo.setDisplayFlag(False)
                    ___sb_edit_hidden_geos.append(geo)

def operation(op):
    global last_sb_node

    scene_viewer = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
    pwd = scene_viewer.pwd()
    child_cat = pwd.childTypeCategory()

    success = False
    
    # OBJ
    if child_cat == geo_utils._obj_category:
        geos = [node for node in hou.selectedNodes() if node.type().name()=="geo"]
        if len(geos) == 2:
            dn1 = geos[0].displayNode()
            dn2 = geos[1].displayNode()
            if dn1 is not None and dn2 is not None:
                with hou.undos.group("Soft Boolean"):                
                    mat = geos[0].evalParm("shop_materialpath")
                    if mat:
                        dn1 = dn1.createOutputNode("material")
                        dn1.parm("shop_materialpath1").set(mat)
                    
                    nodes = (dn1,) + dn1.inputAncestors()
                    xform = geos[0].worldTransform() * geos[1].worldTransform().inverted()
                    t = xform.extractTranslates()
                    r = xform.extractRotates()
                    s = xform.extractScales()
                    sh = xform.extractShears()
                    dn2 = _auto_subdivide(dn2)
                    sb = dn2.createOutputNode("modeler::soft_boolean")
                    prim_count = dn1.geometry().intrinsicValue("primitivecount")
                    sb.setParms({ "type": op, "cutter_quality": 2 if prim_count < 1000 else 0 })

                    x = sb.createInputNode(1, "xform")
                    x.parmTuple("t").set(t)
                    x.parmTuple("r").set(r)
                    x.parmTuple("s").set(s)
                    x.parmTuple("shear").set(sh)
                    
                    new_nodes = hou.moveNodesTo(nodes, geos[1])
                    
                    x.setInput(0, new_nodes[0])
                    
                    sb.setCurrent(True, True)
                    sb.setDisplayFlag(True)
                    sb.setRenderFlag(True)
                    scene_viewer.enterCurrentNodeState()
                    geos[0].destroy()
                    set_color(sb)
                    last_sb_node = sb
                    sb.parent().layoutChildren()
                    success = True

    # SOP
    elif child_cat == geo_utils._sop_category:
        sops = hou.selectedNodes()
        sops_count = len(sops)
        if sops_count == 2:
            with hou.undos.group("Soft Boolean"):                
                sop = _auto_subdivide(sops[1])
                sb = sop.createOutputNode("modeler::soft_boolean")
                prim_count = sops[0].geometry().intrinsicValue("primitivecount")
                sb.setParms({ "type": op, "cutter_quality": 2 if prim_count < 1000 else 0 })
                sb.setInput(1, sops[0])
                sb.setCurrent(True, True)
                sb.setDisplayFlag(True)
                sb.setRenderFlag(True)
                scene_viewer.enterCurrentNodeState()
                set_color(sb)
                last_sb_node = sb
                sb.parent().layoutChildren()
                success = True

        else:
            pane_tab = hou.ui.paneTabUnderCursor()
            if pane_tab is not None and pane_tab.type() == hou.paneTabType.NetworkEditor:
                import soptoolutils
                soptoolutils.genericTool({}, "modeler::soft_boolean")
                success = True

            elif sops_count == 1:
                with hou.undos.group("Soft Boolean"):                
                    cut_pwd, cut_sop = geo_utils.get_object(scene_viewer, "Select an object to cut from.")
                    if cut_pwd is not None and cut_pwd != pwd:
                        cut_sop = _auto_subdivide(cut_sop)
                        sop = sops[0]
                        prim_count = sop.geometry().intrinsicValue("primitivecount")
                        parms = { "type": op, "cutter_quality": 2 if prim_count < 1000 else 0 }
                        node = geo_utils.merge_with_object(sop, pwd, cut_sop, cut_pwd, merge_node_type="modeler::soft_boolean", merge_node_parms=parms)
                        scene_viewer.enterCurrentNodeState()
                        success = True

    if not success:
        hou.ui.displayMessage("At OBJ level select cutter surface, surface you want to cut, and try again.\nYou can also cut at SOP level by selecting two nodes in the network editor or .")

def sop_world_transform(sop):
    pwd = sop.parent()
    while pwd.type().category() != geo_utils._obj_category:
        pwd = pwd.parent()
    mat = pwd.worldTransform()
    return mat, mat.inverted()

def find():
    scene_viewer = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
    pwd = scene_viewer.pwd()
    cur_node = scene_viewer.currentNode()
    child_cat = pwd.childTypeCategory()
    
    # SOP
    if child_cat == geo_utils._sop_category:
        dn = pwd.displayNode()

        if cur_node.type().name() == "modeler::soft_boolean":
            return cur_node
        
        elif dn.type().name() == "modeler::soft_boolean":
            return dn

        else:
            for ancestor in (cur_node,) + cur_node.inputAncestors():
                if ancestor.type().name() == "modeler::soft_boolean":
                    return ancestor

def all_input_sbs(sb):
    sbs = []
    input_conn = sb.inputConnectors()
    if len(input_conn) > 0:
        first_input_connection = input_conn[0]
        if len(first_input_connection):
            input_node = first_input_connection[0].inputNode()
            if input_node.type().name() == "modeler::soft_boolean":
                sbs.append(input_node)
                sbs += all_input_sbs(input_node)
    return sbs

def _sb_inputs(node):
    a = b = c = None
    connectors = node.inputConnectors()
    if len(connectors[0]) > 0:
        a = connectors[0][0].inputNode()
    if len(connectors[1]) > 0:
        b = connectors[1][0].inputNode()
    if len(connectors[2]) > 0:
        c = connectors[2][0].inputNode()
    return a, b, c

def primary_quality(sb, direction):
    all_sbs = all_input_sbs(sb)

    if len(all_sbs) > 0:
        first_sb = all_sbs[-1]
    else:
        first_sb = sb
    
    input_node = _sb_inputs(first_sb)[0]
    
    if input_node is not None:
        with hou.RedrawBlock() as rb:
            subd = None
            ancestors = (input_node,) + input_node.inputAncestors()
            for ancestor in ancestors:
                if ancestor.type().name() == "subdivide" and ancestor.userData("sb_auto_subdivide") is not None:
                    subd = ancestor
                    break
            
            if subd is None:
                subd = input_node.createOutputNode("subdivide", "sb_auto_subdivide")
                subd.setParms({ "fvarlinear": 1, "iterations": 1 })
                subd.setUserData("sb_auto_subdivide", "")
                sb.setInput(0, subd)
                sb.parent().layoutChildren(ancestors + (subd,))
            else:
                subd.parm("iterations").set(subd.evalParm("iterations") + direction)

def select():
    scene_viewer = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
    pwd = scene_viewer.pwd()
    if pwd.childTypeCategory() == geo_utils._obj_category:
        nodes = hou.selectedNodes()
        if nodes and nodes[0].type().name() == "geo":
            path = nodes[0].path()
            for instance in hou.nodeType(geo_utils._sop_category, "object_merge").instances():
                if instance.evalParm("objpath1") == path:
                    outputs = instance.outputs()
                    if len(outputs) == 1 and outputs[0].type().name() == "modeler::soft_boolean":
                        outputs[0].setCurrent(True, True)
                    else:
                        instance.setCurrent(True, True)
                    hou.ui.waitUntil(lambda: True)
                    scene_viewer.enterCurrentNodeState()
                    ui.home_selected()
                    break

    else:
        sb = grab()
        if sb is not None:
            sb.setCurrent(True, True)
            scene_viewer.enterCurrentNodeState()
            ui.home_selected()

def inputs(node):
    a = b = c = None
    connectors = node.inputConnectors()
    if len(connectors[0]) > 0:
        a = connectors[0][0].inputNode()
    if len(connectors[1]) > 0:
        b = connectors[1][0].inputNode()
    if len(connectors[2]) > 0:
        c = connectors[2][0].inputNode()
    return a, b, c

def grab():
    scene_viewer = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
    pwd = scene_viewer.pwd()

    if pwd.childTypeCategory() == geo_utils._sop_category:
        dn = pwd.displayNode()
        if dn is not None:
            # cutters = []
            all_sbs = []
            cutters_sbs = {}
            
            for sb in hou.nodeType(geo_utils._sop_category, "modeler::soft_boolean").instances():
                if sb.parent() == pwd:
                    connectors = sb.inputConnectors()
                    if len(connectors[1]) > 0:
                        cutter = connectors[1][0].inputNode()
                        cutters_sbs[cutter] = sb

            cutters = cutters_sbs.keys()
            if len(cutters) > 1:
                # REMEMBER DISPLAY SHADE STATE
                ds = scene_viewer.curViewport().settings().displaySet(hou.displaySetType.DisplayModel)
                pre_shaded_mode = ds.shadedMode()
                pre_xray = ds.isUsingXRay()
                pre_pick_type = scene_viewer.pickGeometryType()
                ds.setShadedMode(hou.glShadingType.Wire)
                ds.useXRay(True)
            
            
                cutters[0].setDisplayFlag(True)
                dn.setCurrent(False, True)

                for cutter in cutters[1:]:
                    cutter.setSelectableTemplateFlag(True)

                try:
                    gs = scene_viewer.selectGeometry(prompt="Select soft boolean cutter.", use_existing_selection=False, quick_select=True, geometry_types=(hou.geometryType.Edges,), allow_obj_sel=False)
                except hou.OperationInterrupted:
                    scene_viewer.setCurrentState("select")
                    return
                finally:
                    for cutter in cutters[1:]:
                        cutter.setSelectableTemplateFlag(False)
                    
                    dn.setCurrent(True, True)
                    dn.setDisplayFlag(True)
                    
                    # RESTORE SHADE STATE
                    ds.setShadedMode(pre_shaded_mode)
                    ds.useXRay(pre_xray)
                    scene_viewer.setPickGeometryType(pre_pick_type)

                return cutters_sbs[gs.nodes()[0]]

    return None
      
def create_panel(cur_node):
    with hou.RedrawBlock() as rb:
        a, b, c = inputs(cur_node)
        a_path = a.path()
        b_path = b.path()
        
        geo = cur_node.parent().parent().createNode("geo", "sb_panel1")
        geo.parmTuple("p").set(cur_node.geometry().boundingBox().center())
        a_merge = geo.createNode("object_merge")
        a_merge.setParms({"objpath1": a_path, "xformtype": 1})
    
        b_merge = geo.createNode("object_merge")
        b_merge.setParms({"objpath1": b_path, "xformtype": 1})
    
        new_sb = hou.copyNodesTo([cur_node], geo)[0]
        new_sb.setHardLocked(False)
        new_sb.setInput(0, a_merge)
        new_sb.setInput(1, b_merge)
        new_sb.parm("type").set(2)
        new_sb.parm("is_simple").set(cur_node.evalParm("is_simple"))
        
        cur_node.parm("type").set(1)

        xform = new_sb.createOutputNode("xform", "transform_panel")
        xform.parm("px").setExpression("$CEX")
        xform.parm("py").setExpression("$CEY")
        xform.parm("pz").setExpression("$CEZ")
        xform.setSelected(True, False)        
        xform.setDisplayFlag(True)
        xform.setRenderFlag(True)

        geo.layoutChildren()
        geo.moveToGoodPosition()
        cur_node.setCurrent(True, True)
        ui.home_selected()

def simplify_all():
    scene_viewer = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
    pwd = scene_viewer.pwd()

    if pwd.childTypeCategory() == geo_utils._sop_category:
        with hou.RedrawBlock() as rb:
            all_sbs = []
            for f in hou.nodeType(geo_utils._sop_category, "modeler::soft_boolean").instances():
                if f.parent() == pwd:
                    all_sbs.append(f)
            

            if all_sbs:
                value = not all_sbs[0].evalParm("mode")
                for f in all_sbs:
                    f.parm("mode").set(value)

def transfer(sb_sop):
    scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    dst_pwd, dst_sop = geo_utils.get_object(scene_viewer, "Select an object to cut from.")
    pwd = geo_utils.ancestor_object(sb_sop)
    if dst_pwd is not None and dst_pwd != pwd:
        a, b, c = inputs(sb_sop)
        if a is not None and b is not None:
            b_path = b.path()
            new_sb = hou.copyNodesTo([sb_sop], dst_pwd)[0]
            
            dst_sop = _auto_subdivide(dst_sop)

            new_sb.setInput(0, dst_sop)
            m = new_sb.createInputNode(1, "object_merge")
            m.parm("objpath1").set(b_path)
            new_sb.setDisplayFlag(True)
            new_sb.setRenderFlag(True)
            pwd.setCurrent(True, True)

def swap():
    src_sb = find()
    dst_sb = grab()
    if dst_sb is not None and src_sb != dst_sb:  
        with hou.RedrawBlock() as rb:
            src_a, src_b, src_c = inputs(src_sb)
            dst_a, dst_b, dst_c = inputs(dst_sb)
        
            src_parms = src_sb.parms()
        
            src_dict = {}
            dst_dict = {}
        
            for parm in src_parms:
                src_dict[parm.name()] = parm.eval()
                
            for parm in src_parms:
                dst_dict[parm.name()] = dst_sb.evalParm(parm.name())
        
            src_sb.setParms(dst_dict)
            dst_sb.setParms(src_dict)
        
            src_sb.setInput(1, dst_b)
            src_sb.setInput(2, dst_c)
        
            dst_sb.setInput(1, src_b)
            dst_sb.setInput(2, src_c)
            
            set_color(src_sb)
            set_color(dst_sb)

            src_sb.parent().layoutChildren(src_sb.inputAncestors() + dst_sb.inputAncestors() + (src_sb, dst_sb))

def pop():
    scene_viewer = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
    cur_node = scene_viewer.currentNode()

    if cur_node.type().category() == geo_utils._sop_category:
        with hou.RedrawBlock() as rb:
            parent = cur_node.parent()
            cur_node_path = cur_node.path()
            obj_merge = parent.createNode("object_merge")
            ui.catch_outputs(cur_node, obj_merge)
            sops = (cur_node,) + cur_node.inputAncestors()
            
            # FIND FIRST OBJ MANAGER
            while parent.type().category() != geo_utils._obj_category:
                parent = parent.parent()

            pwd = parent.parent()
            geo = pwd.createNode("geo", "separated_sops")
            geo.parm("vm_rendervisibility").set("")
            geo.parm("viewportlod").set(2)
            geo.parmTuple("p").set(cur_node.geometry().boundingBox().center())
            geo.moveToGoodPosition()
            geo.setWorldTransform(parent.worldTransform())
            new_sops = hou.moveNodesTo(sops, geo)
            new_sops[0].setDisplayFlag(True)
            new_sops[0].setRenderFlag(True)
            obj_merge.setParms({"objpath1": geo.path(), "xformtype": 1})
            obj_merge.moveToGoodPosition()
            scene_viewer.setPwd(pwd)
            geo.setCurrent(True, True)
            hou.ui.waitUntil(lambda: True)
            scene_viewer.enterTranslateToolState()

            obj_merge_path = obj_merge.path()
            for i in hou.nodeType(geo_utils._sop_category, "object_merge").instances():
                if i.evalParm("objpath1") == cur_node_path:
                    i.parm("objpath1").set(obj_merge_path)

            ui.home_selected()

    else:
        geos = [node for node in hou.selectedNodes() if node.type().name()=="geo"]
        if len(geos) == 1:
            sop = geos[0].displayNode()
            if sop is not None:
                path = geos[0].path()
                for instance in hou.nodeType(geo_utils._sop_category, "object_merge").instances():
                    if instance.evalParm("objpath1") == path:
                        outputs = instance.outputs()
                        if len(outputs) == 1 and outputs[0].type().name() == "modeler::soft_boolean":
                            with hou.RedrawBlock() as rb:
                                parent = instance.parent()
                                nodes = (sop,) + sop.inputAncestors()
                                xform = geos[0].worldTransform() * parent.worldTransform().inverted()
                                t = xform.extractTranslates()
                                r = xform.extractRotates()
                                s = xform.extractScales()

                                x = outputs[0].createInputNode(1, "xform")
                                x.parmTuple("t").set(t)
                                x.parmTuple("r").set(r)
                                x.parmTuple("s").set(s)

                                dn = parent.displayNode()

                                new_nodes = hou.moveNodesTo(nodes, parent)
                                x.setInput(0, new_nodes[0])

                                dn.setCurrent(True, True)
                                dn.setDisplayFlag(True)
                                dn.setRenderFlag(True)

                                scene_viewer.setPwd(parent.parent())

                                instance.destroy()
                                geos[0].destroy()

                                parent.layoutChildren()

                                break

def set_color(node):
    type_ = node.evalParm("type")
    if type_ == 0:
        node.setColor(hou.Color((1.0, 0.5, 0.5)))
    elif type_ == 1:
        node.setColor(hou.Color((0.584, 0.776, 1.0)))
    elif type_ == 2:
        node.setColor(hou.Color((0.765, 1.0, 0.576)))
    else:
        node.setColor(hou.Color((0.839, 0.839, 0.839)))

def radius():
    sb = find()
    if sb is not None:
        scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        
        try:
            gs = scene_viewer.selectGeometry(prompt="Select polygons to place metaball.", geometry_types=(hou.geometryType.Primitives,))
        except:
            scene_viewer.setCurrentState("select")
            return

        sel = gs.selections()
        if sel:
            with hou.RedrawBlock() as rb:
                
                sel = sel[0].freeze()

                geo = sb.geometry()
                items = sel.selectionString(geo)
                bb = geo.primBoundingBox(items)
                x, y, z = bb.sizevec()
                rad = (x + y + z) / 3.0

                parent = sb.parent()
                meta = parent.createNode("metaball", "metaradius")        

                meta.parmTuple("t").set(bb.center())
                meta.parmTuple("rad").set((rad, rad, rad))
                

                third_connector = sb.inputConnectors()[2]
                if len(third_connector) > 0:
                    input_node = third_connector[0].inputNode()
                    if input_node.type().name() == "merge":
                        input_node.setNextInput(meta)
                    else:
                        merge = sb.createInputNode(2, "merge")
                        merge.setInput(0, input_node)
                        merge.setInput(1, meta)
                        
                else:
                    sb.setInput(2, meta)

                sb.parm("mode").set(0)
                
                meta.setCurrent(True, True)
                scene_viewer.enterCurrentNodeState()

                parent.layoutChildren()

                ui.home_selected()

def finish():
    scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    sop = scene_viewer.currentNode()
    if sop.type().category() == geo_utils._sop_category:
        sop = sop.createOutputNode("modeler::soft_boolean_finish")
        sop.setCurrent(True, True)
        sop.setDisplayFlag(True)
        sop.setRenderFlag(True)
        scene_viewer.enterCurrentNodeState()