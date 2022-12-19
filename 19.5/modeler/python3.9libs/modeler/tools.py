import hou
from modeler import ui, geo_utils, states


###############################################################################
# TOOL UTILS

CATEGORIES = {}

def ADD_TOOL(tool, category_label):
    if category_label not in CATEGORIES:
        CATEGORIES[category_label] = []
    CATEGORIES[category_label].append(tool)


###############################################################################


def boolean(scene_viewer, op):
    pwd = scene_viewer.pwd()
    child_cat = pwd.childTypeCategory()
    
    if child_cat == geo_utils._obj_category:
        nodes = [node for node in (hou.selectedNodes() or pwd.children()) if node.type().name()=="geo"]
        count = len(nodes)
        
        if count == 1:
            next_pwd, next_sop = geo_utils.get_object(scene_viewer, "One object is selected. Select an object to cut from.")
            if next_pwd is not None and next_pwd != nodes[0]:
                nodes.append(next_pwd)
                count = 2
            else:
                return
        
        elif count:
            obj = nodes[-1]
            xform_inverted = obj.worldTransform().inverted()
            obj.setCurrent(True, True)
            sop = obj.displayNode()
            b = sop.createOutputNode("modeler::boolean")
            b.parm("type").set(op)
            if count == 2:
                merge = b
            else:
                merge = b.createInputNode(1, "merge")

            for obj1 in nodes[:-1]:
                sop1 = obj1.displayNode()

                if sop1 is not None:
                    nodes = (sop1,) + sop1.inputAncestors()
                    xform = obj1.worldTransform() * xform_inverted
                    t = xform.extractTranslates()
                    r = xform.extractRotates()
                    s = xform.extractScales()
                    sh = xform.extractShears()
                    x = obj.createNode("xform")
                    merge.setNextInput(x)
                    x.parmTuple("t").set(t)
                    x.parmTuple("r").set(r)
                    x.parmTuple("s").set(s)
                    x.parmTuple("shear").set(sh)
                    new_nodes = hou.moveNodesTo(nodes, obj)
                    x.setInput(0, new_nodes[0])
                    obj1.destroy()

            if count == 2:
                b.parmTuple("p").set(x.geometry().boundingBox().center())
            else:
                b.parmTuple("p").set(merge.geometry().boundingBox().center())

            b.setDisplayFlag(True)
            b.setRenderFlag(True)
            b.setHighlightFlag(True)
            b.setCurrent(True, True)
            scene_viewer.enterCurrentNodeState()
            obj.layoutChildren()

    elif child_cat == geo_utils._sop_category:
        sel = hou.selectedNodes()
        if len(sel) == 2:
            sop1 = sel[1].createOutputNode("modeler::boolean")
            sop1.parm("type").set(op)
            sop1.setInput(1, sel[0])
            sop1.parmTuple("p").set(sel[0].geometry().boundingBox().center())
            sop1.setDisplayFlag(True)
            sop1.setRenderFlag(True)
            sop1.setCurrent(True, True)
            scene_viewer.enterCurrentNodeState()
        
        elif len(sel) == 1:
            sop, sel, pwd = geo_utils.sop_selection(scene_viewer)
            if sop is not None:
                geo = sop.geometry()
                
                # WHOLE GEO -> TRY FINISH THE ACTION WITH A NEW SELECTED OBJECT
                if geo_utils.is_all_selected(sel, geo):
                    next_pwd, next_sop = geo_utils.get_object(scene_viewer, "The SOP has no selection. Select an object to cut from.")
                    if next_pwd is not None and next_pwd != pwd:
                        xform = pwd.worldTransform() * next_pwd.worldTransform().inverted()
                        pivot = geo.boundingBox().center() * xform
                        sop = geo_utils.merge_with_object(sop, pwd, next_sop, next_pwd, merge_node_type="modeler::boolean", merge_node_parms={"type": op})
                        sop.parmTuple("p").set(pivot)
                        sop.parmTuple("pr").set(xform.extractRotates())
                        scene_viewer.enterCurrentNodeState()
                        geo = sop.geometry()
                        items = "!_3d_hidden_primitives"

                elif sel.selectionType() == hou.geometryType.Primitives:
                    items = sel.selectionString(geo, force_numeric=True)
                    
                    sop = sop.createOutputNode("split", "separate_boolean_cutter1")
                    sop.setParms({ "group": items, "negate": True })
                    sop1 = sop.createOutputNode("modeler::boolean")
                    sop1.parm("type").set(op)
                    sop1.setInput(1, sop, 1)
                    sop1.parmTuple("p").set(geo.primBoundingBox(items).center())
                    
                    with hou.RedrawBlock() as rb:
                        sop1.setDisplayFlag(True)
                        sop1.setRenderFlag(True)
                        sop1.setCurrent(True, True)
                    
                    scene_viewer.enterCurrentNodeState()


def qprimitive(scene_viewer, primitive_type):
    t, r = geo_utils.get_selection_center_and_rotation(scene_viewer)
    
    obj = hou.node("/obj").createNode("geo", "qprimitive_object1")
    obj.moveToGoodPosition()
    sop = obj.createNode("modeler::qprimitive")
    sop.parm("type").set(primitive_type)    

    # SCALE NODE
    ii = list(sop.type().instances())
    if len(ii) > 1:
        ii.pop()
        ii.reverse()

        for i in ii:
            sop.parm("scale").set( i.evalParm("scale") )
            break

    if t is not None:
        sop.parmTuple("t").set(t)
        sop.parmTuple("r").set(r)

    sop.setCurrent(True, True)
    scene_viewer.enterCurrentNodeState()


class TopoTools(object):

    def _state_prepare(self, scene_viewer, unpack=False):
        sop = geo_utils.get_sop(scene_viewer)
        if sop is not None:
            with hou.RedrawBlock() as rb:
                if sop.type().name() == "topobuild" and sop.userData("__topo_mode_skin__") is None:
                    sop.parm("topobuild_preedit").pressButton()
                else:
                    sop = sop.createOutputNode("topobuild")
                    sop.setDisplayFlag(True)
                    sop.setRenderFlag(True)
                    sop.setCurrent(True, True)

                highres_sop = self.get_highres_sop()
                
                if highres_sop is not None:
                    om = geo_utils.inject_ref_objectmerge(highres_sop, sop.parent())
                    sop.setInput(1, om)

                if scene_viewer.currentState() != "topobuild":
                    scene_viewer.enterCurrentNodeState()

    def get_highres_sop(self):
        try:
            return hou.node("/obj/__topo_highres__").displayNode()
        except:
            return None

    def topo_mode(self, scene_viewer):
        highres_sop = self.get_highres_sop()

        # DEACTIVATE
        if highres_sop is not None:
            for viewport in scene_viewer.viewports():
                ds = viewport.settings().displaySet(hou.displaySetType.DisplayModel)
                ds.useXRay(False)

            highres_object = highres_sop.parent()
            highres_object.setSelectableInViewport(True)
            
            # RENAME AND DESTROY USER DATA
            initial_name = highres_object.userData("__topo_initial_name__")
            highres_object.destroyUserData("__topo_initial_name__")
            highres_object.setName(initial_name)

            highres_sop.parent().hide(False)
            
            # DESTROY PACK NODE
            highres_sop.destroy()


            hou.ui.displayMessage("Topo mode deactivated.", title="Topo Mode")
        
        # ACTIVATE
        else:
            pwd = scene_viewer.pwd()

            highres_object = highres_sop = None

            if pwd.childTypeCategory() == geo_utils._sop_category:
                highres_object = pwd
                highres_sop = pwd.displayNode()

                # PROCESS FRESH EDIT SOP
                if highres_sop.type().name() == "edit":
                    scene_viewer.enterViewState()
                    hou.ui.waitUntil(lambda: True)
                    try:
                        highres_sop.cookCount()
                    except hou.ObjectWasDeleted:
                        highres_sop = scene_viewer.currentNode()
            else:
                sel_nodes = [ node for node in hou.selectedNodes() if node.type().name() == "geo" ]
                if len(sel_nodes) == 1:
                    highres_object = sel_nodes[0]
                    highres_sop = highres_object.displayNode()

            # OBJECTS EXISTS
            if highres_object is not None and highres_sop is not None:
                result = hou.ui.displayMessage("Topo mode activated. Do you want to start drawing a new patch?", buttons=("Yes", "No"), close_choice=1, default_choice=1, title="Topo Mode")

                with hou.RedrawBlock() as rb:
                    highres_object.setSelectableInViewport(False)
                    
                    # SETUP VIEWPORTS
                    for viewport in scene_viewer.viewports():
                        ds1 = viewport.settings().displaySet(hou.displaySetType.GhostObject)
                        ds2 = viewport.settings().displaySet(hou.displaySetType.SceneObject)
                        ds1.setShadedMode(hou.glShadingType.Smooth)   
                        ds2.setShadedMode(hou.glShadingType.Smooth)
                        ds = viewport.settings().displaySet(hou.displaySetType.DisplayModel)
                        ds.useXRay(True)
                        ds.setShadedMode(hou.glShadingType.SmoothWire)
                    
                    # RENAME AND STORE INITIAL NAME AS USER DATA
                    highres_object.setUserData("__topo_initial_name__", highres_object.name())
                    highres_object.setName("__topo_highres__")
                    hou.clearAllSelected()

                    # CREATE PACK NODE
                    highres_sop.createOutputNode("pack", "packed_for_better_performance").setDisplayFlag(True)
                    highres_sop.setColor( hou.Color(0.094, 0.369, 0.69) )

                # DEACTIVATE NODE
                with hou.RedrawBlock() as rb:
                    highres_object.hide(True)
                    scene_viewer.setPwd(hou.node("/obj"))
                    hou.clearAllSelected()

                # START NEW PATCH
                if result == 0:
                    self.new_patch(scene_viewer, True)


            # CONFIRM ABOUT WRONG SELECTION
            else:
                hou.ui.displayMessage("Select the high-res geometry and try again.", title="Topo Mode")

    def new_patch(self, scene_viewer, strip):
        highres_sop = self.get_highres_sop()

        if highres_sop is None:
            hou.ui.displayMessage("Works only in Topo mode.")
        else:
            sel_nodes = hou.selectedNodes()
            if sel_nodes and sel_nodes[0] == highres_sop.parent() or scene_viewer.pwd() == highres_sop.parent():
                return

            sop = geo_utils.get_sop(scene_viewer)

            if sop is None:
                obj = hou.node("/obj").createNode("geo", "topopatch1")
                obj.moveToGoodPosition()
                om = geo_utils.inject_ref_objectmerge(highres_sop, obj)
                tp = om.createOutputNode("modeler::topopatch")
                tp.parm("strip").set(strip)
            else:
                if sop.parent() == highres_sop.parent():
                    return
            
                om = geo_utils.inject_ref_objectmerge(highres_sop, sop.parent())
                tp = om.createOutputNode("modeler::topopatch")
                tp.parm("strip").set(strip)
                tp.setInput(1, sop)
                tp.moveToGoodPosition()

            with hou.RedrawBlock() as rb:
                tp.setDisplayFlag(True)
                tp.setRenderFlag(True)
                tp.setCurrent(True, True)
    
            scene_viewer.enterCurrentNodeState()

    def project(self, scene_viewer):
        highres_sop = self.get_highres_sop()

        if highres_sop is None:
            hou.ui.displayMessage("Works only in Topo mode.")
        else:
            sop = geo_utils.get_sop(scene_viewer)

            if sop is not None:
                om = geo_utils.inject_ref_objectmerge(highres_sop, sop.parent())

                ray = sop.createOutputNode("modeler::project")
                ray.setInput(1, om)

                with hou.RedrawBlock() as rb:
                    ray.setDisplayFlag(True)
                    ray.setRenderFlag(True)
                    ray.setCurrent(True, True)
                
                scene_viewer.setCurrentState("select")

    def build(self):
        self._state_prepare( hou.ui.paneTabOfType(hou.paneTabType.SceneViewer) )
        ui.run_internal_command("h.pane.gview.state.sop.topobuild.build")

    def slide(self):
        self._state_prepare( hou.ui.paneTabOfType(hou.paneTabType.SceneViewer) )
        ui.run_internal_command("h.pane.gview.state.sop.topobuild.slide")

    def split(self):
        self._state_prepare( hou.ui.paneTabOfType(hou.paneTabType.SceneViewer) )
        ui.run_internal_command("h.pane.gview.state.sop.topobuild.split")

    def move_brush(self):
        self._state_prepare( hou.ui.paneTabOfType(hou.paneTabType.SceneViewer) )
        ui.run_internal_command("h.pane.gview.state.sop.topobuild.brush")

    def smooth_brush(self):
        self._state_prepare( hou.ui.paneTabOfType(hou.paneTabType.SceneViewer) )
        ui.run_internal_command("h.pane.gview.state.sop.topobuild.smooth")

    def skin(self):
        highres_sop = self.get_highres_sop()
        if highres_sop is not None:
            scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
            sop = geo_utils.get_sop(scene_viewer)
            if sop is not None:

                if sop.type().name() == "topobuild":
                    # SKIN TOPOBUILD
                    if sop.userData("__topo_mode_skin__") is not None:
                        scene_viewer.enterCurrentNodeState()
                        ui.run_internal_command("h.pane.gview.state.sop.topobuild.skin")
                        return

                tb = sop.createOutputNode("topobuild", "topo_skin1")
                tb.setUserData("__topo_mode_skin__", "")
                tb.setColor( hou.Color(0.094, 0.369, 0.69) )

                pre_pack_sop = highres_sop.inputs()[0]
                pre_pack_sop_path = pre_pack_sop.path()

                om = None
                for ancestor in sop.inputAncestors():
                    if ancestor.type().name() == "object_merge" and ancestor.evalParm("objpath1") == pre_pack_sop_path:
                        om = ancestor
                        break

                if om is None:
                    om = geo_utils.inject_ref_objectmerge(pre_pack_sop, sop.parent())
                    om.setColor( hou.Color(0.094, 0.369, 0.69) )

                tb.setInput(1, om)

                tb.setDisplayFlag(True)
                tb.setRenderFlag(True)
                tb.setCurrent(True, True)
                scene_viewer.enterCurrentNodeState()
                ui.run_internal_command("h.pane.gview.state.sop.topobuild.skin")


topo_tools = TopoTools()


class RadialMenuTools(object):
    def _check(self, scene_viewer):
        sop, sel, pwd = geo_utils.sop_selection(scene_viewer)
        if sop is not None:
            self.pwd = pwd
            self.sop = sop
            self.sop_geo = sop.geometry()
            self.initial_sel = sel
            self.initial_sel_type = sel.selectionType()
            self.initial_items = sel.selectionString(self.sop_geo, force_numeric=True)
            return True
        return False
    
    def _classic_deform(self, scene_viewer, bend=False, twist=False, taper=False, length_scale=False, tapermode=0):
        sop, sel, pwd = geo_utils.sop_selection(scene_viewer)
        if sop is not None:
            geo = sop.geometry()
                
            if sel.selectionType() != hou.geometryType.Points:
                sel = sel.freeze()
                sel.convert(geo, hou.geometryType.Points)
            
            points = sel.selectionString(geo, force_numeric=True, asterisk_to_select_all=True)
            
            prompts = [
            "Select start of deformation. Press Enter or Escape to deform the entire geometry.",
            "Select end of deformation. Press Enter or Escape to deform the entire geometry.",
            "Select right direction of deformation. Press Enter or Escape to deform the entire geometry.",
            ]

            positions, directions = geo_utils.get_bound_positions_and_directions(scene_viewer, sop, points, prompts=prompts)

            if positions is None:
                bound = sop.createOutputNode("bound")
                bound.setParms({ "group": points, "grouptype": 3, "orientedbbox": True })
                bound_geo = bound.geometry()
                start_pos = bound_geo.prim(4).positionAtInterior(0.5, 0.5)
                end_pos = bound_geo.prim(5).positionAtInterior(0.5, 0.5)
                right_pos = bound_geo.prim(1).positionAtInterior(0.5, 0.5)
                bound.destroy()
            else:
                start_pos, end_pos, right_pos = positions

            uo = (end_pos - start_pos)
            right = uo.cross(right_pos - start_pos).cross(uo).normalized()
            length = uo.length()
            uo_norm = uo.normalized()

            bend_sop = sop.createOutputNode("bend")

            bend_sop.setParms({ "group": points, "grouptype": 3, "upvectorcontrol": 3,
                            "enablebend": bend, "enabletwist": twist, "enabletaper": taper, "enablelengthscale": length_scale,
                            "originx": start_pos[0], "originy": start_pos[1], "originz": start_pos[2],
                            "upx": right[0], "upy": right[1], "upz": right[2],
                            "dirx": uo_norm[0], "diry": uo_norm[1], "dirz": uo_norm[2],
                            "length": length, "tapermode": tapermode })

            bend_sop.setDisplayFlag(True)
            bend_sop.setRenderFlag(True)
            bend_sop.setCurrent(True, True)
            scene_viewer.enterCurrentNodeState()

    def _advanced_deform(self, scene_viewer, node_type_name):
        sop, sel, pwd = geo_utils.sop_selection(scene_viewer)
        if sop is not None:
            geo = sop.geometry()
            if sel.selectionType() != hou.geometryType.Points:
                sel = sel.freeze()
                sel.convert(geo, hou.geometryType.Points)      
            pts = sel.selectionString(geo, force_numeric=True)
            sop = sop.createOutputNode(node_type_name)
            sop.parm("group").set(pts)
            with hou.RedrawBlock() as rb:
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setCurrent(True, True)
            scene_viewer.enterCurrentNodeState()
        return sop

    def _select_item(self, scene_viewer, prompt, geometry_type):
        pre_higlight = self.sop.isHighlightFlagSet()
        pre_pick_type = scene_viewer.pickGeometryType()
        self.sop.setHighlightFlag(False)
        try:
            gs = scene_viewer.selectGeometry(prompt, geometry_types=(geometry_type,),
                                                  use_existing_selection=False, quick_select=True,
                                                  consume_selections=False)
            return gs.selections()[0]
        
        except:
            scene_viewer.setPickGeometryType(self.initial_sel_type)
            hou.ui.waitUntil(lambda: True)
            scene_viewer.setCurrentState("select")
            return None
        
        finally:
            try:
                self.sop.setHighlightFlag(pre_higlight)
                scene_viewer.setPickGeometryType(pre_pick_type)
            except:
                pass


    def stash_history(self, scene_viewer):
        selected_subnets = [node for node in hou.selectedNodes() if node.type().name() == "subnet" and node.type().category() == geo_utils._sop_category]

        if selected_subnets:
            for subnet in selected_subnets:
                is_dn = subnet.isDisplayFlagSet()
                name = subnet.name()
                stash = scene_viewer.pwd().createNode("stash", name)
                geo = subnet.geometry()
                stash.parm("stash").set(geo)
                network.catch_outputs(subnet, stash)
                pos = subnet.position()
                stash.setPosition(pos)
                subnet.destroy()
                stash.setName(name)
                
                if is_dn:
                    stash.setDisplayFlag(True)
                    stash.setRenderFlag(True)
                
                stash.setCurrent(True, False)
        else:
            sop = geo_utils.get_sop(scene_viewer)
            if sop is not None:
                sop.setCurrent(True, True)
                geo = sop.geometry().freeze()

                for group in geo.pointGroups() + geo.edgeGroups() + geo.primGroups():
                    if group.name().startswith("__"):
                        group.destroy()
                
                parent = sop.parent()
                parent.deleteItems(parent.children())
                stash = parent.createNode("stash", "geometry1")
                stash.parm("stash").set(geo)
                hou.ui.waitUntil(lambda: True)
                stash.setCurrent(True, True)
                ui.home_selected()

    def pack_history(self, scene_viewer):
        sop = geo_utils.get_sop(scene_viewer)
        if sop is not None:
            pwd = scene_viewer.pwd()
            children = pwd.children()
            if children:
                ancestors = sop.inputAncestors()
                
                with hou.RedrawBlock() as rb:
                    if ancestors and ancestors[-1].type().name() == "subnet" and not ancestors[-1].isHardLocked():
                        subnet = ancestors[-1]
                        subnet_sop = subnet.displayNode()
                        if subnet_sop is not None:
                            nodes = (sop,) + ancestors[:-1]
                            new_subnet = pwd.collapseIntoSubnet(nodes, pwd.name() + "_edit1")
                            new_subnet = hou.moveNodesTo((new_subnet,), subnet)[0]
                            new_subnet.setInput(0, subnet_sop)
                            new_subnet.moveToGoodPosition()
                            new_subnet.setHardLocked(True)
                            typ = scene_viewer.pickGeometryType()
                            scene_viewer.setPwd(pwd)
                            scene_viewer.setCurrentState("select")
                            sel = hou.Selection(typ)
                            scene_viewer.setCurrentGeometrySelection(typ, (subnet_sop,), (sel,))
                    else:
                        new_subnet = pwd.collapseIntoSubnet(children, pwd.name() + "_edit1")
                        new_subnet.setHardLocked(True)
                        s = pwd.collapseIntoSubnet((new_subnet,), pwd.name() + "_history")

            ui.home_selected()
    
    def clean_history(self, scene_viewer):
        pwd = scene_viewer.pwd()
        if pwd.childTypeCategory() == geo_utils._sop_category:
            sop = pwd.displayNode()
            if sop is not None:
                items = list(set(pwd.glob("* ^_*")) - set(sop.inputAncestors()) - set([sop]))
                if items:
                    pwd.deleteItems(items)
                    sop.setCurrent(True, True)
                    pwd.layoutChildren()
                    ui.home_selected()

    def merge_nodes(self, scene_viewer, node_type_name="merge"):
        pwd = scene_viewer.pwd()
        sel_nodes = hou.selectedNodes()
        nodes = [node for node in (sel_nodes or pwd.children()) if node.type().name()=="geo"]
        # OBJ
        if nodes:
            parent = nodes[0].parent()
            null = parent.createNode("null", "merged_objects1")
            global_center = hou.Vector3()
            for node in nodes:
                sop = node.displayNode()
                if sop is not None:
                    global_center += sop.geometry().boundingBox().center() * node.worldTransform()

                node.setInput(0, null)

            global_center /= len(nodes)
            null.parm("childcomp").set(True)
            null.parmTuple("t").set(global_center)
            null.parm("childcomp").set(False)
            null.setCurrent(True, True)
            parent.layoutChildren( [null] + nodes )
            ui.home_selected()

        # SOP
        elif len(sel_nodes) > 1 and sel_nodes[0].type().category() == geo_utils._sop_category:
            sop = sel_nodes[0]
            m = sop.createOutputNode(node_type_name)
            for node in sel_nodes[1:]:
                m.setNextInput(node)
            m.moveToGoodPosition()
            m.setDisplayFlag(True)
            m.setRenderFlag(True)
            m.setCurrent(True, True)
            ui.home_selected()

    def switch_nodes(self, scene_viewer):
        self.merge_nodes(scene_viewer, node_type_name="switch")

    def delete_attribs(self, scene_viewer):
        sop = geo_utils.get_sop(scene_viewer)
        if sop is not None:
            sop = sop.createOutputNode("attribdelete")
            sop.setParms({ "ptdel": "*", "vtxdel": "*", "primdel": "*", "dtldel": "*" })
            sop.setDisplayFlag(True)
            sop.setRenderFlag(True)
            sop.setCurrent(True, True)

    def delete_groups(self, scene_viewer):
        sop = geo_utils.get_sop(scene_viewer)
        if sop is not None:
            sop = sop.createOutputNode("groupdelete")
            sop.parm("group1").set("*")
            sop.setDisplayFlag(True)
            sop.setRenderFlag(True)
            sop.setCurrent(True, True)

    def _create_material_node(self):
        mat = hou.node("/mat").createNode("principledshader::2.0")
        mat.setParms({"basecolorr": 0.4, "basecolorg": 0.4, "basecolorb": 0.4, "rough": 0.5, "ior": 1.5})
        mat.moveToGoodPosition()
        return mat, mat.path()

    def _get_material_node(self):
        mat_path = hou.ui.selectNode(initial_node=hou.node("/mat/"), title="Select Material Node")
        mat = hou.node(mat_path)
        if mat is not None:
            mat_type = mat.type()
            if mat is not None and mat_type.category() != hou.managerNodeTypeCategory() and not mat_type.isManager():
                return mat, mat_path
        return None, None

    def _get_material_sop_and_parms(self, sop):
        if sop.type().name() == "material":
            num = sop.evalParm("num_materials") + 1
            nums = str(num)
            sop.parm("num_materials").set(num)
            return sop, sop.parm("group" + nums), sop.parm("shop_materialpath" + nums)
        
        sop = sop.createOutputNode("material")
        sop.setDisplayFlag(True)
        sop.setRenderFlag(True)
        sop.setCurrent(True, True)
        return sop, sop.parm("group1"), sop.parm("shop_materialpath1")

    def _pick_material(self, scene_viewer):
        mat_path = ""
        
        try:
            scene_viewer.selectPositions(prompt="Pick the face with material.", position_type=hou.positionType.ViewportXY)[0]
            ui.run_internal_command("h.pane.gview.state.view.set_active_port")
            vp = scene_viewer.curViewport()
            pos = ui.qtg.QCursor.pos()
            mouse_widget = ui.get_scene_viewer_mouse_widget()
            pos = mouse_widget.mapFromGlobal(pos)
            x = pos.x()
            y =  mouse_widget.height() - pos.y()
        except:
            return None

        node = vp.queryNodeAtPixel(x, y)
        if node is not None:
            prim = vp.queryPrimAtPixel(node, x, y)
            if prim is not None:
                try:
                    mat_path = prim.attribValue("shop_materialpath")
                except hou.OperationFailed:
                    pass

                if not mat_path:
                    pwd = geo_utils.ancestor_object(node)
                    mat_path = pwd.evalParm("shop_materialpath")
        try:
            node = hou.node(mat_path)
            node.cookCount()
            return node
        except:
            return None

    def pick_material(self, scene_viewer, duplicate=False):
        pwd = scene_viewer.pwd()
        child_cat = pwd.childTypeCategory()

        mat_path = ""
        if child_cat == geo_utils._obj_category:
            nodes = [node for node in hou.selectedNodes() if node.type().name() == "geo"]
            if nodes:
                mat = self._pick_material(scene_viewer)

                if mat is None:
                    mat_path = ""
                elif duplicate:
                    mat_path = hou.copyNodesTo([mat], mat.parent())[0].path()
                else:
                    mat_path = mat.path()

                with hou.RedrawBlock() as rb:
                    for node in nodes:
                        node.parm("shop_materialpath").set(mat_path)
                        sop = node.displayNode()
                        if sop is not None and sop.geometry().findPrimAttrib("shop_materialpath"):
                            sop = sop.createOutputNode("attribute", "delete_materials1")
                            sop.parm("primdel").set("shop_materialpath")
                            sop.setDisplayFlag(True)
                            sop.setRenderFlag(True)
                            sop.setCurrent(True, True)

                    scene_viewer.setCurrentState("select")
                    
                    if duplicate and mat_path:
                        mat = hou.node(mat_path)
                        mat.setCurrent(True, True)
                    else:
                        scene_viewer.setPwd(pwd)
        else:
            sop, sel, pwd = geo_utils.sop_selection(scene_viewer)
            if sop is not None:
                typ = sel.selectionType()
                geo = sop.geometry()
                items = sel.selectionString(geo, force_numeric=True)

                if typ == hou.geometryType.Primitives:
                    mat = self._pick_material(scene_viewer)

                    with hou.RedrawBlock() as rb:
                        if mat is None:
                            mat_path = ""
                        elif duplicate:
                            mat_path = hou.copyNodesTo([mat], mat.parent())[0].path()
                        else:
                            mat_path = mat.path()

                        # PIECE
                        if items:
                            sop, gparm, mparm = self._get_material_sop_and_parms(sop)
                            gparm.set(items)
                            mparm.set(mat_path)

                        # ALL POLYGONS
                        else:
                            if geo.findPrimAttrib("shop_materialpath"):
                                sop = sop.createOutputNode("attribute", "delete_materials1")
                                sop.parm("primdel").set("shop_materialpath")
                                sop.setDisplayFlag(True)
                                sop.setRenderFlag(True)
                                sop.setCurrent(True, True)

                            pwd.parm("shop_materialpath").set(mat_path)

                        pwd.displayNode().setCurrent(True, True)
                        scene_viewer.enterCurrentNodeState()
                        scene_viewer.setCurrentState("select")
                        scene_viewer.setCurrentGeometrySelection(typ, (sop,), (hou.Selection(typ),))

                        if duplicate and mat_path:
                            mat = hou.node(mat_path)
                            mat.setCurrent(True, True)

    def pick_new_material(self, scene_viewer):
        self.pick_material(scene_viewer, duplicate=True)

    def new_material(self, scene_viewer, existing=False):
        pwd = scene_viewer.pwd()
        child_cat = pwd.childTypeCategory()

        if child_cat == geo_utils._obj_category:
            nodes = [ node for node in hou.selectedNodes() if node.type().name() == "geo" ]
            if nodes:
                if existing:
                    mat, mat_path = self._get_material_node()
                else:    
                    mat, mat_path = self._create_material_node()

                if mat is not None:
                    # UPDATE SCENE VIEWER
                    local_mats = False
                    for node in nodes:
                        node.parm("shop_materialpath").set(mat_path)
                        sop = node.displayNode()
                        if not local_mats and sop is not None and sop.geometry().findPrimAttrib("shop_materialpath"):
                            local_mats = True

                    if not existing:
                        mat.setCurrent(True, True)

        else:
            sop, sel, pwd = geo_utils.sop_selection(scene_viewer)
            if sop is not None:
                typ = sel.selectionType()
                geo = sop.geometry()

                if geo_utils.is_all_selected(sel, geo):
                    if existing:
                        mat, mat_path = self._get_material_node()
                    else:    
                        mat, mat_path = self._create_material_node()

                    if mat is not None:
                        if geo.findPrimAttrib("shop_materialpath"):
                            sop = sop.createOutputNode("attribute", "delete_materials1")
                            sop.parm("primdel").set("shop_materialpath")
                            sop.setDisplayFlag(True)
                            sop.setRenderFlag(True)
                            sop.setCurrent(True, True)

                        pwd.parm("shop_materialpath").set(mat_path)
                        
                    if not existing:
                        mat.setCurrent(True, True)

                elif typ != hou.geometryType.Primitives:
                    scene_viewer.setPromptMessage("Works only with polygons or empty selections!")

                else:
                    faces = sel.selectionString(geo, force_numeric=True)

                    if existing:
                        mat, mat_path = self._get_material_node()
                    else:    
                        mat, mat_path = self._create_material_node()

                    if mat is not None:
                        sop, gparm, mparm = self._get_material_sop_and_parms(sop)
                        gparm.set(faces)
                        mparm.set(mat_path)
                        
                        if not existing:
                            mat.setCurrent(True, True)

    def clear_material(self, scene_viewer):
        pwd = scene_viewer.pwd()
        child_cat = pwd.childTypeCategory()

        if child_cat == geo_utils._obj_category:
            for node in hou.selectedNodes():
                parm = node.parm("shop_materialpath")
                if parm is not None:
                    parm.set("")

        else:
            sop, sel, pwd = geo_utils.sop_selection(scene_viewer)
            if sop is not None:
                typ = sel.selectionType()
                geo = sop.geometry()
                if (geo_utils.is_all_selected(sel, geo) or typ == hou.geometryType.Primitives) and geo.findPrimAttrib("shop_materialpath") is not None:
                    faces = sel.selectionString(geo, force_numeric=True)
                    sop = sop.createOutputNode("attribwrangle", "flatten_uv1")
                    sop.setParms({ "group": faces, "class": 1, "snippet": 's@shop_materialpath = "";' })

                    with hou.RedrawBlock() as rb:
                        sop.setDisplayFlag(True)
                        sop.setRenderFlag(True)
                        sop.setCurrent(True, True)

    def get_material(self, scene_viewer):
        self.new_material(scene_viewer, existing=True)

    def edit_material(self, scene_viewer):
        pwd = scene_viewer.pwd()
        child_cat = pwd.childTypeCategory()

        if child_cat == geo_utils._obj_category:
            nodes = [node for node in hou.selectedNodes() if node.type().name() == "geo"]
            if nodes:
                mat_path = nodes[0].evalParm("shop_materialpath")
                if mat_path:
                    mat = hou.node(mat_path)
                    mat.setCurrent(True, True)
        else:
            sop, sel, pwd = geo_utils.sop_selection(scene_viewer)
            if sop is not None:
                typ = sel.selectionType()
                geo = sop.geometry()
                items = sel.selectionString(geo, force_numeric=True)
            
                if typ == hou.geometryType.Primitives:
                    if geo.findPrimAttrib("shop_materialpath"):
                        mat_path = sel.prims(geo)[0].stringAttribValue("shop_materialpath")
                        if mat_path:
                            mat = hou.node(mat_path)
                            mat.setCurrent(True, True)
                        else:
                            mat_path = pwd.evalParm("shop_materialpath")
                            if mat_path:
                                mat = hou.node(mat_path)
                                mat.setCurrent(True, True)

    def _flatten(self, scene_viewer, o, d):
        scene_viewer.setCurrentState("select")
        scene_viewer.setCurrentGeometrySelection(self.initial_sel_type, (self.sop,), (self.initial_sel,))
        sop = self.sop.createOutputNode("xformaxis", "flatten1")
        
        if self.initial_sel_type == hou.geometryType.Primitives:
            grouptype = 4
        elif self.initial_sel_type == hou.geometryType.Edges:
            grouptype = 2
        else:
            grouptype = 3

        sop.setParms({"group": self.initial_items, "grouptype": grouptype, "scale": 0.0})
        sop.parmTuple("orig").set(o)
        sop.parmTuple("dir").set(d)

        with hou.RedrawBlock() as rb:
            sop.setDisplayFlag(True)
            sop.setHighlightFlag(True)
            sop.setRenderFlag(True)
            sop.setCurrent(True, True)
            scene_viewer.enterCurrentNodeState()
            hou.ui.waitUntil(lambda: True)
            scene_viewer.setCurrentState("select")

    def _arrow_flatten(self, scene_viewer, axis, direction):
        viewport = scene_viewer.curViewport()
        
        if viewport.type() == hou.geometryViewportType.UV:
            sop = scene_viewer.currentNode()
            geo = sop.geometry()
            
            try:
                sel = scene_viewer.currentGeometrySelection().selections()[0]
            except:
                try:
                    sel = geo.selection()
                except:
                    return

            if sel is not None and sel.selectionType() == hou.geometryType.Vertices:
                items = sel.selectionString(geo, force_numeric=True)

                if axis == 0:
                    axis_char = "x"
                else:
                    axis_char = "y"

                if direction < 0:
                    big = 999999
                    op_char = "<"
                else:
                    big = 0
                    op_char = ">"

                aw_snippet = """int vtxs[] = expandvertexgroup(0, "%s");
vector uv;
float target = %f;
foreach(int vtx; vtxs)
{
uv = vertex(0, "uv", vtx)[0];
if(uv.%s %s target)
    target = uv.%s;
}

int prim, i;
foreach(int vtx; vtxs)
{
prim = vertexprim(0, vtx);
uv = vertex(0, "uv", vtx);
uv.%s = target;
i = vertexprimindex(0, vtx);
setvertexattrib(0, "uv", prim, i, uv);
}""" % (items, big, axis_char, op_char, axis_char, axis_char)

                sop = sop.createOutputNode("attribwrangle", "flatten_uvs1")
                sop.setParms({ "class": 0, "snippet": aw_snippet })

                with hou.RedrawBlock() as rb:
                    sop.setDisplayFlag(True)
                    sop.setRenderFlag(True)
                    sop.setCurrent(True, True)
                    scene_viewer.setPickGeometryType(hou.geometryType.Vertices)
                    scene_viewer.setCurrentState("select")
                    scene_viewer.setCurrentGeometrySelection(hou.geometryType.Vertices, (sop,), (sel,))

        elif self._check(scene_viewer):
            o = geo_utils.sop_selection_center(self.sop, self.initial_sel)
            
            self.sop_geo = self.sop_geo.freeze()
            self.sop_geo.transform(self.pwd.worldTransform())

            if self.initial_sel_type == hou.geometryType.Points:
                bb = self.sop_geo.pointBoundingBox(self.initial_items)
            
            elif self.initial_sel_type == hou.geometryType.Primitives:
                bb = self.sop_geo.primBoundingBox(self.initial_items)
            
            else:
                sel = self.initial_sel.freeze()
                sel.convert(self.sop_geo, hou.geometryType.Points)
                bb = self.sop_geo.pointBoundingBox(sel.selectionString(self.sop_geo, force_numeric=True))

            o = bb.center()
            
            d = ui.get_hvd(scene_viewer, True)[axis]
            d_ = ui.get_hvd(scene_viewer, False)[axis]

            if direction < 0:
                m = bb.minvec()
                M = bb.maxvec()
            else:
                m = bb.maxvec()
                M = bb.minvec()

            if d[0]:
                if d_[0] > 0:
                    o = hou.Vector3(m[0], o[1], o[2]) 
                else:
                    o = hou.Vector3(M[0], o[1], o[2]) 
            
            elif d[1]:
                if d_[1] > 0:
                    o = hou.Vector3(o[0], m[1], o[2]) 
                else:
                    o = hou.Vector3(o[0], M[1], o[2]) 
                        
            else:
                if d_[2] > 0:
                    o = hou.Vector3(o[0], o[1], m[2]) 
                else:
                    o = hou.Vector3(o[0], o[1], M[2]) 
                        
            o *= self.pwd.worldTransform().inverted()
            d *= self.pwd.worldTransform().transposed()
            
            self._flatten(scene_viewer, o, d)

    def flatten_h(self, scene_viewer, axis=1):
        if self._check(scene_viewer):
            o = geo_utils.sop_selection_center(self.sop, self.initial_sel)
            sel = self._select_item(scene_viewer, "Select an origin point", hou.geometryType.Points)
            if sel is not None:
                o = sel.points(self.sop_geo)[0].position()
            d = ui.get_hvd(scene_viewer, True)[axis]
            d *= self.pwd.worldTransform().transposed()
            self.flatten(scene_viewer, o, d)

    def flatten_v(self, scene_viewer):
        self.flatten_h(scene_viewer, axis=0)

    def flatten_auto(self, scene_viewer):
        if self._check(scene_viewer):
            n, c = geo_utils.get_selection_normal_and_center(self.sop, self.initial_sel, self.sop_geo)
            n = hou.Vector3(0.0, 0.0, 1.0) * (hou.Vector3(0.0, 0.0, 1.0).matrixToRotateTo(n) * hou.hmath.buildTranslate(c)).inverted().transposed()
            self._flatten(scene_viewer, c, n)

    def flatten_by_edge(self, scene_viewer):
        if self._check(scene_viewer):
            sel = self._select_item(scene_viewer, "Select an edge.", hou.geometryType.Edges)
            if sel is not None:
                edge = sel.edges(self.sop_geo)[0]
                pt1, pt2 = edge.points()
                pt1_pos = pt1.position()
                pt2_pos = pt2.position()
                edge_vec = pt2_pos - pt1_pos

                edge_prims = edge.prims()
                if len(edge_prims) == 1:
                    normal = edge_prims[0].normal()
                else:
                    if self.initial_sel_type == hou.geometryType.Primitives:
                        prims_str = "{} {}".format(edge_prims[0].number(), edge_prims[1].number())
                        sel1 = hou.Selection(self.sop_geo, hou.geometryType.Primitives, prims_str)
                        sel1.combine(self.sop_geo, self.initial_sel, hou.pickModifier.Intersect)
                        count = sel1.numSelected()
                        if count == 1:
                            normal = sel1.prims(self.sop_geo)[0].normal()
                        else:
                            normal = (edge_prims[0].normal() + edge_prims[1].normal()) / 2.0
                    else:
                        sel = self._select_item(scene_viewer, "Select support face or press Escape to use an average of edge faces", hou.geometryType.Primitives)
                        if sel is None:
                            normal = (edge_prims[0].normal() + edge_prims[1].normal()) / 2.0
                        else:
                            normal = sel.prims(self.sop_geo)[0].normal()

                d = edge_vec.cross(normal)
                d = d.cross(edge_vec)
                o = (pt1_pos + pt2_pos) / 2.0
                self._flatten(scene_viewer, o, d)

    def flatten_by_edge_dir(self, scene_viewer):
        if self._check(scene_viewer):
            sel = self._select_item(scene_viewer, "Select an edge.", hou.geometryType.Edges)
            if sel is not None:
                edge = sel.edges(self.sop_geo)[0]
                pt1, pt2 = edge.points()
                pt1_pos = pt1.position()
                pt2_pos = pt2.position()
                d = pt2_pos - pt1_pos

                sel = self._select_item(scene_viewer, "Select an orgin point.", hou.geometryType.Points)
                if sel is None:
                    o = (pt1_pos + pt2_pos) / 2.0
                else:
                    o = sel.points(self.sop_geo)[0].position()

                self._flatten(scene_viewer, o, d)

    def flatten_by_face_normal(self, scene_viewer):
        if self._check(scene_viewer):
            sel = self._select_item(scene_viewer, "Select a face.", hou.geometryType.Primitives)
            if sel is not None:
                face = sel.prims(self.sop_geo)[0]
                sel = self._select_item(scene_viewer, "Select an origin point.", hou.geometryType.Points)
                if sel is not None:
                    self._flatten(scene_viewer, sel.points(self.sop_geo)[0].position(), face.normal())

    def flatten_left(self, scene_viewer):
        self._arrow_flatten(scene_viewer, 0, -1)

    def flatten_right(self, scene_viewer):
        self._arrow_flatten(scene_viewer, 0, 1)

    def flatten_up(self, scene_viewer):
        self._arrow_flatten(scene_viewer, 1, 1)

    def flatten_down(self, scene_viewer):
        self._arrow_flatten(scene_viewer, 1, -1)

    def twist(self, scene_viewer):
        self._classic_deform(scene_viewer, twist=True)

    def taper(self, scene_viewer):
        self._classic_deform(scene_viewer, taper=True)

    def bend(self, scene_viewer):
        self._classic_deform(scene_viewer, bend=True)

    def length_scale(self, scene_viewer):
        self._classic_deform(scene_viewer, length_scale=True)

    def size(self, scene_viewer):
        sop = self._advanced_deform(scene_viewer, "modeler::size_deform")
        if sop is not None:
            sop.parm("init").pressButton()

    def falloff_xform(self, scene_viewer):
        sop, sel, pwd = geo_utils.sop_selection(scene_viewer)
        if sop is not None:
            geo = sop.geometry()
            sel_type = sel.selectionType()
            if sel_type == hou.geometryType.Primitives:
                faces = True
            elif sel_type == hou.geometryType.Points:
                faces = False
            else:
                return

            sop = sop.createOutputNode("modeler::falloff_xform")
            sop.setParms({ "group": sel.selectionString(geo, force_numeric=True), "faces": faces })
            
            with hou.RedrawBlock() as rb:
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setCurrent(True, True)
            
            scene_viewer.enterCurrentNodeState()

    def mountain(self, scene_viewer):
        sop, sel, pwd = geo_utils.sop_selection(scene_viewer)
        if sop is not None:
            geo = sop.geometry()
            typ = sel.selectionType()
            if typ != hou.geometryType.Points:
                sel = sel.freeze()
                sel.convert(geo, hou.geometryType.Points)
            
            items = sel.selectionString(geo, force_numeric=True)
            sop = sop.createOutputNode("mountain::2.0")
            sop.parm("group").set(items)
            
            # with hou.RedrawBlock() as rb:
            sop.setDisplayFlag(True)
            sop.setRenderFlag(True)
            sop.setCurrent(True, True)
            scene_viewer.enterCurrentNodeState()

    def lattice(self, scene_viewer):
        pwd = scene_viewer.pwd()

        # START
        if pwd.userData("lattice") is None:
            if self._check(scene_viewer):
                if self.initial_sel_type != hou.geometryType.Points:
                    sel = self.initial_sel.freeze()
                    sel.convert(self.sop_geo, hou.geometryType.Points)
                    self.initial_items = sel.selectionString(self.sop_geo, force_numeric=True)

                lattice_object = hou.node("/obj").createNode("geo", "lattice_object1")
                lattice_object.setUserData("lattice", "")
                lattice_object.moveToGoodPosition()

                om = lattice_object.createNode("object_merge", "import_object_to_deform")
                om.setParms({ "objpath1": self.sop.path(), "xformtype": 1 })
                
                bound = om.createOutputNode("bound", "lattice")
                bound.setParms({ "group": self.initial_items, "grouptype": 3, \
                                 "dodivs": True, "divsx": 1, "divsy": 1, "divsz": 1, \
                                 "minsizex": 0.001, "minsizey": 0.001, "minsizez": 0.001 })
                
                bound_path = bound.path()

                lattice_sop = self.sop.createOutputNode("lattice")
                lattice_sop.parm("group").set(self.initial_items)
                lattice_sop.parm("divsx").setExpression( 'ch("{}/divsx")'.format(bound_path) )
                lattice_sop.parm("divsy").setExpression( 'ch("{}/divsy")'.format(bound_path) )
                lattice_sop.parm("divsz").setExpression( 'ch("{}/divsz")'.format(bound_path) )

                om1 = lattice_sop.createInputNode(1, "object_merge")
                om1.setParms({ "objpath1": bound.path(), "xformtype": 1 })
                
                om2 = lattice_sop.createInputNode(2, "object_merge")
                om2.setParms({ "objpath1": lattice_object.path(), "xformtype": 1 })
                
                lattice_sop.moveToGoodPosition()
                
                scene_viewer.setPickGeometryType(hou.geometryType.Points)
                
                with hou.RedrawBlock() as rb:
                    lattice_sop.setDisplayFlag(True)
                    lattice_sop.setRenderFlag(True)
                    bound.setDisplayFlag(True)
                    lattice_sop.setCurrent(True, True)
                    bound.setCurrent(True, True)

                    scene_viewer.setCurrentState("select")

        # FINISH
        else:
            om = pwd.children()[0]
            sop = hou.node( om.evalParm("objpath1") )
            lattice_sop = sop.outputs()[0]
            _, om1, om2 = lattice_sop.inputs()
            
            om1.setHardLocked(True)
            om2.setHardLocked(True)
            
            om1.parm("objpath1").set("")
            om2.parm("objpath1").set("")

            lattice_sop.parm("divsx").deleteAllKeyframes()
            lattice_sop.parm("divsy").deleteAllKeyframes()
            lattice_sop.parm("divsz").deleteAllKeyframes()

            result_subnet = sop.parent().collapseIntoSubnet([om1, om2, lattice_sop], "lattice_result1")
            result_subnet.moveToGoodPosition()
            result_subnet.setCurrent(True, True)

            scene_viewer.setCurrentState("select")
            
            pwd.destroy()

    def sym_box(self, scene_viewer):
        sop = hou.node("/obj").createNode("geo", "sym_box1").createNode("box")
        new_sop = sop.createOutputNode("modeler::symmetrize")

        _sym_setup_node(scene_viewer, sop, new_sop)

        new_sop.setDisplayFlag(True)
        new_sop.setRenderFlag(True)
        new_sop.setCurrent(True, True)
        scene_viewer.setCurrentState("select")

        _sym_update_instance_node(new_sop)


radial_menu_tools = RadialMenuTools()


###############################################################################
# VIEW TOOLS


_pre_align_camera = _aligned_vp = _aligned_vp_name = _pre_align_scene_viewer = None

def AlignView(mode):
    global _pre_align_camera, _aligned_vp, _aligned_vp_name, _pre_align_scene_viewer

    _aligned_vp = mode.scene_viewer.curViewport()
    
    # WRONG VIEWPORT TYPE
    if _aligned_vp.type() != hou.geometryViewportType.Perspective:
        mode.scene_viewer.setPromptMessage("Can't align this viewport. Change viewport type to perspective and try again")

    # ALREADY ALIGNED
    elif _pre_align_camera is not None:
        RestoreView()
    
    # ALIGN
    else:
        hvd = _aligned_vp.viewTransform().extractRotationMatrix3().asTupleOfTuples()
        view_right = hou.Vector3(hvd[0])
        view_top = hou.Vector3(hvd[1])
        view_depth = hou.Vector3(hvd[2])
        x = ui.numpy.abs(hvd[0])
        x_max_id = x.argmax()
        x.fill(0.0)
        y = ui.numpy.abs(hvd[1])
        y_max_id = y.argmax()
        y.fill(0.0)
        x[x_max_id] = 1.0
        y[y_max_id] = 1.0
        view_h_abs = hou.Vector3(x)
        view_v_abs = hou.Vector3(y)
        view_d_abs = hou.Vector3(ui.numpy.abs(ui.numpy.cross(x, y)))
        x[x_max_id] = ui.numpy.sign(hvd[0][x_max_id])
        y[y_max_id] = ui.numpy.sign(hvd[1][y_max_id])
        view_h = hou.Vector3(x)
        view_v = hou.Vector3(y)
        view_d = hou.Vector3(ui.numpy.cross(x, y))
        x = view_h[0], view_v[0], view_d[0]
        y = view_h[1], view_v[1], view_d[1]
        z = view_h[2], view_v[2], view_d[2]
        mat = hou.Matrix3((x, y, z))
        cam = _aligned_vp.defaultCamera()
        _pre_align_camera = cam.stash()
        cam.setRotation(mat)
        if not cam.isOrthographic():
            orthowidth = hou.Vector3(cam.translation()).distanceTo(hou.Vector3(cam.pivot()))
            cam.setOrthoWidth(orthowidth)
            cam.setPerspective(False)
        
        # MODIFY GRID
        m = _aligned_vp.viewTransform()
        m1 = hou.hmath.buildTranslate(m.extractTranslates()).inverted()
        mode.scene_viewer.referencePlane().setTransform(m * m1)

        _aligned_vp_name = _aligned_vp.name()

        _pre_align_scene_viewer = mode.scene_viewer

    return True

def RestoreView():
    global _pre_align_camera, _aligned_vp, _aligned_vp_name, _pre_align_scene_viewer

    if _pre_align_camera is not None:
        cam = _aligned_vp.defaultCamera()
        _pre_align_camera.setPivot(cam.pivot())                   
        _pre_align_camera.setTranslation(cam.translation())               
        _aligned_vp.setDefaultCamera(_pre_align_camera)
        _pre_align_camera = None

        _pre_align_scene_viewer.referencePlane().setTransform(hou.hmath.identityTransform() * hou.hmath.buildRotate(90, 0, 0))

ADD_TOOL(AlignView, "View")


def Frame(mode):
    mode.scene_viewer.curViewport().frameSelected()
    return True

ADD_TOOL(Frame, "View")


def FrameAll(mode):
    mode.scene_viewer.curViewport().frameAll()
    return True

ADD_TOOL(FrameAll, "View")


def HomeView(mode):
    mode.scene_viewer.curViewport().homeAll()
    return True
    
ADD_TOOL(HomeView, "View")


def OrthoView(mode):
    viewport = mode.scene_viewer.curViewport()
    
    if viewport.type() != hou.geometryViewportType.Perspective:
        mode.scene_viewer.setPromptMessage("Can't align this viewport. Change viewport type to perspective, and try again")

    elif _pre_align_camera is None or (_pre_align_camera is not None and viewport.name() != _aligned_vp_name):
        cam = viewport.defaultCamera()
        cam.setPerspective(cam.isOrthographic())
    return True

ADD_TOOL(OrthoView, "View")


_pre_wire_mode_dm = hou.glShadingType.SmoothWire

def WireGeometry(mode):
    global _pre_wire_mode_dm
    
    pwd = mode.scene_viewer.pwd()

    # INSIDE LATTICE OBJECT
    if pwd.userData("lattice") is not None:
        return WireObjects(mode)

    elif mode.scene_viewer.selectionMode() == hou.selectionMode.Geometry:
        ds = mode.scene_viewer.curViewport().settings().displaySet(hou.displaySetType.DisplayModel)
        shade_mode = ds.shadedMode()

        if shade_mode == hou.glShadingType.Wire:
            ds.setShadedMode(_pre_wire_mode_dm)
        else:
            ds.setShadedMode(hou.glShadingType.Wire)
            
            _pre_wire_mode_dm = shade_mode
    
    return True
    
ADD_TOOL(WireGeometry, "View")


_pre_wire_mode_os = hou.glShadingType.SmoothWire

def WireObjects(mode):
    global _pre_wire_mode_os

    settings = mode.scene_viewer.curViewport().settings()
    ds1 = settings.displaySet(hou.displaySetType.SceneObject)
    ds2 = settings.displaySet(hou.displaySetType.GhostObject)
    shade_mode = ds1.shadedMode()

    if shade_mode == hou.glShadingType.Wire:
        ds1.setShadedMode(_pre_wire_mode_os)
        ds2.setShadedMode(_pre_wire_mode_os)
    else:
        ds1.setShadedMode(hou.glShadingType.Wire)
        ds2.setShadedMode(hou.glShadingType.Wire)
        
        _pre_wire_mode_os = shade_mode
    
    return True
    
ADD_TOOL(WireObjects, "View")


def WireShadeGeometry(mode):
    pwd = mode.scene_viewer.pwd()

    # INSIDE LATTICE OBJECT
    if pwd.userData("lattice") is not None:
        return WireShadeObjects(mode)
    
    elif mode.scene_viewer.selectionMode() == hou.selectionMode.Geometry:
        settings = mode.scene_viewer.curViewport().settings()
                
        ds = settings.displaySet(hou.displaySetType.DisplayModel)

        if ds.shadedMode() == hou.glShadingType.SmoothWire:
            ds.setShadedMode(hou.glShadingType.Smooth)
        else:
            ds.setShadedMode(hou.glShadingType.SmoothWire)
    
    return True

ADD_TOOL(WireShadeGeometry, "View")


def WireShadeObjects(mode):
    settings = mode.scene_viewer.curViewport().settings()
    
    ds1 = settings.displaySet(hou.displaySetType.SceneObject)
    ds2 = settings.displaySet(hou.displaySetType.GhostObject)

    if ds1.shadedMode() == hou.glShadingType.SmoothWire:
        ds1.setShadedMode(hou.glShadingType.Smooth)
        ds2.setShadedMode(hou.glShadingType.Smooth)
    else:
        ds1.setShadedMode(hou.glShadingType.SmoothWire)
        ds2.setShadedMode(hou.glShadingType.SmoothWire)
    return True

ADD_TOOL(WireShadeObjects, "View")


def HideOtherObjects(mode):
    hou.hscript("vieweroption -a 0 %s.%s.world" % (hou.ui.curDesktop().name(), hou.ui.paneTabOfType(hou.paneTabType.SceneViewer).name()))
    return True

ADD_TOOL(HideOtherObjects, "View")


def ShowAllObjects(mode):
    hou.hscript("vieweroption -a 1 %s.%s.world" % (hou.ui.curDesktop().name(), hou.ui.paneTabOfType(hou.paneTabType.SceneViewer).name()))
    return True

ADD_TOOL(ShowAllObjects, "View")


def GhostOtherObjects(mode):
    hou.hscript("vieweroption -a 2 %s.%s.world" % (hou.ui.curDesktop().name(), hou.ui.paneTabOfType(hou.paneTabType.SceneViewer).name()))
    return True

ADD_TOOL(GhostOtherObjects, "View")


class _PreviewSubdivided():
    _subdivide_sop = None
    _iterations = 2

    def start(self, scene_viewer, shade_mode):
        with hou.undos.group("Modeler: Preview Subdivided"):
            if self._subdivide_sop is None:
                sop = scene_viewer.currentNode()
                
                try:
                    self._subdivide_sop = sop.createOutputNode("subdivide", "__preview_subdivided__")
                except:
                    scene_viewer.setPromptMessage("Something wrong!")
                    return

                self._subdivide_sop.parm("iterations").set(self._iterations)

                with hou.RedrawBlock() as rb:
                    self._subdivide_sop.setCurrent(True, True)
                    self._subdivide_sop.setDisplayFlag(True)

                self._viewport = scene_viewer.curViewport()
                self._vp_settings = self._viewport.settings()
                self._display_set = self._vp_settings.displaySet(hou.displaySetType.DisplayModel)
                self._shade_mode = self._display_set.shadedMode()
                self._follow_sel = self._vp_settings.guideEnabled(hou.viewportGuide.FollowSelection)

                self._vp_settings.enableGuide(hou.viewportGuide.FollowSelection, False)
                self._display_set.setShadedMode(shade_mode)

            else:
                try:
                    self._iterations = self._subdivide_sop.evalParm("iterations")
                    with hou.RedrawBlock() as rb:
                        i = self._subdivide_sop.inputs()[0]
                        i.setCurrent(True, True)
                        self._subdivide_sop.destroy()
            
                except hou.ObjectWasDeleted:
                    pass
                
                finally:
                    self._vp_settings.enableGuide(hou.viewportGuide.FollowSelection, self._follow_sel)
                    self._display_set.setShadedMode(self._shade_mode)
                    self._subdivide_sop = None

        return True

_preview_subdivided = _PreviewSubdivided()


def PreviewSubdivided(mode):
    return _preview_subdivided.start(mode.scene_viewer, shade_mode=hou.glShadingType.Smooth)

ADD_TOOL(PreviewSubdivided, "View")


def PreviewSubdividedWired(mode):
    return _preview_subdivided.start(mode.scene_viewer, shade_mode=hou.glShadingType.SmoothWire)

ADD_TOOL(PreviewSubdividedWired, "View")


def ViewSubdivide(mode):
    pwd = mode.scene_viewer.pwd()

    # SOP
    if pwd.childTypeCategory() == geo_utils._sop_category and pwd.displayNode() is not None:
        nodes = [pwd]

    # OBJ
    else:
        nodes = [node for node in hou.selectedNodes() if node.type().name()=="geo"]

    if nodes:
        if nodes[0].evalParm("viewportlod") == 5:
            value1 = 0
            value2 = False
            value3 = "mantra_catclark"
        else:
            value1 = 5
            value2 = True
            value3 = "osd_catclark"
            
        for node in nodes:
            node.setParms({ "viewportlod": value1, "vm_rendersubd": value2, "vm_subdstyle": value3 })
    return True

ADD_TOOL(ViewSubdivide, "View")


def ViewInstanceSubdivide(mode):
    node = mode.scene_viewer.currentNode()

    if node.type().category() == geo_utils._sop_category:
        pwd = mode.scene_viewer.pwd()
        pwd_path = pwd.path()
        geo = node.geometry()

        instance_node = _sym_get_instance_node(node)

        if instance_node is not None:
            with hou.undos.group("Modeler: View Instance Subdivide"):
                viewportlod_parm = instance_node.parm("viewportlod")
                if viewportlod_parm is None:
                    with hou.RedrawBlock() as rb:
                        mode.scene_viewer.setPwd(instance_node.parent())
                        instance_node.setSelected(True, True)
                        ui.run_internal_command("h.pane.gview.increase_subd")
                        node.setCurrent(True, True)
                else:
                    if viewportlod_parm.eval() == 5:
                        viewportlod_parm.set(0)
                    else:
                        viewportlod_parm.set(5)
    return True

ADD_TOOL(ViewInstanceSubdivide, "View")


def ViewNormalsAngle(mode):
    viewports = mode.scene_viewer.viewports()
    cur_angle = str(viewports[0].settings().vertexNormalCuspAngle())
    result, value = hou.ui.readInput("Enter new value", buttons=("OK", "Cancel"), default_choice=0, close_choice=1, title="Vertex Normals Angle", initial_contents=cur_angle)
    if not result:
        hou.ui.waitUntil(lambda: True)
        try:
            value = float(value)
            for viewport in viewports:
                viewport.settings().vertexNormalCuspAngle(value)
        except:
            pass
    return True

ADD_TOOL(ViewNormalsAngle, "View")


def ShowGrid(mode):
    ui.run_internal_command("h.pane.gview.refplane")
    return True

ADD_TOOL(ShowGrid, "View")


def SideBySideLayout(mode):
    if mode.scene_viewer.viewportLayout() == hou.geometryViewportLayout.Single:
        mode.scene_viewer.setViewportLayout(hou.geometryViewportLayout.DoubleSide)
    else:
        mode.scene_viewer.setViewportLayout(hou.geometryViewportLayout.Single, 1)
        mode.scene_viewer.curViewport().changeType(hou.geometryViewportType.Perspective)
    return True

ADD_TOOL(SideBySideLayout, "View")


def MaximizeViewer(mode):
    pane = mode.scene_viewer.pane()
    mode.finish()
    if pane.isMaximized():
        pane.setIsMaximized(False)
    else:
        pane.setIsMaximized(True)
    ui.executeDeferred(mode.start)

ADD_TOOL(MaximizeViewer, "View")


def Backdrop(mode):
    mode.scene_viewer.runShelfTool("modeler::backdrop")
    return True

ADD_TOOL(Backdrop, "View")


def QLight(mode):
    mode.scene_viewer.runShelfTool("modeler::qlight")
    return True

ADD_TOOL(QLight, "View")


###############################################################################
# STATE


def _wheel_change_radius(node, wheel_dir):
    delta = 10.0
    rad = node.evalParm("rad")
    if rad == 0.0:
        if wheel_dir > 0:
            node.parm("rad").set(0.01)
    
    elif rad < 0.01 and wheel_dir < 0:
        node.parm("rad").set(0.0)
        
    else:
        rad = rad + wheel_dir * rad / delta
        node.parm("rad").set(rad)

def _wheel_change_scale(node, wheel_dir):
    if wheel_dir > 0:
        node.parm("scale").set(node.evalParm("scale") * 1.2)
    else:
        node.parm("scale").set(node.evalParm("scale") / 1.2)

def _wheel(mode, wheel_dir):
    state = mode.state()
    cur_node = mode.scene_viewer.currentNode()
    is_geo_container = cur_node.type().category() == geo_utils._obj_category

    # SUBDIVIDE | PREVIEW SUBDIVIDED
    if cur_node.name() == "__preview_subdivided__" or state == "subdivide":
        cur_node.parm("iterations").set(cur_node.evalParm("iterations") + wheel_dir)

    # SELECT STATE
    elif state == "select" and not is_geo_container:
        node_type_name = cur_node.type().name()

        # EDIT SOP RADIUS
        if node_type_name == "edit":
            _wheel_change_radius(cur_node, wheel_dir)

        # POLYSPLIT LOOPS
        elif node_type_name == "polysplit::2.0" and cur_node.evalParm("pathtype") == 1:
            cur_node.parm("numloops").set(max(0, cur_node.evalParm("numloops") + wheel_dir))
     
        # BOUND NODE (LATTICE)
        elif node_type_name == "bound":
            divs = cur_node.evalParm("divsx") + wheel_dir
            cur_node.parmTuple("divs").set((divs, divs, divs))

    # INTERACTIVE STATES
    elif state in ("modeler::extrude", "modeler::bevel", "modeler::hose", "modeler::thickness", "modeler::bridge"):
        cur_node.parm("divisions").set(cur_node.evalParm("divisions") + wheel_dir)
    
    # COPYXFORM STATE
    elif state == "copyxform":
        cur_node.parm("ncy").set(cur_node.evalParm("ncy") + wheel_dir)

    # POLYFILL STATE
    elif state == "polyfill":
        v = cur_node.evalParm("fillmode")
        if wheel_dir > 0:
            if v == 5:
                cur_node.parm("fillmode").set(0)
            else:
                cur_node.parm("fillmode").set(v + 1)
        else:
            if v == 0:
                cur_node.parm("fillmode").set(5)
            else:
                cur_node.parm("fillmode").set(v - 1)

    # EDGELOOP STATE
    elif state in ("edgeloop", "polysplit::2.0") and cur_node.evalParm("pathtype") == 1 and cur_node.evalParm("splitloc"):
        typ = mode.scene_viewer.pickGeometryType()
        sel = hou.Selection(typ)
        mode.scene_viewer.setCurrentState("select")
        mode.scene_viewer.setCurrentGeometrySelection(typ, (cur_node,), (sel,))

    # BOUND NODE (LATTICE)
    elif state == "bound":
        mode.scene_viewer.setCurrentState("select")
        divs = cur_node.evalParm("divsx") + wheel_dir
        cur_node.parmTuple("divs").set((divs, divs, divs))

    # QPRIMITIVE
    elif state == "modeler::qprimitive":
        cur_node.parm("res").set(cur_node.evalParm("res") + wheel_dir)

    # SOFT BOOLEAN
    elif state == "modeler::soft_boolean":
        cur_node.parm("fillet_profile_quality").set(cur_node.evalParm("fillet_profile_quality") + wheel_dir)

    # INSERT MESH
    elif state == "modeler::insert_mesh":
        cur_node.parm("subdivide_inserted").set(cur_node.evalParm("subdivide_inserted") + wheel_dir)

    # FALLOFF TRANSFORM
    elif state == "modeler::falloff_xform":
        cur_node.parm("relax_iterations").set(cur_node.evalParm("relax_iterations") + wheel_dir)

    # ARRAY
    elif state == "modeler::array":
        cur_node.parm("count1").set(cur_node.evalParm("count1") + wheel_dir)

    # TOPODRAW
    elif cur_node.type().name() == "modeler::topopatch":
        cur_node.parm("divs").set(cur_node.evalParm("divs") + wheel_dir)

    # MULTILOOP
    elif cur_node.type().name() == "modeler::multiloop":
        cur_node.parm("numloops").set(cur_node.evalParm("numloops") + wheel_dir)

    # SCALE PARM FOR OTHER NODE TYPES
    elif cur_node.type().category() == geo_utils._sop_category:
        parm = cur_node.parm("scale")
        if parm is not None:
            _wheel_change_scale(cur_node, wheel_dir)

    return True


#------------------------------------------------------------------------------


def NodeState(mode):
    with hou.RedrawBlock() as rb:
        try:
            mode.scene_viewer.currentNode().setCurrent(True, True)
            mode.scene_viewer.enterCurrentNodeState()
        except hou.OperationFailed:
            pass
    return True

ADD_TOOL(NodeState, "State")


def SetHandlePivot(mode):
    mode.start_volatile_hotkey_symbol("h.pane.gview.handle.volatile_handle_geometry_detachment", handle_mode=True)
    return True

ADD_TOOL(SetHandlePivot, "State")


def DetachHandle(mode):
    ui.run_internal_command("h.pane.gview.handle.xform.handle_geometry_detachment")
    return True

ADD_TOOL(DetachHandle, "State")


def OrientHandle(mode):
    ui.run_internal_command("h.pane.gview.handle.xform.click_orient")
    return True

ADD_TOOL(OrientHandle, "State")


def CycleHandleAlignment(mode):
    ui.run_internal_command("h.pane.gview.handle.xform.cycle_alignment")
    return True

ADD_TOOL(CycleHandleAlignment, "State")


def SelectReplace(mode, mods=ui.qt.NoModifier, pick_visible=True):
    if mode.state() not in ("select", "scriptselect"):
        return SelectState(mode)

    mode.scene_viewer.setPickingVisibleGeometry(pick_visible)
    return LeftButtonDrag(mode, mods)

ADD_TOOL(SelectReplace, "State")


def SelectAdd(mode):
    return SelectReplace(mode, mods=ui.qt.ShiftModifier)

ADD_TOOL(SelectAdd, "State")


def SelectRemove(mode):
    return SelectReplace(mode, mods=ui.qt.ControlModifier)

ADD_TOOL(SelectRemove, "State")


def SelectThroughReplace(mode):
    return SelectReplace(mode, pick_visible=False)

ADD_TOOL(SelectThroughReplace, "State")


def SelectThroughAdd(mode):
    return SelectReplace(mode, mods=ui.qt.ShiftModifier, pick_visible=False)

ADD_TOOL(SelectThroughAdd, "State")


def SelectThroughRemove(mode):
    return SelectReplace(mode, mods=ui.qt.ControlModifier, pick_visible=False)

ADD_TOOL(SelectThroughRemove, "State")


_drag_mods = None
_drag_release_callback = None

def LeftButtonDrag(mode, mods=ui.qt.NoModifier, release_callback=None):
    global _drag_mods, _drag_release_callback

    mode.mouse_widget.removeEventFilter(mode)
    ui.qtest.mousePress(mode.mouse_widget, ui.qt.LeftButton, mods, mode.press_pos)
    mode.mouse_widget.installEventFilter(mode)
    mode.mouse_release_callback = _LeftButtonDrag
    _drag_mods = mods
    _drag_release_callback = release_callback
    return True

def _LeftButtonDrag(mode):
    global _drag_mods, _drag_release_callback
    
    mode.mouse_widget.removeEventFilter(mode)
    ui.qtest.mouseRelease(mode.mouse_widget, ui.qt.LeftButton, _drag_mods, mode.release_pos)
    mode.mouse_widget.installEventFilter(mode)

    if _drag_release_callback is not None:
        _drag_release_callback()
        _drag_release_callback = None

    return True

ADD_TOOL(LeftButtonDrag, "State")


def RightButtonDrag(mode, mods=ui.qt.NoModifier, release_callback=None):
    global _drag_mods, _drag_release_callback

    mode.mouse_widget.removeEventFilter(mode)
    ui.qtest.mousePress(mode.mouse_widget, ui.qt.RightButton, mods, mode.press_pos)
    mode.mouse_widget.installEventFilter(mode)
    mode.mouse_release_callback = _RightButtonDrag
    _drag_mods = mods
    _drag_release_callback = release_callback
    return True

def _RightButtonDrag(mode):
    global _drag_mods, _drag_release_callback
    
    mode.mouse_widget.removeEventFilter(mode)
    ui.qtest.mouseRelease(mode.mouse_widget, ui.qt.RightButton, _drag_mods, mode.release_pos)
    mode.mouse_widget.installEventFilter(mode)

    if _drag_release_callback is not None:
        _drag_release_callback()
        _drag_release_callback = None

    return True

ADD_TOOL(RightButtonDrag, "State")


def MiddleButtonDrag(mode, mods=ui.qt.NoModifier, release_callback=None):
    global _drag_mods, _drag_release_callback

    mode.mouse_widget.removeEventFilter(mode)
    ui.qtest.mousePress(mode.mouse_widget, ui.qt.MiddleButton, mods, mode.press_pos)
    mode.mouse_widget.installEventFilter(mode)
    mode.mouse_release_callback = _MiddleButtonDrag
    _drag_mods = mods
    _drag_release_callback = release_callback
    return True

def _MiddleButtonDrag(mode):
    global _drag_mods, _drag_release_callback
    
    mode.mouse_widget.removeEventFilter(mode)
    ui.qtest.mouseRelease(mode.mouse_widget, ui.qt.MiddleButton, _drag_mods, mode.release_pos)
    mode.mouse_widget.installEventFilter(mode)

    if _drag_release_callback is not None:
        _drag_release_callback()
        _drag_release_callback = None

    return True

ADD_TOOL(MiddleButtonDrag, "State")


def WheelUp(mode):
    return _wheel(mode, 1)

ADD_TOOL(WheelUp, "State")


def WheelDown(mode):
    return _wheel(mode, -1)

ADD_TOOL(WheelDown, "State")


###############################################################################
# SELECT


def _set_selection_mode(scene_viewer, sel_type):
    with hou.RedrawBlock() as rb:
        scene_viewer.setGroupPicking(False)
        
        if scene_viewer.currentState() == "scriptselect":
            if sel_type == hou.geometryType.Points:
                ui.run_internal_command("h.pane.gview.model.seltypepoints")
            elif sel_type == hou.geometryType.Primitives:
                ui.run_internal_command("h.pane.gview.model.seltypeprims")
            elif sel_type == hou.geometryType.Edges:
                ui.run_internal_command("h.pane.gview.model.seltypeedges")
        else:
            cur_node = scene_viewer.currentNode()
            cat = cur_node.type().category()
            
            if cat == geo_utils._sop_category:
                cur_node.parent().displayNode().setCurrent(True, True)
            
            elif cat == geo_utils._obj_category:
                display = cur_node.displayNode()
                if display is None:
                    scene_viewer.setPwd(cur_node)
                    scene_viewer.setCurrentState("select")
                    scene_viewer.setPickGeometryType(sel_type)
                    return True
                
                display.setCurrent(True, True)
                hou.ui.waitUntil(lambda: True)
            else:
                return True

            scene_viewer.setCurrentState("select")
            scene_viewer.setPickGeometryType(sel_type)

            # CLEAR SELECTION
            gs = scene_viewer.currentGeometrySelection()
            sels = gs.selections()
            if len(sels) == 1:
                sel = hou.Selection(sel_type)
                scene_viewer.setCurrentGeometrySelection(sel_type, (gs.nodes()[0],), (sel,))

    return True

def _convert(mode, sel_typ):
    if mode.scene_viewer.selectionMode() == hou.selectionMode.Geometry:
        if mode.state() == "select":
            if sel_typ == hou.geometryType.Points:
                ui.run_internal_command("h.pane.gview.model.sel.convertpoint")
            elif sel_typ == hou.geometryType.Edges:
                ui.run_internal_command("h.pane.gview.model.sel.convertedge")
            elif sel_typ == hou.geometryType.Primitives:
                ui.run_internal_command("h.pane.gview.model.sel.convertprimitive")
            else:
                ui.run_internal_command("h.pane.gview.model.selectboundary")  

            mode.scene_viewer.setGroupPicking(False)
            
        else:
            sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
            if sop is not None:
                mode.scene_viewer.setCurrentState("select")
                
                if sel.selectionType() != sel_typ:
                    sel = sel.freeze()
                    geo = sop.geometry()
                    sel.convert(geo, sel_typ)
                
                mode.scene_viewer.setPickGeometryType(sel_typ)
                mode.scene_viewer.setCurrentGeometrySelection(sel_typ, (sop,), (sel,))
                mode.scene_viewer.setGroupPicking(False)

    return True

def _convert_edges_to_loops(scene_viewer, r1, r2):
    sop, sel, pwd = geo_utils.sop_selection(scene_viewer)
    if sop is not None and sel.selectionType() == hou.geometryType.Edges:
        geo = sop.geometry()
        edges = sel.edges(geo)

        if len(edges) > 1:
            sel = hou.Selection(geo.edgeLoop(edges, hou.componentLoopType.Extended, True, r1, r2))
        else:
            sel = hou.Selection(geo.edgeLoop((edges[0], edges[0]), hou.componentLoopType.Extended, True, r1, r2))

        scene_viewer.setCurrentState("select")
        scene_viewer.setCurrentGeometrySelection(hou.geometryType.Edges, (sop,), (sel,))

def _select_by_attrib_name(scene_viewer, mask):
    if scene_viewer.isGroupPicking() and scene_viewer.groupListMask() == mask:
        scene_viewer.setGroupPicking(False)
    else:
        scene_viewer.setGroupListMask(mask)
        scene_viewer.setGroupPicking(True)
        scene_viewer.setGroupListColoringGeometry(False)
        scene_viewer.setGroupListType(hou.groupListType.Primitives)
        scene_viewer.setSelectionMode(hou.selectionMode.Geometry)
        scene_viewer.setPickGeometryType(hou.geometryType.Primitives)
        scene_viewer.setCurrentState("select")

    return True


#------------------------------------------------------------------------------


def SelectState(mode):
    if mode.scene_viewer.isGroupPicking():
        mode.scene_viewer.setGroupPicking(False)
    else:
        cur_node = mode.scene_viewer.currentNode()
        if cur_node.type().category() == geo_utils._sop_category:
            if not cur_node.isDisplayFlagSet():
                cur_node.parent().displayNode().setCurrent(True, True)
                hou.ui.waitUntil(lambda: True)

        state = mode.state()
        
        # FINISH EDGELOOP
        if state == "edgeloop" and not mode.scene_viewer.currentNode().evalParm("splitloc"):
            mode.scene_viewer.setCurrentState("select")
            mode.scene_viewer.currentNode().destroy()

        # SPLIT
        elif state == "polysplit::2.0" and mode.scene_viewer.currentNode().evalParm("pathtype") == 0 and not mode.scene_viewer.currentNode().evalParm("splitloc"):
            mode.mouse_widget.removeEventFilter(mode)
            mode.keyboard_widget.removeEventFilter(mode)
            ui.qtest.keyClick(mode.keyboard_widget, ui.qt.Key_Return, ui.qt.NoModifier)
            mode.mouse_widget.installEventFilter(mode)
            mode.keyboard_widget.installEventFilter(mode)
            hou.ui.waitUntil(lambda: True)
            sop = mode.scene_viewer.currentNode()
            if not sop.evalParm("splitloc"):
                mode.scene_viewer.setCurrentState("select")
                sop.destroy()

        # OBJ CLEAR SELECTION
        if mode.scene_viewer.selectionMode() == hou.selectionMode.Object:
            if state == "select":
                hou.clearAllSelected()
            else:
                mode.scene_viewer.setCurrentState("select")
        
        # OTHER CASES
        else:
            # SOP SELECT STATE
            if state in ("select", "scriptselect"):
                geo_utils.clear_sop_selection(mode.scene_viewer)

            # GET SELECTION AND SET IT TO SELECTION STATE 
            else:
                sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
                if sop is not None:
                    items = sel.selectionString(sop.geometry())
                    mode.scene_viewer.setCurrentState("select")
                    typ = sel.selectionType()
                    mode.scene_viewer.setPickGeometryType(typ)
                    if items not in  ("*", "", "!_3d_hidden_primitives"):
                        mode.scene_viewer.setCurrentGeometrySelection(typ, (mode.scene_viewer.currentNode(),), (sel,))

    return True

ADD_TOOL(SelectState, "Select")


def BoxSelectionStyle(mode):
    mode.scene_viewer.setPickStyle(hou.pickStyle.Box)
    return True

ADD_TOOL(BoxSelectionStyle, "Select")


def LassoSelectionStyle(mode):
    mode.scene_viewer.setPickStyle(hou.pickStyle.Lasso)
    return True

ADD_TOOL(LassoSelectionStyle, "Select")


def BrushSelectionStyle(mode):
    mode.scene_viewer.setPickStyle(hou.pickStyle.Brush)
    return True

ADD_TOOL(BrushSelectionStyle, "Select")


def LaserSelectionStyle(mode):
    mode.scene_viewer.setPickStyle(hou.pickStyle.Laser)
    return True

ADD_TOOL(LaserSelectionStyle, "Select")


def SelectVisibleOnly(mode):
    mode.scene_viewer.setPickingVisibleGeometry( not mode.scene_viewer.isPickingVisibleGeometry() )

ADD_TOOL(SelectVisibleOnly, "Select")


def SelectObjects(mode):
    if mode.scene_viewer.selectionMode() == hou.selectionMode.Geometry:
        if mode.scene_viewer.currentNode() == mode.scene_viewer.pwd():
            mode.scene_viewer.setPwd(hou.node("/obj"))

        mode.scene_viewer.setSelectionMode(hou.selectionMode.Object)
        mode.scene_viewer.setCurrentState("select")
    else:
        if mode.state() == "select":
            hou.clearAllSelected()
        else:
            mode.scene_viewer.setCurrentState("select")

    return True

ADD_TOOL(SelectObjects, "Select")


def SelectPoints(mode):
    if mode.scene_viewer.curViewport().type() == hou.geometryViewportType.UV:
        return _set_selection_mode(mode.scene_viewer, hou.geometryType.Vertices)
    else:
        return _set_selection_mode(mode.scene_viewer, hou.geometryType.Points)

ADD_TOOL(SelectPoints, "Select")


def SelectEdges(mode):
    return _set_selection_mode(mode.scene_viewer, hou.geometryType.Edges)

ADD_TOOL(SelectEdges, "Select")


def SelectFaces(mode):
    return _set_selection_mode(mode.scene_viewer, hou.geometryType.Primitives)

ADD_TOOL(SelectFaces, "Select")


def ConvertToPoints(mode):
    return _convert(mode, hou.geometryType.Points)

ADD_TOOL(ConvertToPoints, "Select")


def ConvertToEdges(mode):
    return _convert(mode, hou.geometryType.Edges)

ADD_TOOL(ConvertToEdges, "Select")


def ConvertToFaces(mode):
    return _convert(mode, hou.geometryType.Primitives)

ADD_TOOL(ConvertToFaces, "Select")


def ConvertToShells(mode):
    if mode.scene_viewer.selectionMode() != hou.selectionMode.Geometry:
        return

    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        geo = sop.geometry()
        typ = sel.selectionType()

        with hou.RedrawBlock() as rb:
            if typ != hou.geometryType.Primitives:
                sel = sel.freeze()
                sel.convert(geo, hou.geometryType.Primitives)
                mode.scene_viewer.setPickGeometryType(hou.geometryType.Primitives)
                hou.ui.waitUntil(lambda: True)

            faces = sel.selectionString(geo, force_numeric=True)
            tmp_sop = sop.createOutputNode("groupexpand")
            tmp_sop.setParms({ "group": faces, "outputgroup": "", "floodfill": True })
            mode.scene_viewer.setCurrentState("select")
            mode.scene_viewer.setCurrentGeometrySelection( hou.geometryType.Primitives, (sop,), (tmp_sop.geometry().selection(),) )
            tmp_sop.destroy()

    return True

ADD_TOOL(ConvertToShells, "Select")


def ConvertEdgesToLoops(mode):
    return _convert_edges_to_loops(mode.scene_viewer, False, False)

ADD_TOOL(ConvertEdgesToLoops, "Select")


def ConvertEdgesToRings(mode):
    return _convert_edges_to_loops(mode.scene_viewer, True, True)

ADD_TOOL(ConvertEdgesToRings, "Select")


def ConvertToBoundary(mode):
    return _convert(mode, None)

ADD_TOOL(ConvertToBoundary, "Select")


def GrowSelection(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        typ = sel.selectionType()
        if mode.state() != "select":
            mode.scene_viewer.setPickGeometryType(typ)
            hou.ui.waitUntil(lambda: True)
            mode.scene_viewer.setCurrentState("select")
        ui.run_internal_command("h.pane.gview.model.growselection")
    return True

ADD_TOOL(GrowSelection, "Select")


def ShrinkSelection(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        typ = sel.selectionType()
        if mode.state() != "select":
            mode.scene_viewer.setPickGeometryType(typ)
            hou.ui.waitUntil(lambda: True)
            mode.scene_viewer.setCurrentState("select")
        ui.run_internal_command("h.pane.gview.model.shrinkselection")
    return True

ADD_TOOL(ShrinkSelection, "Select")


def InvertSelection(mode):
    pwd = mode.scene_viewer.pwd()
    if pwd.childTypeCategory() == geo_utils._obj_category:
        mode.scene_viewer.setCurrentState("select")
        ui.run_internal_command("h.pane.gview.world.invertselection")
    else:
        sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
        if sop is not None:
            mode.scene_viewer.setCurrentState("select")
            typ = sel.selectionType()
            items = sel.selectionString(sop.geometry(), force_numeric=True)
            mode.scene_viewer.setPickGeometryType(typ)
            if items != "!_3d_hidden_primitives":
                sel = sel.freeze()
                sel.invert(sop.geometry())
                mode.scene_viewer.setCurrentGeometrySelection(typ, (sop,), (sel,))
    return True

ADD_TOOL(InvertSelection, "Select")


def SelectOpenFaces(mode):
    sop = geo_utils.get_sop(mode.scene_viewer)
    if sop is not None:
        with hou.undos.group("Modeler: Select Open Faces"):
            g = sop.createOutputNode("groupcreate")
            g.parm("basegroup").set("@intrinsic:closed==0")
            sel = g.geometry().selection()
            faces = sel.selectionString(sop.geometry(), force_numeric=True)
            with hou.RedrawBlock() as rb:
                mode.scene_viewer.setCurrentState("select")
                mode.scene_viewer.setPickGeometryType(hou.geometryType.Primitives)
                mode.scene_viewer.setCurrentGeometrySelection(hou.geometryType.Primitives, (sop,), (sel,))
                g.destroy()
    
    return True

ADD_TOOL(SelectOpenFaces, "Select")


def SelectByNormals(mode):
    mode.scene_viewer.setGroupPicking(False)
    mode.scene_viewer.setCurrentState("select")
    ui.run_internal_command("h.pane.gview.model.selectbynormal")
    return True

ADD_TOOL(SelectByNormals, "Select")


def SelectByShells(mode):
    return _select_by_attrib_name(mode.scene_viewer, mask='+3d')

ADD_TOOL(SelectByShells, "Select")


def SelectByMaterials(mode):
    return _select_by_attrib_name(mode.scene_viewer, "@shop_materialpath")

ADD_TOOL(SelectByMaterials, "Select")


def SelectByNameAttribute(mode):
    return _select_by_attrib_name(mode.scene_viewer, "@name")

ADD_TOOL(SelectByNameAttribute, "Select")


def SelectByFaceGroups(mode):
    return _select_by_attrib_name(mode.scene_viewer, mask='*')

ADD_TOOL(SelectByFaceGroups, 'Select')


def LoopSelectionReplace(mode):
    mode.loop = True
    return True

ADD_TOOL(LoopSelectionReplace, "Select")


def LoopSelectionAdd(mode):
    return LoopSelectionReplace(mode)

ADD_TOOL(LoopSelectionAdd, "Select")


def LoopSelectionRemove(mode):
    return LoopSelectionReplace(mode)

ADD_TOOL(LoopSelectionRemove, "Select")


def LoopSelectionToggle(mode):
    return LoopSelectionReplace(mode)

ADD_TOOL(LoopSelectionToggle, "Select")


###############################################################################
# DEFORM


def _xform(mode, op=0):
    state = mode.state()

    with hou.RedrawBlock() as rb:
        with hou.undos.group("Modeler: Transform Operation"):
            node = mode.scene_viewer.currentNode()
            node_type_name = node.type().name()

            # UV EDIT
            if mode.scene_viewer.curViewport().type() == hou.geometryViewportType.UV:
                sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer, auto_select_all=True)
                if sop is not None:
                    if op == 0:
                        ui.run_internal_command("h.pane.gview.state.new_move")
                    elif op == 1:
                        ui.run_internal_command("h.pane.gview.state.new_rotate")
                    else:
                        ui.run_internal_command("h.pane.gview.state.new_scale")
                return True

            elif state == "edit":
                if node.evalParm("xformspace"):
                    node.parm("apply").pressButton()
                    mode.scene_viewer.setCurrentState("select")
                    node.parm("xformspace").set(0)

                if op == 0:
                    ui.run_internal_command("h.pane.gview.state.new_move")
                elif op == 1:
                    ui.run_internal_command("h.pane.gview.state.new_rotate")
                else:
                    ui.run_internal_command("h.pane.gview.state.new_scale")

            elif state in ( "tube", "box", "sphere", "polyextrude::2.0", "copyxform", "xform",
                            "modeler::array", "modeler::falloff_xform", "modeler::qprimitive", "modeler::boolean"):
            
                if op == 0:
                    ui.run_internal_command("h.pane.gview.state.new_move")
                elif op == 1:
                    ui.run_internal_command("h.pane.gview.state.new_rotate")
                else:
                    ui.run_internal_command("h.pane.gview.state.new_scale")

                mode.scene_viewer.curViewport().settings().enableGuide(hou.viewportGuide.NodeHandles, True)

            # STANDARD TRANSFORM
            else:
                # OBJ
                if mode.scene_viewer.pwd().childTypeCategory() == geo_utils._obj_category and hou.selectedNodes():
                    if op == 0:
                        ui.run_internal_command("h.pane.gview.state.new_move")
                    elif op == 1:
                        ui.run_internal_command("h.pane.gview.state.new_rotate")
                    else:
                        ui.run_internal_command("h.pane.gview.state.new_scale")
                
                # SOP
                else:
                    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer, auto_select_all=True)
                    if sop is not None:
                        # SELECT
                        if state != "select":
                            mode.scene_viewer.setCurrentState("select")
                            
                        if op == 0:
                            mode.scene_viewer.enterTranslateToolState()
                        elif op == 1:
                            mode.scene_viewer.enterRotateToolState()
                        else:
                            mode.scene_viewer.enterScaleToolState()

                        hou.ui.waitUntil(lambda: True)
                        sop = mode.scene_viewer.currentNode()
                        geo_utils.setup_edit_sop_for_symmetry(sop)
                        sop.parm("xformspace").set(0)

    return True

#------------------------------------------------------------------------------

def Translate(mode):
    return _xform(mode, 0)

ADD_TOOL(Translate, "Deform")


def Rotate(mode):
    return _xform(mode, 1)

ADD_TOOL(Rotate, "Deform")


def Scale(mode):
    return _xform(mode, 2)

ADD_TOOL(Scale, "Deform")


def LocalTranslate(mode, op=0):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer, auto_select_all=True)
    if sop is not None:
        geo = sop.geometry()
        
        sel_type = sel.selectionType()
        if sel_type == hou.geometryType.Primitives:
            grouptype = 4
        elif sel_type == hou.geometryType.Edges:
            grouptype = 2
        else:
            grouptype = 3

        items = sel.selectionString(geo, force_numeric=True) or "*"

        with hou.undos.group("Modeler: Local TRS Operation"):
            with hou.RedrawBlock() as rb:
                sop = geo_utils.get_edit_sop(mode.scene_viewer, sop)
                sop.setParms({"group": items, "grouptype": grouptype, "xformspace": 2, "localframe": 0})
                geo_utils.setup_edit_sop_for_symmetry(sop)
                
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setHighlightFlag(True)
                sop.setCurrent(True, True)

                mode.scene_viewer.enterCurrentNodeState()

                if op == 0:
                    ui.run_internal_command("h.pane.gview.state.new_move")
                elif op == 1:
                    ui.run_internal_command("h.pane.gview.state.new_rotate")
                else:
                    ui.run_internal_command("h.pane.gview.state.new_scale")

    return True

ADD_TOOL(LocalTranslate, "Deform")


def LocalRotate(mode):
    return LocalTranslate(mode, 1)

ADD_TOOL(LocalRotate, "Deform")


def LocalScale(mode):
    return LocalTranslate(mode, 2)

ADD_TOOL(LocalScale, "Deform")


def MakeCircle(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer, auto_select_all=True)
    if sop is not None:
        with hou.RedrawBlock() as rb:
            mode.scene_viewer.enterScaleToolState()
            ui.run_internal_command("h.pane.gview.state.sop.edit.circle")
    return True

ADD_TOOL(MakeCircle, "Deform")


def Straighten(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer, auto_select_all=True)
    if sop is not None and sel.selectionType() != hou.geometryType.Primitives:
        with hou.RedrawBlock() as rb:
            mode.scene_viewer.enterTranslateToolState()
            ui.run_internal_command("h.pane.gview.state.sop.edit.straighten")
            mode.scene_viewer.setCurrentState("select")
    return True

ADD_TOOL(Straighten, "Deform")


def EvenlySpace(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer, auto_select_all=True)
    if sop is not None:
        with hou.RedrawBlock() as rb:
            mode.scene_viewer.enterTranslateToolState()
            ui.run_internal_command("h.pane.gview.state.sop.edit.spacing")
            mode.scene_viewer.setCurrentState("select")
    return True

ADD_TOOL(EvenlySpace, "Deform")


def SetFlow(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None and sel.selectionType() == hou.geometryType.Edges:
        with hou.undos.group("Modeler: Set Flow"):
            geo = sop.geometry()        
            edges = sel.selectionString(sop.geometry(), force_numeric=True)
            sop = sop.createOutputNode("set_flow")
            sop.parm("group").set(edges)
        
            with hou.RedrawBlock() as rb:
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setCurrent(True, True)
        
        mode.scene_viewer.enterCurrentNodeState()
    
    return True

ADD_TOOL(SetFlow, "Deform")


def UnRotate(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        with hou.undos.group("Modeler: UnRotate"):
            gc = sop.createOutputNode("groupcreate")
            geo = sop.geometry()
            
            if sel.selectionType() != hou.geometryType.Primitives:
                sel = sel.freeze()
                sel.convert(geo, hou.geometryType.Primitives)
            
            faces = sel.selectionString(geo, force_numeric=True)

            gc.setParms({ "groupname":"__selection__", "basegroup": faces })
            aw = gc.createOutputNode("attribwrangle")
            aw.setParms({ "group": "__selection__", "grouptype": 4, "class": 1, "vex_inplace": True, "vex_selectiongroup": "__selection__", "snippet": """matrix m = invert(detail(1, "xform")) * invert(optransform(".."));
    foreach(int pt; primpoints(0, @primnum))
    setpointattrib(0, "P", pt, vector(point(0, "P", pt) * m));""" })
            b = gc.createOutputNode("bound")
            b.setParms({ "group": "__selection__", "grouptype": 4, "orientedbbox": True, "addxformattrib": True })
            aw.setInput(1, b)
            
            with hou.RedrawBlock() as rb:
                aw.setDisplayFlag(True)
                aw.setRenderFlag(True)
                aw.setHighlightFlag(True)
                aw.setCurrent(True, True)
            
            mode.scene_viewer.setCurrentState("select") 
            mode.scene_viewer.setPickGeometryType(hou.geometryType.Primitives)

            b.moveToGoodPosition()

ADD_TOOL(UnRotate, "Deform")


def AlignComponents(mode):
    mode.scene_viewer.runShelfTool("tool_align")

ADD_TOOL(AlignComponents, "Deform")


###############################################################################
# DEFORM STATES


_grab_objects = None
_grab_objects_translatemethod = None
_grab_start_time = None
_grab_state_name = None
_grab_mode = None
_grab_mods = None

def _grab(mode, mods, state_name):
    global _grab_objects, _grab_objects_translatemethod, _grab_start_time, _grab_state_name, _grab_mode, _grab_mods

    state = mode.state()
    
    # FINISH SCRIPTSELECT
    if state == "scriptselect":
        ui.run_internal_command("h.pane.gview.accept")

    # SOP
    elif mode.scene_viewer.pwd().childTypeCategory() == geo_utils._sop_category:
        sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
        if sop is not None:
            # UV GRAB
            if mode.scene_viewer.curViewport().type() == hou.geometryViewportType.UV:
                with hou.undos.group("Modeler: Grab UVs"):
                    cur_node = mode.scene_viewer.currentNode()
                    if cur_node.type().name() == "uvedit":
                        cur_node.parm("apply").pressButton()
                        hou.ui.waitUntil(lambda: True)
                    else:
                        cur_node = cur_node.createOutputNode("uvedit")
                        cur_node.setDisplayFlag(True)
                        cur_node.setRenderFlag(True)
                        cur_node.setCurrent(True, True)

                    if mods == ui.qt.ShiftModifier:
                        cur_node.parm("ty").disable(True)

                    elif mods == ui.qt.ControlModifier:
                        cur_node.parm("tx").disable(True)

                _grab_mode = mode
                _grab_objects_translatemethod = hou.getPreference("handles.indirectdragtranslatemethod.val")

                hou.setPreference("handles.indirectdragtranslatemethod.val", "2")
                mode.scene_viewer.curViewport().settings().enableGuide(hou.viewportGuide.NodeHandles, False)
                mode.scene_viewer.enterTranslateToolState()

                return MiddleButtonDrag(mode, release_callback=_finish_grab_objects_or_uvs_callback)

            # CONTINUE GRABBING GEOEMTRY
            geo = sop.geometry()

            sel_type = sel.selectionType()
            items = sel.selectionString(geo, force_numeric=True, asterisk_to_select_all=True)

            if sel_type == hou.geometryType.Points:
                items_center = geo.pointBoundingBox(items).center()
                grouptype = 3
            
            elif sel_type == hou.geometryType.Primitives:
                items_center = geo.primBoundingBox(items).center()
                grouptype = 4
            
            elif sel_type == hou.geometryType.Edges:
                sel = sel.freeze()
                sel.convert(geo, hou.geometryType.Points)
                items_center = geo.pointBoundingBox(sel.selectionString(geo, force_numeric=True)).center()
                grouptype = 2
            
            else:
                return True

            with hou.undos.group("Modeler: Grab Geometry"):
                with hou.RedrawBlock() as rb:
                    node = geo_utils.get_edit_sop(mode.scene_viewer, sop)

                    # GRAB
                    if state_name == "modeler::grab":
                        node.setParms({ "group": items, "grouptype": grouptype, "xformspace": 0,
                                                 "px": items_center[0], "py": items_center[1], "pz": items_center[2] })
                        state_class = states.Grab
                    
                    # SLIDE
                    elif state_name == "modeler::slide":
                        node.setParms({ "group": items, "grouptype": grouptype, "xformspace": 0, "slideonsurface": True,
                                                 "px": items_center[0], "py": items_center[1], "pz": items_center[2] })
                        state_class = states.Slide
                    
                    # Peak
                    else:
                        node.setParms({ "group": items, "grouptype": grouptype, "xformspace": 0, "switcher1": 1 })
                        state_class = states.Peak

                    node.setRenderFlag(True)
                    node.setHighlightFlag(True)
                    node.setDisplayFlag(True)
                    node.setCurrent(True, True)
            
                    state_class._new_edit = node != sop
                    state_class.node = node
                    
                    _grab_start_time = mode.key_tool_time
                    _grab_mode = mode
                    _grab_mods = mods
                    _grab_state_name = state_name
                    
                    hou.ui.postEventCallback( __grab )

    # OBJ
    else:
        _grab_objects = [ node for node in hou.selectedNodes() if node.parm("tx") is not None ]
        if _grab_objects:
            with hou.undos.group("Modeler: Grab Objects"):
                if mods == ui.qt.ShiftModifier:
                    h = ui.get_hvd(mode.scene_viewer, True)[0]
                    if h[0]:
                        for node in _grab_objects:
                            node.parm("ty").disable(True)
                            node.parm("tz").disable(True)
                    elif h[1]:
                        for node in _grab_objects:
                            node.parm("tx").disable(True)
                            node.parm("tz").disable(True)
                    else:
                        for node in _grab_objects:
                            node.parm("tx").disable(True)
                            node.parm("ty").disable(True)

                elif mods == ui.qt.ControlModifier:
                    v = ui.get_hvd(mode.scene_viewer, True)[1]
                    if v[0]:
                        for node in _grab_objects:
                            node.parm("ty").disable(True)
                            node.parm("tz").disable(True)
                    elif v[1]:
                        for node in _grab_objects:
                            node.parm("tx").disable(True)
                            node.parm("tz").disable(True)
                    else:
                        for node in _grab_objects:
                            node.parm("tx").disable(True)
                            node.parm("ty").disable(True)

                elif mods == ui.qt.ControlModifier | ui.qt.ShiftModifier:
                    d = ui.get_hvd(mode.scene_viewer, True)[2]
                    if d[0]:
                        for node in _grab_objects:
                            node.parm("tx").disable(True)
                    elif d[1]:
                        for node in _grab_objects:
                            node.parm("ty").disable(True)
                    else:
                        for node in _grab_objects:
                            node.parm("tz").disable(True)

                else:
                    mods = ui.qt.NoModifier
                
                with hou.RedrawBlock() as rb:
                    _grab_objects_translatemethod = hou.getPreference("handles.indirectdragtranslatemethod.val")
                    
                    hou.setPreference("handles.indirectdragtranslatemethod.val", "2")
                    mode.scene_viewer.curViewport().settings().enableGuide(hou.viewportGuide.NodeHandles, False)
                    mode.scene_viewer.enterTranslateToolState()

                    MiddleButtonDrag(mode, release_callback=_finish_grab_objects_or_uvs_callback)

    return True


def __grab():
    _grab_mode.scene_viewer.setCurrentState(_grab_state_name)
    LeftButtonDrag(_grab_mode, _grab_mods, release_callback=_finish_grab_callback)

def _finish_grab_callback():
    if ( ui.time.time() - _grab_start_time ) > 0.2:
        _grab_mode.scene_viewer.setCurrentState("select")

def _finish_grab_objects_or_uvs_callback():
    ui.executeDeferred(__finish_grab_objects_or_uvs_callback)

def __finish_grab_objects_or_uvs_callback():
    # UV
    if _grab_mode.state() == "uvedit":
        _grab_mode.scene_viewer.currentNode().parmTuple("t").disable(False)
        _grab_mode.scene_viewer.setCurrentState("select")

    # OBJECTS
    else:
        for node in _grab_objects:
            node.parmTuple("t").disable(False)
        
    _grab_mode.scene_viewer.curViewport().settings().enableGuide(hou.viewportGuide.NodeHandles, True)
    hou.setPreference("handles.indirectdragtranslatemethod.val", _grab_objects_translatemethod)


#------------------------------------------------------------------------------


def Grab(mode):
    return _grab(mode, ui.qt.NoModifier, "modeler::grab")

ADD_TOOL(Grab, "Deform States")


def GrabHorizontal(mode):
    return _grab(mode, ui.qt.ShiftModifier, "modeler::grab")

ADD_TOOL(GrabHorizontal, "Deform States")


def GrabVertical(mode):
    return _grab(mode, ui.qt.ControlModifier, "modeler::grab")

ADD_TOOL(GrabVertical, "Deform States")


def GrabBestPlane(mode):
    return _grab(mode, ui.qt.ControlModifier | ui.qt.ShiftModifier, "modeler::grab")

ADD_TOOL(GrabBestPlane, "Deform States")


def Peak(mode):
    return _grab(mode, ui.qt.NoModifier, "modeler::peak")

ADD_TOOL(Peak, "Deform States")


def Slide(mode):
    return _grab(mode, ui.qt.NoModifier, "modeler::slide")

ADD_TOOL(Slide, "Deform States")


_relax_scene_viewer = None
_relax_prims_sel = None

def _finish_relax_callback():
    _relax_scene_viewer.setCurrentState("select")


def Relax(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)

    if sop is not None:
        # UV VIUEWPORT
        if mode.scene_viewer.curViewport().type() == hou.geometryViewportType.UV:
            if mode.state() != "uvedit":
                mode.scene_viewer.setCurrentState("uvedit")
                hou.ui.waitUntil(lambda: True)
            ui.run_internal_command("h.pane.gview.state.sop.uvedit.smooth")

        # 3D VIUEWPORT
        else:
            global _relax_scene_viewer, _relax_prims_sel
            
            _relax_scene_viewer = mode.scene_viewer

            geo = sop.geometry()
            sel_typ = sel.selectionType()

            if sel_typ == hou.geometryType.Primitives:
                grouptype = 0

            elif sel_typ == hou.geometryType.Points:
                grouptype = 1
            
            elif sel_typ == hou.geometryType.Edges:
                grouptype = 2
            
            else:
                return True
            
            with hou.undos.group("Modeler: Relax"):
                sop = sop.createOutputNode("modeler::relax")
                sop.setParms({ "group": sel.selectionString(geo, force_numeric=True), "grouptype": grouptype, "pinborder": grouptype == 2 })

                with hou.RedrawBlock() as rb:
                    sop.setDisplayFlag(True)
                    sop.setRenderFlag(True)
                    sop.setCurrent(True, True)

            _relax_scene_viewer.enterCurrentNodeState()

            return LeftButtonDrag(mode, release_callback=_finish_relax_callback)
    
    return True

ADD_TOOL(Relax, "Deform States")


Push = states.Push

ADD_TOOL(Push, "Deform States")


_smooth_brush_opacity = 0.1

def _finish_smooth_brush(node, event_type, **kwargs):
    global _smooth_brush_opacity
    node.removeAllEventCallbacks()

    ui.show_current_geo( hou.ui.paneTabOfType(hou.paneTabType.SceneViewer), True )
    geo_utils.global_brush_radius = node.evalParm("sculptrad")
    _smooth_brush_opacity = node.evalParm("opacity")

def SmoothBrush(mode):
    sop = mode.scene_viewer.currentNode()
    if sop.type().category() == geo_utils._sop_category:
        if sop.type().name() == "edit" and sop.cookCount() < 4:
            sop.destroy()
            mode.scene_viewer.setCurrentState("select")
        else:
            with hou.undos.group("Modeler: Push Smooth"):
                ui.show_current_geo(mode.scene_viewer, False)
                sop = geo_utils.get_edit_sop(mode.scene_viewer, sop)
                sop.setParms({ "modeswitcher1": 1, "group": "", "sculptrad": geo_utils.global_brush_radius, "opacity": _smooth_brush_opacity })
                geo_utils.setup_edit_sop_for_symmetry(sop)
                sop.setCurrent(True, True)
                mode.scene_viewer.enterCurrentNodeState()
                ui.run_internal_command("h.pane.gview.state.sop.brush.p_smooth")

                # TOPO
                highres_sop = topo_tools.get_highres_sop()
                if highres_sop is not None:
                    p = sop.createOutputNode("modeler::project")
                    om = geo_utils.inject_ref_objectmerge(highres_sop, sop.parent())
                    p.setInput(1, om)
                    p.setDisplayFlag(True)
                    p.setRenderFlag(True)
                else:
                    sop.setDisplayFlag(True)
                    sop.setRenderFlag(True)

                ui.qtg.QCursor.setPos(ui.qtg.QCursor.pos() + ui.qtc.QPoint(0, 1))

                hou.ui.waitUntil(lambda: True)
                sop.addEventCallback((hou.nodeEventType.AppearanceChanged,), _finish_smooth_brush)

        return True

ADD_TOOL(SmoothBrush, "Deform States")



###############################################################################
# EDIT


def _walk_history(scene_viewer, direction):
    class WalkHistoryButton(ui.qtw.QPushButton):
        def __init__(self, node, parent):
            icon = hou.ui.createQtIcon(node.type().icon())
            super(WalkHistoryButton, self).__init__(icon, node.name(), parent)
            self.setMouseTracking(True)
            self.setFlat(True)
            self._node = node

        def focusInEvent(self, event):
            super(WalkHistoryButton, self).focusInEvent(event)
            margin = hou.ui.scaledSize(12)
            pos_on_button = self.mapToGlobal(ui.qtc.QPoint(margin, margin))
            ui.qtg.QCursor.setPos(pos_on_button)

        def mousePressEvent(self, event):
            super(WalkHistoryButton, self).mousePressEvent(event)
            self.parent().close()
 
        def mouseMoveEvent(self, event):
            super(WalkHistoryButton, self).mouseMoveEvent(event)
            
            try:
                if not self._node.isDisplayFlagSet():
                    self._node.setCurrent(True, True)
                    self._node.setDisplayFlag(True)
                    self._node.setRenderFlag(True)
            
            except hou.ObjectWasDeleted:
                self.parent().close()

        def keyPressEvent(self, event):
            super(WalkHistoryButton, self).keyPressEvent(event)
            if event.key() in (ui.qt.Key_Escape, ui.qt.Key_Return, ui.qt.Key_Space):
                self.parent().close()

    cur_node = scene_viewer.currentNode()

    if direction > 0:
        nodes = cur_node.inputs()
    else:
        nodes = cur_node.outputs()

    nodes_count = len(nodes)

    if nodes_count == 1 or nodes_count > 4:
        node = nodes[0]
        with hou.undos.group("Modeler: Walk History"):
            node.setCurrent(True, True)
            node.setDisplayFlag(True)
            node.setRenderFlag(True)

    elif nodes_count > 1:
        node = nodes[0]
        with hou.undos.group("Modeler: Walk History"):
            node.setCurrent(True, True)
            node.setDisplayFlag(True)
            node.setRenderFlag(True)

        widget = ui.qtw.QDialog( hou.qt.mainWindow() )
        widget.setAttribute(ui.qt.WA_DeleteOnClose)
        widget.setWindowTitle("Select one of the ancestor nodes.")
        layout = ui.qtw.QHBoxLayout(widget)

        for node in nodes:
            layout.addWidget(WalkHistoryButton(node, widget))
        
        cursor_pos = ui.qtg.QCursor().pos()
        widget.adjustSize()
        widget.move( cursor_pos.x()-widget.width() / 2, cursor_pos.y()-widget.height() / 2 + hou.ui._getTabMenuIconSize()[0] * 2 )
        widget.show()

    network_pane = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.NetworkEditor)
    if network_pane is not None:
        network_pane.homeToSelection()


#------------------------------------------------------------------------------


def Launcher(mode):
    mode.launcher.start()
    return True

ADD_TOOL(Launcher, "Edit")


def Undo(mode):
    if mode.state() != "scriptselect":
        labels = hou.undos.undoLabels()
        if labels and labels[0] == "Grab Drag" and mode.scene_viewer.currentNode().type().name() == "edit" and states.Grab._new_edit:
            edit_name = mode.scene_viewer.currentNode().name()
            while mode.scene_viewer.currentNode().name() == edit_name:
                hou.undos.performUndo()
        else:
            hou.undos.performUndo()

    return True

ADD_TOOL(Undo, "Edit")


def Redo(mode):
    if mode.state() != "scriptselect":
        hou.undos.performRedo()
    return True

ADD_TOOL(Redo, "Edit")


def DeleteNode(mode):
    with hou.undos.group("Modeler: Delete Node"):
        scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        sel_nodes = hou.selectedNodes()
        
        if len(sel_nodes) > 1:
            [ n.destroy() for n in sel_nodes ]
        
        elif len(sel_nodes) == 1 and sel_nodes[0].type().category() == geo_utils._sop_category and not sel_nodes[0].isDisplayFlagSet():
            sel_nodes[0].destroy()
        
        else:
            cont = True
            pwd = scene_viewer.pwd()
            child_cat = pwd.childTypeCategory()
            if child_cat == geo_utils._obj_category:
                nodes = [node for node in (sel_nodes or pwd.children()) if node.type().name() in ("geo", "modeler::freeform")]
                if nodes:
                    pwd.deleteItems(nodes)

                    mode.scene_viewer.setCurrentState("select")

            elif child_cat == geo_utils._sop_category:
                sop = pwd.displayNode()
                if sop is not None:
                    inputs = sop.inputs()
                    
                    if inputs:
                        if sop.type().name() == "modeler::topopatch" and len(inputs) == 2:
                            sop1 = inputs[1]
                        else:
                            sop1 = inputs[0] or inputs[-1]
                        
                        sop1.setDisplayFlag(True)
                        sop1.setRenderFlag(True)
                        sop1.setCurrent(True, True)
                        scene_viewer.enterViewState()
                        hou.ui.waitUntil(lambda: True)
                        scene_viewer.enterCurrentNodeState()
                    
                    elif len(pwd.children()) == 1:
                        result = hou.ui.displayMessage("Latest node. What to delete?", buttons=("Delete Parent", "Delete Node" , "Abort"), close_choice=2, default_choice=0)
                        if result == 0:
                            pwd.destroy()
                            cont = False
                        
                        elif result == 2:
                            cont = False

                    if cont:
                        try:
                            sop.destroy()
                        except hou.ObjectWasDeleted:
                            pass
    
    return True

ADD_TOOL(DeleteNode, "Edit")


def RepeatNodeParms(mode):
    node = mode.scene_viewer.currentNode()
    node_type_name = node.type().name()
    exclude_parm_names = ("group", "grouptype", "srcgroup", "dstgroup")
    with hou.undos.group("Modeler: Repeat Node Parms"):
        for a in node.inputAncestors():
            if a.type().name() == node_type_name:
                for p in a.parms():
                    if p.name() not in exclude_parm_names:
                        node.parm(p.name()).set(p.eval())
                break
    
    return True

ADD_TOOL(RepeatNodeParms, "Edit")


def NewScene(mode):
    mode.scene_viewer.setCurrentState("select")
    ui.run_internal_command("h.new")
    return True

ADD_TOOL(NewScene, "Edit")


def OpenScene(mode):
    ui.run_internal_command("h.open")
    return True

ADD_TOOL(OpenScene, "Edit")


def SaveScene(mode):
    ui.run_internal_command("h.save")
    return True

ADD_TOOL(SaveScene, "Edit")


def JumpIn(mode):
    ui.run_internal_command("h.pane.wsheet.jump")
    mode.scene_viewer.setCurrentState("select")
    return True

ADD_TOOL(JumpIn, "Edit")


def JumpOut(mode):
    ui.run_internal_command("h.pane.wsheet.updir")
    mode.scene_viewer.setCurrentState("select")
    return True

ADD_TOOL(JumpOut, "Edit")


def WalkHistoryUp(mode):
    scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    _walk_history(scene_viewer, 1)
    return True

ADD_TOOL(WalkHistoryUp, "Edit")


def WalkHistoryDown(mode):
    scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    _walk_history(scene_viewer, -1)
    return True

ADD_TOOL(WalkHistoryDown, "Edit")


def FreezeObject(mode):
    cur_node = mode.scene_viewer.currentNode()
    if cur_node.type().category() == geo_utils._sop_category:
        ancestor = geo_utils.ancestor_object(cur_node)
        geo_utils.freeze([ancestor])
        ancestor.displayNode().setCurrent(True, True)
    else:
        nodes = [ node for node in hou.selectedNodes() if node.type().name() in ("geo", "subnet") ]
        geo_utils.freeze(nodes)

ADD_TOOL(FreezeObject, "Edit")


def CenterObjectPivot(mode):
    mode.scene_viewer.runShelfTool("object_centerpivot")

ADD_TOOL(CenterObjectPivot, "Edit")


def Quit(mode):
    mode.finish()
    return True

ADD_TOOL(Quit, "Edit")


###############################################################################
# RADIAL MENUS


def AddMenu(mode):
    mode.show_radial_menu("modeler_add")
    return True

ADD_TOOL(AddMenu, "Radial Menus")


def FlattenMenu(mode):
    mode.show_radial_menu("modeler_flatten")
    return True

ADD_TOOL(FlattenMenu, "Radial Menus")


def DeformMenu(mode):
    mode.show_radial_menu("modeler_deform")
    return True

ADD_TOOL(DeformMenu, "Radial Menus")


def TopoMenu(mode):
    mode.show_radial_menu("modeler_topo")
    return True

ADD_TOOL(TopoMenu, "Radial Menus")


def BooleanMenu(mode):
    mode.show_radial_menu("modeler_boolean")
    return True

ADD_TOOL(BooleanMenu, "Radial Menus")


def MaterialsMenu(mode):
    mode.show_radial_menu("modeler_materials")
    return True

ADD_TOOL(MaterialsMenu, "Radial Menus")


def NetworkMenu(mode):
    mode.show_radial_menu("modeler_network")
    return True

ADD_TOOL(NetworkMenu, "Radial Menus")


def KitBashMenu(mode):
    mode.show_radial_menu("modeler_kitbash")
    return True

ADD_TOOL(KitBashMenu, "Radial Menus")


def PatternMenu(mode):
    mode.show_radial_menu("modeler_pattern")
    return True

ADD_TOOL(PatternMenu, "Radial Menus")


def ViewportTypeMenu(mode):
    mode.show_radial_menu("modeler_vp_type")
    return True

ADD_TOOL(ViewportTypeMenu, "Radial Menus")


###############################################################################
# MESH


def _sym_setup_node(scene_viewer, pre_sop, new_sop):
    geo = pre_sop.geometry()

    if geo.findGlobalAttrib("sym_origin") is None:
        h = ui.get_hvd(scene_viewer)[0]
        
        if (h[0] == -1.0):
            new_sop.parm("flip").set(True)
        elif (h[1] == 1.0):
            new_sop.parm("axis").set(1)
        elif (h[1] == -1.0):
            new_sop.parm("axis").set(1)
            new_sop.parm("flip").set(True)
        elif (h[2] == 1.0):
            new_sop.parm("axis").set(2)
        elif (h[2] == -1.0):
            new_sop.parm("axis").set(2)
            new_sop.parm("flip").set(True)

        new_sop.parmTuple("origin").set( pre_sop.geometry().boundingBox().center())

    else:
        sym_origin = geo.attribValue("sym_origin")
        sym_axis = geo.attribValue("sym_axis")
        sym_flip = geo.attribValue("sym_flip")
        new_sop.setParms({"axis": sym_axis, "flip": sym_flip,
                          "originx": sym_origin[0], "originy": sym_origin[1], "originz": sym_origin[2] })

        sym_normals_cuspangle = geo.attribValue("sym_normals_cuspangle")
        if sym_normals_cuspangle > -1.0:
            new_sop.setParms({"normals": True, "normals_cuspangle": sym_normals_cuspangle})


def _sym_get_instance_node(sop):
    pwd_path = sop.creator().path()
    for i in hou.nodeType(geo_utils._obj_category, "instance").instances():
        if i.evalParm("instancepath") == pwd_path:
            return i
    return None


def _sym_update_instance_node(new_sop):
    pwd = new_sop.creator()
    geo = new_sop.geometry()
    instance_node = _sym_get_instance_node(new_sop)

    if instance_node is None:
        new_sop.parm("mirror").set(False)
        pwd_parent = pwd.parent()
        instance_node = pwd_parent.createNode("instance")
        instance_node.parm("instancepath").set(pwd.path())
        instance_node.moveToGoodPosition()
        instance_node.setSelectableInViewport(False)

    sym_origin = geo.attribValue("sym_origin")
    sym_axis = geo.attribValue("sym_axis")
    if sym_axis == 0:
        instance_node.parmTuple("s").set((-1.0, 1.0, 1.0))
    elif sym_axis == 1:
        instance_node.parmTuple("s").set((1.0, -1.0, 1.0))
    else:
        instance_node.parmTuple("s").set((1.0, 1.0, -1.0))

    instance_node.parmTuple("p").set(sym_origin)


#------------------------------------------------------------------------------


_isolated_objects = None

def Isolate(mode):
    with hou.undos.group("Modeler: Isolate"):
        pwd = mode.scene_viewer.pwd()
        if pwd.childTypeCategory() == geo_utils._obj_category:
            global _isolated_objects
    
            # UNISOLATE
            if _isolated_objects:
                for node in _isolated_objects:
                    try:
                        node.setDisplayFlag(True)
                    except:
                        pass
                _isolated_objects = None

            # ISOLATE
            else:
                nodes = []
                for node in [ node for node in pwd.children() if node.type().name() == "geo" ]:
                    if not node.isSelected() and node.isDisplayFlagSet():
                        node.setDisplayFlag(False)
                        nodes.append(node)
                if nodes:
                    _isolated_objects = nodes

        else:
            sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
            if sop is not None:
                geo = sop.geometry()

                # ALL SELECTED
                if geo_utils.is_all_selected(sel, geo):
                    if geo.findPrimGroup("_3d_hidden_primitives") is None:
                        return
                    else:
                        sop = sop.createOutputNode("visibility", "unisolate1")
                        sop.parm("action").set(1)

                # PARTIALLY SELECTED
                else:
                    if sel.selectionType() != hou.geometryType.Primitives:
                        sel = sel.freeze()
                        sel.convert(geo, hou.geometryType.Primitives)

                    faces = sel.selectionString(geo, force_numeric=True)
                    sop = sop.createOutputNode("visibility", "isolate1")
                    sop.setParms({ "group": faces, "applyto": 1 })
                
                with hou.RedrawBlock() as rb:
                    sop.setDisplayFlag(True)
                    sop.setRenderFlag(True)
                    sop.setCurrent(True, True)
                
                mode.scene_viewer.setCurrentState("select")
    
    return True

ADD_TOOL(Isolate, "Mesh")


def Separate(mode):
    with hou.undos.group("Modeler: Separate"):
        sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
        if sop is not None:
            existing_sep = None
            for ancestor in sop.inputAncestors():
                if ancestor.type().name() == "split" and len(ancestor.inputs()) == 1:
                    existing_sep = ancestor
                    break

            items = sel.selectionString(sop.geometry(), force_numeric=True)
            typ = sel.selectionType()

            if existing_sep is not None and not existing_sep.outputConnectors()[1]:
                sop = sop.createOutputNode("boolean::2.0")
                sop.parm("booleanop").set(0)
                sop.setInput(1, existing_sep, 1)
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setCurrent(True, True)
                s = pwd.collapseIntoSubnet((sop,), "unseparate1")
                s.moveToGoodPosition()

            elif items and typ == hou.geometryType.Primitives: 
                new_sep = sop.createOutputNode("split", "separate1")
                new_sep.parm("group").set(items)
                new_sep.setDisplayFlag(True)
                new_sep.setRenderFlag(True)
                new_sep.setCurrent(True, True)
            else:
                return

            ui.home_selected()
    
    return True

ADD_TOOL(Separate, "Mesh")


def Combine(mode):
    pwd = mode.scene_viewer.pwd()
    child_cat = pwd.childTypeCategory()

    if child_cat == geo_utils._obj_category:
        objs = [node for node in hou.selectedNodes() if node.type().name()=="geo"]
        if len(objs) > 1:
            with hou.undos.group("Modeler: Combine"):
                with hou.RedrawBlock() as rb:
                    geo_utils.objecttoolutils.freeze(objs)
                    obj = objs[0]
                    sop = obj.displayNode()
                    
                    # MAIN MATERIAL
                    mat = obj.evalParm("shop_materialpath")
                    if mat:
                        if sop.geometry().findPrimAttrib("shop_materialpath") is not None:
                            sop = sop.createOutputNode("attribwrangle", "global_material1")
                            sop.setParms({ "group": '@shop_materialpath==""', "snippet": 's@shop_materialpath = "%s";' % mat, "class": 1 })
                        else:
                            sop = sop.createOutputNode("material")
                            sop.parm("shop_materialpath1").set(mat)

                        obj.parm("shop_materialpath").set("")

                    mat = obj.evalParm("shop_materialpath")
                    sop.setCurrent(True, True)
                    m = sop.createOutputNode("merge")
                    for i, obj1 in enumerate(objs[1:]):
                        sop = obj1.displayNode()
                        if sop is not None:
                            sop = obj1.displayNode()
                            nodes_to_copy = (sop,) + sop.inputAncestors()
                            copied_nodes = hou.copyNodesTo(nodes_to_copy, obj)
                            new_sop = copied_nodes[0]

                            mat = obj1.evalParm("shop_materialpath")
                            if mat:
                                if new_sop.geometry().findPrimAttrib("shop_materialpath") is not None:
                                    new_sop = new_sop.createOutputNode("attribwrangle", "global_material1")
                                    new_sop.setParms({ "group": '@shop_materialpath==""', "snippet": 's@shop_materialpath = "%s";' % mat, "class": 1 })
                                else:
                                    new_sop = new_sop.createOutputNode("material")
                                    new_sop.parm("shop_materialpath1").set(mat)

                            m.setInput(i + 1, new_sop)
                            obj1.destroy()    
                    
                    m.setSelected(True, True)
                    m.setDisplayFlag(True)
                    m.setRenderFlag(True)
                    obj.layoutChildren()
                    obj.setCurrent(True, True)
            ui.home_selected()
    
    elif child_cat == geo_utils._sop_category:
        sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
        if sop is not None:
            next_pwd, next_sop = geo_utils.get_object(mode.scene_viewer, "Select an object to combine with.")
            if next_pwd is not None and next_pwd != pwd:
                with hou.undos.group("Modeler: Combine"):
                    node = geo_utils.merge_with_object(sop, pwd, next_sop, next_pwd, merge_node_type="merge")
                    mode.scene_viewer.setCurrentState("select")
    
    return True

ADD_TOOL(Combine, "Mesh")


def Extract(mode):
    nodes = [node for node in hou.selectedNodes() if node.type().name()=="geo"]
    if nodes:
        nodes_to_layout = []
        pwd_parent = nodes[0].parent()
    
        result = hou.ui.displayMessage("How to extract the shells?", buttons=("Simple extract", "Extract and group", "Cancel"), default_choice=0, close_choice=2, title="Extract All Polygonal Shells")
        if result == 2:
            return

        parent_with_null = result == 1

        with hou.undos.group("Modeler: Extract"):
            with hou.RedrawBlock() as rb:
                for pwd in nodes:
                    sop = pwd.displayNode()
                    if sop is not None:
                        if parent_with_null:
                            null = pwd_parent.createNode("null")
                        
                        name = pwd.name()
                        xform = pwd.worldTransform()
                        global_center = sop.geometry().boundingBox().center() * xform
                        mat_path = pwd.evalParm("shop_materialpath")
                        con = sop.createOutputNode("connectivity")
                        con.parm("connecttype").set(1)
                        blast = con.createOutputNode("blast")
                        blast.parm("negate").set(True)
                        prefix = "@class=="
                        i = 0
                        while True:
                            blast.parm("group").set(prefix + str(i))
                            geo = hou.Geometry(blast.geometry())
                            geo.transform(xform)
                            prim_count = geo.intrinsicValue("primitivecount")
                            if prim_count == 0:
                                break
                            new_geo = pwd_parent.createNode("geo")
                            if parent_with_null:
                                new_geo.setInput(0, null)
                            
                            center = geo.boundingBox().center()
                            new_geo.setParms({ "shop_materialpath": mat_path, "px": center[0], "py": center[1], "pz": center[2] })
                            stash = new_geo.createNode("stash")
                            stash.parm("stash").set(geo)
                            i += 1
                            nodes_to_layout.append(new_geo)
                        
                        blast.destroy()
                        con.destroy()
                        pwd.destroy()

                        if parent_with_null:
                            null.parm("childcomp").set(True)
                            null.parmTuple("t").set(global_center)
                            null.parm("childcomp").set(False)
                            nodes_to_layout.append(null)
                            null.setName(name)
                    
                # LAYOUT
                mode.scene_viewer.pwd().layoutChildren(nodes_to_layout)
                ui.frame_items(nodes_to_layout)
                mode.scene_viewer.setCurrentState("select")

    else:
        sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
        if sop is not None:
            geo = sop.geometry()
            
            if not geo_utils.is_all_selected(sel, geo) and sel.selectionType() == hou.geometryType.Primitives:
                items = sel.selectionString(geo, force_numeric=True)
                
                with hou.undos.group("Modeler: Extract"):
                    b = sop.createOutputNode("blast")
                    b.parm("group").set(items)
                    b1 = sop.createOutputNode("blast")
                    b1.setParms({ "group": items, "negate": True })
                    geo = hou.Geometry(b1.geometry())
                    geo.transform(pwd.localTransform())
                    s = b1.createOutputNode("stash")
                    s.parm("stash").set(geo)
                    obj = pwd.parent().createNode("geo", "extracted_prims1")
                    hou.moveNodesTo((s,), obj)
                    
                    with hou.RedrawBlock() as rb:
                        b.setDisplayFlag(True)
                        b.setRenderFlag(True)
                        b.setCurrent(True, True)
                    
                    b1.destroy()
                    obj.moveToGoodPosition()
    
    return True

ADD_TOOL(Extract, "Mesh")


_copied_geo = None

def CopyFaces(mode, cut=False):
    global _copied_geo

    with hou.undos.group("Modeler: Clipboard Action"):
        pwd = mode.scene_viewer.pwd()
        child_cat = pwd.childTypeCategory()
        _copied_geo = None
        if child_cat == geo_utils._obj_category:
            objs = [node for node in hou.selectedNodes() if node.type().name()=="geo"]
            if len(objs) == 1:
                sop = objs[0].displayNode()
                if sop is not None:
                    _copied_geo = sop.geometry().freeze()
                    _copied_geo.transform(geo_utils.ancestor_object(objs[0]).worldTransform())
                    if cut:
                        objs[0].destroy()

        else:
            sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
            if sop is not None and sel.selectionType() == hou.geometryType.Primitives:
                geo = sop.geometry().freeze()
                faces = sel.selectionString(geo, force_numeric=True)
                
                bv = hou.sopNodeTypeCategory().nodeVerb("blast")
                bv.setParms({"group": faces, "negate": True})
                
                _copied_geo = hou.Geometry()
                bv.execute(_copied_geo, (geo,))
                _copied_geo.transform(geo_utils.ancestor_object(pwd).worldTransform())

                if cut:
                    sop = sop.createOutputNode("blast", "cut_faces1")
                    sop.parm("group").set(faces)
                    sop.setDisplayFlag(True)
                    sop.setRenderFlag(True)
                    sop.setCurrent(True, True)

        if _copied_geo is None:
            mode.scene_viewer.setPromptMessage("Wrong selection! Select faces or one geometry object and try again.")
        else:
            if cut:
                mode.scene_viewer.setPromptMessage("{} faces was removed to clipboard".format(_copied_geo.intrinsicValue("primitivecount")))
            else:
                mode.scene_viewer.setPromptMessage("{} faces was copied to clipboard".format(_copied_geo.intrinsicValue("primitivecount")))
    
    return True

ADD_TOOL(CopyFaces, "Mesh")


def CutFaces(mode):
    return CopyFaces(mode, cut=True)

ADD_TOOL(CutFaces, "Mesh")


def PasteFaces(mode):
    if _copied_geo is None:
        mode.scene_viewer.setPromptMessage("There are no faces in clipboard!")
    else:
        with hou.undos.group("Paste Faces"):
            pwd = mode.scene_viewer.pwd()
            child_cat = pwd.childTypeCategory()
            if child_cat == geo_utils._sop_category:
                xform = geo_utils.ancestor_object(pwd).worldTransform().inverted()
                geo = hou.Geometry(_copied_geo)
                geo.transform(xform)

                sop = pwd.displayNode()
                if sop is None:
                    stash = pwd.createNode("stash", "pasted_geo1")
                    stash.parm("stash").set(geo)
                    sop_to_display = stash
                    sel = None
                else:
                    merge = sop.createOutputNode("merge")
                    stash = merge.createInputNode(1, "stash", "pasted_geo1")
                    stash.parm("stash").set(geo)
                    sop_to_display = merge
                    geo = merge.geometry()
                    b = geo.intrinsicValue("primitivecount") - 1
                    a = b - _copied_geo.intrinsicValue("primitivecount") + 1
                    sel = hou.Selection(geo, hou.geometryType.Primitives, "{}-{}".format(a, b))

                sop_to_display.setDisplayFlag(True)
                sop_to_display.setRenderFlag(True)
                sop_to_display.setCurrent(True, True)
                
                mode.scene_viewer.setPickGeometryType(hou.geometryType.Primitives)
                mode.scene_viewer.setCurrentState("select")
                if sel is not None:
                    mode.scene_viewer.setCurrentGeometrySelection(hou.geometryType.Primitives, (sop_to_display,), (sel,))

                mode.scene_viewer.setPromptMessage("{} faces was pasted from clipboard".format(_copied_geo.intrinsicValue("primitivecount")))

            elif child_cat == geo_utils._obj_category:
                obj = pwd.createNode("geo", "pasted_geo1")
                obj.moveToGoodPosition()
                stash = obj.createNode("stash", "pasted_geo1")
                stash.parm("stash").set(_copied_geo)
                stash.setDisplayFlag(True)
                stash.setRenderFlag(True)
                obj.setCurrent(True, True)
                
                mode.scene_viewer.setPickGeometryType(hou.geometryType.Primitives)
                mode.scene_viewer.setCurrentState("select")
                mode.scene_viewer.setPromptMessage('{} faces was pasted from clipboard to a new object "{}"'.format(_copied_geo.intrinsicValue("primitivecount"), obj.name()))
    
    return True

ADD_TOOL(PasteFaces, "Mesh")


def Duplicate(mode):
    pwd = mode.scene_viewer.pwd()
    state = mode.state()

    if state == "modeler::boolean":
        cur_node = mode.scene_viewer.currentNode()
        cur_node.parm("repeat").pressButton()

    elif pwd.childTypeCategory() == geo_utils._obj_category:
        nodes = [node for node in (hou.selectedNodes() or pwd.children()) if node.type().name() in ("geo", "modeler::freeform")]
        if nodes:
            with hou.undos.group("Modeler: Duplicate Objects"):
                new_nodes = hou.copyNodesTo(nodes, pwd)
                for node in new_nodes:
                    node.moveToGoodPosition()
            if state != "select":
                mode.scene_viewer.enterTranslateToolState()

    else:
        sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
        if sop is not None:
            geo = sop.geometry()

            items = geo_utils.selected_polygons(sel, geo)
            if items is not None:
                with hou.undos.group("Modeler: Duplicate Faces"):
                    sop = sop.createOutputNode("copyxform")
                    p = geo.primBoundingBox(items).center()
                    sop.setParms({ "sourcegroup": items, "sourcegrouptype": 1, "px": p[0], "py": p[1], "pz": p[2] })
                    
                    with hou.RedrawBlock() as rb:
                        sop.setDisplayFlag(True)
                        sop.setRenderFlag(True)
                        sop.setHighlightFlag(True)
                        sop.setCurrent(True, True)
                    
                mode.scene_viewer.enterCurrentNodeState()
                    
            elif sel.selectionType() == hou.geometryType.Edges:
                with hou.undos.group("Modeler: Duplicate Faces"):
                    d = sop.createOutputNode("dissolve")
                    d.setParms({ "group": sel.selectionString(geo, force_numeric=True), "invertsel": 1, "reminlinepts": False, "bridge": 1, "boundarycurves": True })
                    p = d.createOutputNode("polypath")
                    g = p.createOutputNode("groupcreate")
                    g.parm("groupname").set("__selection__")
                    
                    gd = sop.createOutputNode("groupdelete")
                    gd.parm("group1").set("__selection__")

                    m = g.createOutputNode("merge")
                    m.setNextInput(gd)

                    x = m.createOutputNode("xform", "transform_open_faces1")
                    x.setParms({ "group": "__selection__", "grouptype": 4 })
                    
                    with hou.RedrawBlock() as rb:
                        x.setDisplayFlag(True)
                        x.setRenderFlag(True)
                        x.setHighlightFlag(True)
                        
                        sel = x.geometry().selection()
                        x.parmTuple("p").set(geo_utils.sop_selection_center(x, sel))

                        s = pwd.collapseIntoSubnet((d, p, g, gd, m), "duplicate_edges1")
                        s.moveToGoodPosition()
                        x.moveToGoodPosition()
                        
                        x.setCurrent(True, True)

                mode.scene_viewer.enterCurrentNodeState()

    return True

ADD_TOOL(Duplicate, "Mesh")


def Array(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        with hou.undos.group("Modeler: Array"):
            geo = sop.geometry()
            if sel.selectionType() != hou.geometryType.Primitives:
                sel = sel.freeze()
                sel.convert(geo, hou.geometryType.Primitives)
            
            pts = sel.selectionString(geo, force_numeric=True)
            sop = sop.createOutputNode("modeler::array")
            sop.parm("group").set(pts)

            sop.setDisplayFlag(True)
            sop.setRenderFlag(True)
            sop.setCurrent(True, True)
            mode.scene_viewer.enterCurrentNodeState()
    
    return True

ADD_TOOL(Array, "Mesh")


def Symmetrize(mode):
    sop = geo_utils.get_sop(mode.scene_viewer)
    if sop is not None:
        if sop.type().name() == "modeler::symmetrize" and sop.evalParm("on"):
            return

        with hou.undos.group("Modeler: Symmetrize"):
            with hou.RedrawBlock() as rb:
                pwd = geo_utils.ancestor_object(sop)
                geo_utils.freeze((pwd,))
                sop = sop.parent().displayNode()
                sop.setCurrent(True, True)

                new_sop = sop.createOutputNode("modeler::symmetrize")

                if sop.geometry().findGlobalAttrib("sym_origin") is None:
                    p = sop.geometry().boundingBox().center()
                    new_sop.parmTuple("origin").set(p)

                _sym_setup_node(mode.scene_viewer, sop, new_sop)

                new_sop.setDisplayFlag(True)
                new_sop.setRenderFlag(True)
                new_sop.setCurrent(True, True)
                mode.scene_viewer.enterCurrentNodeState()

                _sym_update_instance_node(new_sop)

    return True

ADD_TOOL(Symmetrize, "Mesh")


def SymmetryOff(mode):
    sop = geo_utils.get_sop(mode.scene_viewer)
    if sop is not None:
        geo = sop.geometry()
        if geo.findGlobalAttrib("sym_axis") is not None:
            with hou.undos.group("Modeler: Symmetry Off"):
                with hou.RedrawBlock() as rb:
                    if sop.type().name() == "modeler::symmetrize":
                        sop.parm("on").set(False)
                        sop.parm("mirror").set(True)
                    else:
                        new_sop = sop.createOutputNode("modeler::symmetrize")
                        
                        _sym_setup_node(mode.scene_viewer, sop, new_sop)

                        new_sop.parm("on").set(False)
                        new_sop.parm("mirror").set(True)

                        new_sop.setDisplayFlag(True)
                        new_sop.setRenderFlag(True)
                        new_sop.setCurrent(True, True)

                    instance_node = _sym_get_instance_node(sop)
                    if instance_node is not None:
                        instance_node.destroy()

                    mode.scene_viewer.enterCurrentNodeState()
    return True

ADD_TOOL(SymmetryOff, "Mesh")


def Delete(mode):
    pwd = mode.scene_viewer.pwd()
    child_cat = pwd.childTypeCategory()

    # DELETE OBJECTS
    if child_cat == geo_utils._obj_category:
        with hou.undos.group("Modeler: Delete"):
            nodes = [node for node in (hou.selectedNodes() or pwd.children()) if node.type().name() in ("geo", "freeform")]
            if nodes:
                pwd.deleteItems(nodes)

    # DELETE SOP GEOMETRY
    elif child_cat == geo_utils._sop_category:
        sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
        if sop is not None:
            with hou.undos.group("Modeler: Delete"):
                sop.setCurrent(True, True)
                geo = sop.geometry()
                
                if sop.type().name() == "blast" and geo_utils.is_all_selected(sel, geo):
                    sop.parm("negate").set(not sop.evalParm("negate"))
                else:
                    typ = sel.selectionType()
                    items = sel.selectionString(geo, force_numeric=True)

                    if typ == hou.geometryType.Primitives:
                        sop = sop.createOutputNode("blast")
                        sop.setParms({"group": items, "grouptype": 4})
                    
                    elif typ == hou.geometryType.Edges:
                        sop = sop.createOutputNode("dissolve::2.0")
                        sop.setParms({ "group": items, "coltol": 180.0 })
                    

                    elif typ == hou.geometryType.Points:
                        sop = sop.createOutputNode("blast")
                        sop.setParms({"group": items, "grouptype": 3})
                
                    with hou.RedrawBlock() as rb:
                        sop.setDisplayFlag(True)
                        sop.setRenderFlag(True)
                        sop.setCurrent(True, True)
                        mode.scene_viewer.setCurrentState("select")

    return True

ADD_TOOL(Delete, "Mesh")


def Collapse(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        geo = sop.geometry()
        typ = sel.selectionType()
        items = sel.selectionString(geo)

        if typ == hou.geometryType.Points:
            if sel.numSelected() != 1:
                with hou.undos.group("Modeler: Collapse"):
                    f1 = sop.createOutputNode("fuse")
                    f1.setParms({"querygroup": items, "tol3d": 999999, "createsnappedgroup": True})
                    new_point = str(f1.geometry().findPointGroup("snapped_points").points()[0].number())
                    f1.parm("createsnappedgroup").set(False)
                    f1.setDisplayFlag(True)
                    f1.setRenderFlag(True)
                    f1.setCurrent(True, True)
                    mode.scene_viewer.setCurrentState("select")
                    sel = hou.Selection(sop.geometry(), typ, new_point)
                    mode.scene_viewer.setCurrentGeometrySelection(typ, (f1,), (sel,))
        else:
            with hou.undos.group("Modeler: Collapse"):
                sop = sop.createOutputNode("edgecollapse")
                sop.parm("group").set(sel.selectionString(geo, force_numeric=True))
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setCurrent(True, True)
                mode.scene_viewer.setCurrentState("select")
    return True

ADD_TOOL(Collapse, "Mesh")


def Connect(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        if sop.type().name() == "modeler::unwrap" and sop.evalParm("dosetup"):
            sop.parm("toggle_edges").pressButton()
            return

        geo = sop.geometry()

        if not geo_utils.is_all_selected(sel, geo):
            sel_type = sel.selectionType()
            count = sel.numSelected()
            sel_type = sel.selectionType()
            items = sel.selectionString(geo, force_numeric=True, collapse_where_possible = False)

            with hou.undos.group("Modeler: Connect"):
                if sel_type == hou.geometryType.Points:
                    if count == 2:
                        pt1, pt2 = sel.points(geo)
                        edge = geo.findEdge(pt1, pt2)
                        if edge is not None:
                            sop = sop.createOutputNode("edgedivide")
                            sop.setParms({ "group": edge.edgeId(), "sharedpoints": True })
                            sop.setDisplayFlag(True)
                            sop.setRenderFlag(True)
                            sop.setCurrent(True, True)
                            mode.scene_viewer.setPickGeometryType(hou.geometryType.Points)
                            mode.scene_viewer.setCurrentState("select")
                            sel = hou.Selection(sop.geometry(), hou.geometryType.Points, str(geo.intrinsicValue("pointcount")))
                            mode.scene_viewer.setCurrentGeometrySelection(hou.geometryType.Points, (sop,), (sel,))
                            return
                    
                    elif count == 1:
                        return
                    
                    grouptype = 1

                elif sel_type == hou.geometryType.Edges:
                    if sop.type().name() == "unwrap":
                        sop.hdaModule().add_edges(sop, hou.pickModifier.Toggle)
                        return

                    elif mode.scene_viewer.curViewport().type() == hou.geometryViewportType.UV:
                        mode.scene_viewer.setCurrentState("uvedit")
                        hou.ui.waitUntil(lambda: True)
                        ui.run_internal_command("h.pane.gview.state.sop.uvedit.toggle_sew")
                        return

                    if count == 1:
                        sop = sop.createOutputNode("polysplit::2.0")
                        sop.setParms({ "splitloc": items, "pathtype": 1 })
                        sop.setDisplayFlag(True)
                        sop.setRenderFlag(True)
                        sop.setHighlightFlag(True)
                        sop.setCurrent(True, True)
                        mode.scene_viewer.enterCurrentNodeState()
                        return

                    grouptype = 2
                
                else: 
                    grouptype = 0

                sop = sop.createOutputNode("modeler::connect")
                sop.setParms({ "group": items, "grouptype": grouptype })
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setHighlightFlag(True)
                sop.setCurrent(True, True)
                if sel_type == hou.geometryType.Points:
                    mode.scene_viewer.setCurrentState("select")
                else:
                    mode.scene_viewer.enterCurrentNodeState()
    return True

ADD_TOOL(Connect, "Mesh")


def MultiLoop(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None and sel.selectionType() == hou.geometryType.Edges:
        with hou.undos.group('Modeler: Multi Loop'):
            geo = sop.geometry()
            sop = sop.createOutputNode("modeler::multiloop")
            sop.parm('group').set(sel.selectionString(geo, force_numeric=True))
            
            with hou.RedrawBlock() as rb:
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setCurrent(True, True)
            
            mode.scene_viewer.enterCurrentNodeState()

    return True

ADD_TOOL(MultiLoop, "Mesh")


def Slice(mode, doclip=False, domirror=False):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        items = geo_utils.selected_polygons(sel, sop.geometry())
        if items is not None:   
            with hou.undos.group("Modeler: Slice"):
                sop = sop.createOutputNode("modeler::slice")
                sop.setParms({ "group": items, "doclip": doclip, "domirror": domirror })

                mod = sop.hdaModule()
                mod.auto_origin(sop)

                with hou.RedrawBlock() as rb:
                    sop.setDisplayFlag(True)
                    sop.setRenderFlag(True)
                    sop.setCurrent(True, True)
                    
                    mod.dir_from_best_axis(sop, 0)

                    mode.scene_viewer.enterCurrentNodeState()

    return True

ADD_TOOL(Slice, "Mesh")


def Clip(mode):
    return Slice(mode, True)

ADD_TOOL(Clip, "Mesh")


def Mirror(mode):
    return Slice(mode, True, True)

ADD_TOOL(Mirror, "Mesh")


def Subdivide(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        geo = sop.geometry()
        items = geo_utils.selected_polygons(sel, geo)
        if items is not None:
            with hou.undos.group("Modeler: Subdivide"):
                sop = sop.createOutputNode("subdivide")
                sop.setParms({ "subdivide": items, "surroundpoly": 2 })

                with hou.RedrawBlock() as rb:
                    sop.setDisplayFlag(True)
                    sop.setRenderFlag(True)
                    sop.setHighlightFlag(True)
                    sop.setCurrent(True, True)
                
            mode.scene_viewer.setCurrentState("subdivide")
    
    return True

ADD_TOOL(Subdivide, "Mesh")


def BridgeConnected(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None and sel.selectionType() == hou.geometryType.Edges:
        with hou.undos.group('Modeler: Bridge Connected'):
            if sop.type().name() == 'topobuild':
                sop.parm('topobuild_preedit').pressButton()
            else:
                sop = sop.createOutputNode('topobuild')

            # USE TOPO REFERENCE AS PROJECTION INPUT
            highres_sop = topo_tools.get_highres_sop()
            if highres_sop is not None:
                om = geo_utils.inject_ref_objectmerge(highres_sop, sop.parent())
                sop.setInput(1, om)

            sop.parm('topobuild_numedits').set(1)
            sop.parm('edit1_tool').set('bridgeconnectededges')
            sop.parm('edit1_data').set(sel.selectionString(sop.geometry(), force_numeric=True))
            
            with hou.RedrawBlock() as rb:
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setCurrent(True, True)
            
            mode.scene_viewer.setCurrentState('select')

    return True

ADD_TOOL(BridgeConnected, "Mesh")


def Fill(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        geo = sop.geometry()
        typ = sel.selectionType()

        with hou.undos.group("Modeler: Fill"):
            with hou.RedrawBlock() as rb:
                if typ == hou.geometryType.Edges:
                    edges = sel.selectionString(geo, force_numeric=True)                    
                    completeloops = True

                elif typ == hou.geometryType.Primitives:
                    sop1 = sop.createOutputNode("groupcreate")
                    sop1.setParms({ "groupname": "__prims__", "basegroup": sel.selectionString(geo) })                        

                    sop2 = sop1.createOutputNode("grouppromote")
                    sop2.setParms({ "fromtype1": 1, "totype1": 2, "group1": "__prims__", "newname1": "__selection__", "preserve1": True, "onlyfull1": True})

                    sop3 = sop2.createOutputNode("blast")
                    sop3.setParms({ "group": "__prims__", "grouptype": 4, "removegrp": True })

                    sop = pwd.collapseIntoSubnet((sop1, sop2, sop3), "hole_for_polyfill1")
                    sop.moveToGoodPosition()

                    edges = "__selection__"
                    completeloops = False

                else:
                    sel = sel.freeze()
                    sel.convert(geo, hou.geometryType.Edges)
                    edges = sel.selectionString(geo, force_numeric=True)
                    completeloops = True

                sop = sop.createOutputNode("polyfill")
                sop.setParms({ "group": edges, "fillmode": 5, "smoothtoggle": False, "subdivtoggle": False, "completeloops": completeloops })
        
                sop.setDisplayFlag(True)
                hou.ui.waitUntil(lambda: True)
                if sop.warnings():
                    sop.parm("fillmode").set(0) 
                sop.setCurrent(True, True)
                sop.setHighlightFlag(True)
                sop.setRenderFlag(True)

                mode.scene_viewer.enterCurrentNodeState()
    
    return True

ADD_TOOL(Fill, "Mesh")


def Flip(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        items = sel.selectionString(sop.geometry(), force_numeric=True)
        typ = sel.selectionType()
        if typ == hou.geometryType.Primitives:
            with hou.undos.group("Modeler: Flip Faces"):
                sop = sop.createOutputNode("reverse")
                sop.parm("group").set(items)
                with hou.RedrawBlock() as rb:
                    sop.setDisplayFlag(True)
                    sop.setRenderFlag(True)
                    sop.setCurrent(True, True)
                
            mode.scene_viewer.setCurrentState("select")

        elif typ == hou.geometryType.Edges:
            if mode.scene_viewer.currentState() == "edgeflip":
                sop.parm("cycles").set(sop.evalParm("cycles") + 1)
            else:
                with hou.undos.group("Modeler: Flip Edges"):
                    sop = sop.createOutputNode("edgeflip")
                    sop.parm("group").set(items)

                    with hou.RedrawBlock() as rb:
                        sop.setDisplayFlag(True)
                        sop.setRenderFlag(True)
                        sop.setHighlightFlag(True)
                        sop.setCurrent(True, True)
                    
                mode.scene_viewer.enterCurrentNodeState()
    
    return True

ADD_TOOL(Flip, "Mesh")


def Fuse(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        with hou.undos.group("Modeler: Fuse"):
            typ = sel.selectionType()
            geo = sop.geometry()
            
            if typ != hou.geometryType.Points:
                sel = sel.freeze()
                sel.convert(geo, hou.geometryType.Points)

            items = sel.selectionString(geo, force_numeric=True)

            try:
                initial_sel_type = mode.scene_viewer.pickGeometryType()
                sel1 = None
                gs = mode.scene_viewer.selectGeometry("Select target point or press Escape to cancel.", geometry_types=(hou.geometryType.Points,), use_existing_selection=False, quick_select=True, consume_selections=False)
                sel1 = gs.selections()[0]
            except:
                mode.scene_viewer.setPickGeometryType(initial_sel_type)

            sop = sop.createOutputNode("fuse")
            sop.parm("querygroup").set(items)
            
            if sel1 is not None:
                sop.setParms({ "usetargetgroup": 1, "targetgroup": sel1.selectionString(geo, force_numeric=True), "usetol3d": False })

            with hou.RedrawBlock() as rb:
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setCurrent(True, True)
    return True

ADD_TOOL(Fuse, "Mesh")


def CreateNormals(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        with hou.undos.group("Modeler: Create Normals"):
            sop = sop.createOutputNode("normal")
            sop.setParms({"method": 2, "cuspangle": 40})
            items = sel.selectionString(sop.geometry(), force_numeric=True)
            if items:
                typ = sel.selectionType()
                if typ == hou.geometryType.Primitives:
                    sop.setParms({ "group": items, "grouptype": 4 })
                elif typ == hou.geometryType.Edges:
                    sop.setParms({ "group": items, "grouptype": 2 })
                elif typ == hou.geometryType.Points:
                    sop.setParms({ "group": items, "grouptype": 3 })

            with hou.RedrawBlock() as rb:
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setCurrent(True, True)
            mode.scene_viewer.enterCurrentNodeState()
    
    return True

ADD_TOOL(CreateNormals, "Mesh")


def CreaseEdges(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        with hou.undos.group("Crease Edges"):
            geo = sop.geometry()
            typ = sel.selectionType()
            items = sel.selectionString(geo, force_numeric=True)
            if typ == hou.geometryType.Primitives:
                b = sop.createOutputNode("blast")
                b.parm("group").set(items)
                g = b.createOutputNode("groupcreate")
                g.setParms({ "groupname": "__edges__", "grouptype": 2, "groupbase": False, "groupedges": True, "unshared": True })
                t = sop.createOutputNode("grouptransfer")
                t.setParms({ "edgegroups": "__edges__", "thresholddist": 0.0001 })
                t.setInput(1, g)
                t.setHighlightFlag(True)
                edges = t.geometry().selection().selectionString(geo, force_numeric=True)
                pwd.deleteItems([b, g, t])

            elif typ == hou.geometryType.Edges:
                edges = sel.selectionString(geo, force_numeric=True)
            
            else:
                return

            c = sop.createOutputNode("crease")
            c.setParms({ "group": edges, "op": 1 })
            
            with hou.RedrawBlock() as rb:
                c.setDisplayFlag(True)
                c.setHighlightFlag(True)
                c.setCurrent(True, True)

            mode.scene_viewer.enterCurrentNodeState()

    return True

ADD_TOOL(CreaseEdges, "Mesh")


def CleanEdges(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        geo = sop.geometry()
        prims = geo_utils.selected_polygons(sel, geo)
        if prims is not None:
            with hou.undos.group("Modeler: Clean Edges"):
                sop = sop.createOutputNode("clean_edges")
                sop.parm("group").set(prims)
                
                with hou.RedrawBlock() as rb:
                    sop.setDisplayFlag(True)
                    sop.setRenderFlag(True)
                    sop.setCurrent(True, True)

            mode.scene_viewer.setCurrentState("select")
    
    return True

ADD_TOOL(CleanEdges, "Mesh")


def FixOverlaps(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        geo = sop.geometry()
        prims = geo_utils.selected_polygons(sel, geo)
        if prims is not None:
            with hou.undos.group("Modeler: Fix Overlaps"):
                sop = sop.createOutputNode("fix_overlaps")
                sop.parm("group").set(prims)
                
                with hou.RedrawBlock() as rb:
                    sop.setDisplayFlag(True)
                    sop.setRenderFlag(True)
                    sop.setCurrent(True, True)

            mode.scene_viewer.setCurrentState("select")
    
    return True

ADD_TOOL(FixOverlaps, "Mesh")


def FixCurves(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        geo = sop.geometry()
        prims = geo_utils.selected_polygons(sel, geo, close_faces=False)
        if prims is not None:
            with hou.undos.group("Modeler: Fix Curves"):
                sop = sop.createOutputNode("fix_curves")
                sop.parm("group").set(prims)
                
                with hou.RedrawBlock() as rb:
                    sop.setDisplayFlag(True)
                    sop.setRenderFlag(True)
                    sop.setCurrent(True, True)

            mode.scene_viewer.setCurrentState("select")
    
    return True

ADD_TOOL(FixCurves, "Mesh")


def FixNormals(mode):
    sop = geo_utils.get_sop(mode.scene_viewer)
    if sop is not None:
        with hou.undos.group("Modeler: Fix Normal Directions"):
            sop = sop.createOutputNode("facet", "fix_normals")
            sop.setParms({"cons": 2, "dist": 0.0001, "orientPolys": True})
            
            with hou.RedrawBlock() as rb:
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setCurrent(True, True)
        
        mode.scene_viewer.setCurrentState("select")
    
    return True

ADD_TOOL(FixNormals, "Mesh")


def TopoMode(mode):
    topo_tools.topo_mode(mode.scene_viewer)

ADD_TOOL(TopoMode, "Mesh")


def AutoUnwrap(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        geo = sop.geometry()
        
        if sel.selectionType() == hou.geometryType.Primitives:
            prims = geo_utils.selected_polygons(sel, geo)
        
        elif geo_utils.is_all_selected(sel, geo):
            prims = "!_3d_hidden_primitives"
        
        else:
            return

        with hou.undos.group("Modeler: AutoUnwrap"):
            sop = sop.createOutputNode("modeler::auto_unwrap")
            sop.parm("group").set(prims)
            
            with hou.RedrawBlock() as rb:
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setCurrent(True, True)
        
        mode.scene_viewer.enterCurrentNodeState()
    
    return True

ADD_TOOL(AutoUnwrap, "Mesh")


def Unwrap(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        geo = sop.geometry()

        if sel.selectionType() == hou.geometryType.Primitives:
            prims = geo_utils.selected_polygons(sel, geo)
        
        elif geo_utils.is_all_selected(sel, geo):
            prims = "!_3d_hidden_primitives"
        
        else:
            return
        
        with hou.undos.group("Modeler: Unwrap"):
            sop = sop.createOutputNode("modeler::unwrap")
            sop.parm("group").set(prims)
            
            with hou.RedrawBlock() as rb:
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setCurrent(True, True)
                
        mode.scene_viewer.setCurrentState("select")
    
    return True

ADD_TOOL(Unwrap, "Mesh")


def Layout(mode):
    scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        geo = sop.geometry()
        
        if sel.selectionType() == hou.geometryType.Primitives:
            prims = geo_utils.selected_polygons(sel, geo)
        
        elif geo_utils.is_all_selected(sel, geo):
            prims = "!_3d_hidden_primitives"
        
        else:
            return

        with hou.undos.group("Modeler: UV Layout"):
            if sop.type().name() == "modeler::unwrap":
                sop.parm("dosetup").set(False)
                hou.ui.waitUntil(lambda: True)
            
            sop = sop.createOutputNode("uvlayout::3.0")
            sop.setParms({ "group": prims,  "axisalignislands": 2, "paddingboundary": True, "padding": 4, "correctareas": True })
            
            with hou.RedrawBlock() as rb:
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setCurrent(True, True)
            
            # ui.executeDeferred(scene_viewer.enterCurrentNodeState)
            mode.scene_viewer.enterCurrentNodeState()

    return True

ADD_TOOL(Layout, "Mesh")


###############################################################################
# MESH STATES


def Extrude(mode, mods=ui.qt.NoModifier):
    global _extrude_edges_scene_viewer

    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        with hou.undos.group("Modeler: Extrude"):
            sel_type = sel.selectionType()

            # POINTS
            if sel_type == hou.geometryType.Points:
                sop = sop.createOutputNode("modeler::extrude_points")
                sop.parm("group").set(sel.selectionString(sop.geometry(), force_numeric=True))
                
                sop.setDisplayFlag(True)
                sop.setHighlightFlag(True)
                sop.setRenderFlag(True)

                with hou.RedrawBlock() as rb:
                    sop.setCurrent(True, True)

                mode.scene_viewer.enterCurrentNodeState()  
                
                LeftButtonDrag(mode)
            
            # EDGES
            elif sel_type == hou.geometryType.Edges:
                sop = sop.createOutputNode("polyextrude::2.0")
                sop.setParms({ "group": sel.selectionString(sop.geometry(), force_numeric=True), "xformfront": True, "xformspace": 1 })
                with hou.RedrawBlock() as rb:
                    sop.setDisplayFlag(True)
                    sop.setHighlightFlag(True)
                    sop.setRenderFlag(True)
                    sop.setCurrent(True, True)
                ui.show_handles(mode.scene_viewer, False)
                hou.hscript('omparm "Polygon Extruder 2" extrude2 {} "rotate(1)"'.format(sop.path()))
                mode.scene_viewer.enterViewState()
                mode.scene_viewer.enterCurrentNodeState()
                
                _extrude_edges_scene_viewer = mode.scene_viewer
                MiddleButtonDrag(mode, release_callback=_extrude_edges_release_callback)
            
            # FACES
            else:
                sop = sop.createOutputNode("modeler::extrude")
                sop.setParms({ "group": sel.selectionString(sop.geometry(), force_numeric=True) })

                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                
                with hou.RedrawBlock() as rb:
                    sop.setCurrent(True, True)
                
                mode.scene_viewer.enterCurrentNodeState()
                
                return LeftButtonDrag(mode, mods)

    return True

_extrude_edges_scene_viewer = None
def _extrude_edges_release_callback():
    ui.show_handles(_extrude_edges_scene_viewer, True)

ADD_TOOL(Extrude, "Mesh States")


def Inset(mode):
    return Extrude(mode, ui.qt.ShiftModifier)

ADD_TOOL(Inset, "Mesh States")


def Bevel(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        typ = sel.selectionType()

        if typ == hou.geometryType.Primitives:
            grouptype = 0
        elif typ == hou.geometryType.Points:
            grouptype = 1
        else:
            grouptype = 2

        geo = sop.geometry()

        with hou.undos.group("Modeler: Bevel"):
            sop = sop.createOutputNode("modeler::bevel")
            sop.setParms({ "group": sel.selectionString(geo, force_numeric=True), "grouptype": grouptype })
            with hou.RedrawBlock() as rb:
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setCurrent(True, True)
        
        mode.scene_viewer.enterCurrentNodeState()
        
        return LeftButtonDrag(mode)
    
    return True

ADD_TOOL(Bevel, "Mesh States")


def Bridge(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)

    if sop is not None:
        success = True
        geo = sop.geometry()
        typ = sel.selectionType()

        if typ == hou.geometryType.Edges:
            edges = sel.edges(geo)
            half = int(len(edges) / 2)
            src = " ".join( [edge.edgeId() for edge in edges[0:half]] )
            dst = " ".join( [edge.edgeId() for edge in edges[half:]] )


        elif typ == hou.geometryType.Primitives:
            prims = sel.prims(geo)
            half = int(len(prims) / 2)
            src = " ".join([str(prim.number()) for prim in prims[0:half]])
            dst = " ".join([str(prim.number()) for prim in prims[half:]])
        
        else:
            return True

        with hou.undos.group("Modeler: Bridge"):
            sop = sop.createOutputNode("modeler::bridge")
            sop.setParms({ "srcgroup": src, "dstgroup" : dst })
            with hou.RedrawBlock() as rb:
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
                sop.setCurrent(True, True)
            mode.scene_viewer.enterCurrentNodeState()

        return LeftButtonDrag(mode, ui.qt.ControlModifier)
    
    return True

ADD_TOOL(Bridge, "Mesh States")


def Thickness(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None: 
        geo = sop.geometry()
        items = geo_utils.selected_polygons(sel, geo)
        if items is not None:
            with hou.undos.group("Modeler: Thickness"):
                sop = sop.createOutputNode("modeler::thickness")
                sop.parm("group").set(items)

                with hou.RedrawBlock() as rb:
                    sop.setDisplayFlag(True)
                    sop.setRenderFlag(True)
                    sop.setCurrent(True, True)

            mode.scene_viewer.enterCurrentNodeState()
            
            return LeftButtonDrag(mode)
    
    return True

ADD_TOOL(Thickness, "Mesh States")


def Hose(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)

    if sop is not None:
        items = geo_utils.selected_polygons(sel, sop.geometry())
        
        if items is not None:
            with hou.undos.group("Modeler: Hose"):
                sop = sop.createOutputNode("modeler::hose")
                sop.parm("group").set(items)

                with hou.RedrawBlock() as rb:
                    sop.setDisplayFlag(True)
                    sop.setRenderFlag(True)
                    sop.setCurrent(True, True)

            mode.scene_viewer.enterCurrentNodeState()

            return LeftButtonDrag(mode)
    
    return True

ADD_TOOL(Hose, "Mesh States")


def Split(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        with hou.undos.group("Modeler: Split"):
            if mode.state() == "polysplit::2.0" and not sop.evalParm("splitloc"):
                ui.run_internal_command("h.pane.gview.accept")
            mode.scene_viewer.setCurrentState("polysplit::2.0")
        ui.home_selected()
    
    return True

ADD_TOOL(Split, "Mesh States")


def Loop(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        with hou.undos.group("Modeler: Loop"):
            with hou.RedrawBlock() as rb:
                if mode.state() in ("polysplit::2.0", "edgeloop") and not sop.evalParm("splitloc"):
                    sop.destroy()
                mode.scene_viewer.setCurrentState("edgeloop")
        ui.home_selected()
    
    return True

ADD_TOOL(Loop, "Mesh States")


def Knife(mode):
    cur_node = mode.scene_viewer.currentNode()
    if cur_node.type().category() == geo_utils._sop_category:
        with hou.undos.group("Modeler: Knife"):
            knife_sop = cur_node.createOutputNode("knife")
            knife_sop.parm("knifeop").set("both")
            knife_sop.setCreatorState("knife")
            with hou.RedrawBlock() as rb:
                knife_sop.setDisplayFlag(True)
                knife_sop.setRenderFlag(True)
                knife_sop.setCurrent(True, True)
                mode.scene_viewer.setCurrentState("knife")
                knife_sop.setHighlightFlag(False)
    
    return True

ADD_TOOL(Knife, "Mesh States")


def PointWeld(mode):
    sop, sel, pwd = geo_utils.sop_selection(mode.scene_viewer)
    if sop is not None:
        with hou.undos.group("Modeler: Point Weld"):
            geo_utils.soptoolutils.genericTool({}, "pointweld")
    
    return True

ADD_TOOL(PointWeld, "Mesh States")
