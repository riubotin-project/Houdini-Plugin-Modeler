import hou, objecttoolutils, soptoolutils


_sop_category = hou.sopNodeTypeCategory()
_obj_category = hou.objNodeTypeCategory()
_sop_and_obj_categories = (_sop_category, _obj_category)


global_brush_radius = 0.1

###############################################################################
# SELECTION UTILS


def get_sop(scene_viewer, set_current=True):
    cur_node = scene_viewer.currentNode()

    if cur_node.type().category() == _sop_category:
        display = cur_node.parent().displayNode()
        display.setCurrent(True, True)
        return display
    else:
        sel = hou.selectedNodes()
        if sel and sel[0].type().childTypeCategory() ==_sop_category:
            sop = sel[0].displayNode()
            if sop is not None:
                if set_current:
                    sop.setCurrent(True, True)
                    hou.ui.waitUntil(lambda: True)
                return sop
    
    return None


def get_edit_sop(scene_viewer, sop):
    if sop.type().name() == "edit":
        sop.parm("apply").pressButton()
        sop.setParms({ "slideonsurface": False, "switcher1": 0, "modeswitcher1": 0,
                       "px": 0.0, "py": 0.0, "pz": 0.0, "prx": 0.0, "pry": 0.0, "prz": 0.0 })

    else:
        sop = sop.createOutputNode("edit")

    return sop


def sop_selection(scene_viewer, auto_select_all=False):
    pwd = scene_viewer.pwd()
    child_cat = pwd.childTypeCategory()
    
    # OBJ
    if child_cat == _obj_category:
        objects = [node for node in hou.selectedNodes() if node.type().name()=="geo"]
        if objects:
            sop = objects[0].displayNode()
            if sop is not None:
                with hou.RedrawBlock() as rb:
                    scene_viewer.setPwd(objects[0])
                    sop.setCurrent(True, True)
                    geo = sop.geometry()
                    if geo.findPrimGroup("_3d_hidden_primitives") is not None:
                        sel = hou.Selection(geo, hou.geometryType.Primitives, "!_3d_hidden_primitives")
                    else:
                        sel = hou.Selection(geo, hou.geometryType.Primitives, "*")

                    if scene_viewer.pickGeometryType() != hou.geometryType.Primitives:
                        scene_viewer.setPickGeometryType(hou.geometryType.Primitives)
                    
                return sop, sel, objects[0]

    # SOP
    elif child_cat == _sop_category:
        sop = pwd.displayNode()
        if sop is not None:
            sop_type_name = sop.type().name()

            # COMMIT TOPO BUILD SELECTION
            if sop_type_name == "topobuild":
                scene_viewer.setCurrentState("select")

            # GET SCENE VIEWER GEOMETRY SELECTION
            gs = scene_viewer.currentGeometrySelection()
            
            # NOT "SELECT" STATE
            if gs is None:
                sel = sop.geometry().selection()
                if sel is not None and sel.numSelected() > 0:
                                        
                    # CATCH FRESH EDIT SOP
                    if sop.type().name() == "edit" and sop.cookCount() < 4:
                        sel = sel.freeze()
                        new_sop = sop.inputs()[0]
                        sop.destroy()
                        sop = new_sop

                    typ = sel.selectionType()
                    if typ != scene_viewer.pickGeometryType():
                        scene_viewer.setPickGeometryType(typ)
                        hou.ui.waitUntil(lambda: True)

                    return sop, sel, ancestor_object(pwd)

            # "SELECT" STATE OR OTHER STATE IS IN THE SELECTION MODE
            elif gs.nodes():
                return sop, gs.selections()[0], ancestor_object(pwd)


            # EMPTY SELECTION
            geo = sop.geometry()
            viewer_sel_type = scene_viewer.pickGeometryType()
            if geo.findPrimGroup("_3d_hidden_primitives") is None:
                sel = hou.Selection(geo, viewer_sel_type, "*")
            else:
                sel = hou.Selection(geo, hou.geometryType.Primitives, "!_3d_hidden_primitives")
                if viewer_sel_type != hou.geometryType.Primitives:
                    sel = sel.freeze()
                    sel.convert(geo, viewer_sel_type)

            # AUTO SELECT WHOLE GEOMETRY
            if auto_select_all:
                # CATCH FRESH EDIT SOP
                scene_viewer.setCurrentState("select")
                try:
                    scene_viewer.setCurrentGeometrySelection(viewer_sel_type, (sop,), (sel,))
                except hou.ObjectWasDeleted:
                    hou.ui.waitUntil(lambda: True)
                    scene_viewer.setCurrentGeometrySelection(viewer_sel_type, (scene_viewer.currentNode(),), (sel,))

            return sop, sel, ancestor_object(pwd)

    return None, None, None


def is_all_selected(sel, geo):
    sel_type = sel.selectionType()
    
    # NOT ISOLATED POLYGONS
    if geo.findPrimGroup("_3d_hidden_primitives") is None:
        if sel_type == hou.geometryType.Primitives:
            return sel.numSelected() == geo.intrinsicValue("primitivecount")
        elif sel_type == hou.geometryType.Points:
            return sel.numSelected() == geo.intrinsicValue("pointcount")
        else:
            sel = sel.freeze()
            sel.convert(geo, hou.geometryType.Points)
            return sel.numSelected() == geo.intrinsicValue("pointcount")
    
    # ISOLATED POLYGONS
    else:
        unisolated_faces_sel = hou.Selection(geo, hou.geometryType.Primitives, "!_3d_hidden_primitives")
        if sel_type == hou.geometryType.Primitives:
            sel = sel.freeze()
            sel.combine(geo, unisolated_faces_sel, hou.pickModifier.Toggle)
            return not sel.numSelected()
        else:
            unisolated_faces_sel.convert(geo, sel_type)
            unisolated_faces_sel.combine(geo, sel, hou.pickModifier.Toggle)
            return not unisolated_faces_sel.numSelected()
    return False


def whole_selection(node, selection_type):
    geo = node.geometry()
    sel = hou.Selection(geo, hou.geometryType.Primitives, "!_3d_hidden_primitives")
    if selection_type != hou.geometryType.Primitives:
        sel = sel.freeze()
        sel.convert(geo, selection_type)
    return sel


def set_sop_selection(scene_viewer, sop, selection, selection_type):
    scene_viewer.setCurrentState("select")
    try:
        scene_viewer.setCurrentGeometrySelection(selection_type, (sop,), (selection,))
    except hou.ObjectWasDeleted:
        hou.ui.waitUntil(lambda: True)
        scene_viewer.setCurrentGeometrySelection(selection_type, (scene_viewer.currentNode(),), (selection,))

def clear_sop_selection(scene_viewer):
    sel_type = scene_viewer.pickGeometryType()
    sel = hou.Selection(sel_type)
    scene_viewer.setCurrentGeometrySelection(sel_type, (scene_viewer.currentNode(),), (sel,))


def selected_polygons(sel, geo, close_faces=True):
    if is_all_selected(sel, geo):
        return "!_3d_hidden_primitives" if close_faces else "@intrinsic:closed==0"
    elif sel.selectionType() == hou.geometryType.Primitives:
        return sel.selectionString(geo, force_numeric=True)
    else:
        return None


def get_selection_normal_and_center(sop, sel, geo):
    with hou.undos.disabler():
        g = sop.createOutputNode("modeler::group_normal")
        typ = sel.selectionType()
        if typ == hou.geometryType.Primitives:
            grouptype = 0
        elif typ == hou.geometryType.Points:
            grouptype = 1
        else:
            grouptype = 2

        g.setParms({ "group": sel.selectionString(geo), "grouptype": grouptype })

        ggeo = g.geometry()
        n = hou.Vector3(ggeo.attribValue("N"))
        c = hou.Vector3(ggeo.attribValue("center"))
        g.destroy()
        return n, c


def get_selection_center_and_rotation(scene_viewer):
    if scene_viewer.pwd().childTypeCategory() == _sop_category:
        sop, sel, pwd = sop_selection(scene_viewer)
        if sop is not None:
            geo = sop.geometry()
            if not is_all_selected(sel, geo):
                z, center = get_selection_normal_and_center(sop, sel, geo)
                world_xform = ancestor_object(sop).worldTransform()
                
                initial_sel_type = scene_viewer.pickGeometryType()

                try:
                    gs = scene_viewer.selectGeometry("To rotate geometry, select the nearest Z-axis. Press Escape to just translate.",
                                                     consume_selections=False, geometry_types=(hou.geometryType.Edges,), use_existing_selection=False, quick_select=True)
                    
                    pt1, pt2 = gs.selections()[0].edges(geo)[0].points()
                    pos1 = pt1.position()
                    pos2 = pt2.position()
                    y = (pos2 - pos1).normalized()

                except:
                    return center * world_xform, (0.0, 0.0, 0.0)

                scene_viewer.setPickGeometryType(initial_sel_type)
                
                world_xform_inverted_transposed = world_xform.inverted().transposed()

                global_y = y * world_xform_inverted_transposed
                global_z = z * world_xform_inverted_transposed
                global_x = global_z.cross(global_y)
                xform =  hou.Matrix3((global_x, global_z, global_y))

                return center * world_xform, xform.extractRotates()

    return None, None


def sop_selection_center(sop, sel, xform=hou.hmath.identityTransform()):
    typ = sel.selectionType()
    geo = sop.geometry()
    if typ == hou.geometryType.Points:
        return geo.pointBoundingBox(sel.selectionString(geo)).center() * xform
    elif typ == hou.geometryType.Primitives:
        return geo.primBoundingBox(sel.selectionString(geo)).center() * xform
    else:
        sel = sel.freeze()
        sel.convert(geo, hou.geometryType.Points)
        return geo.pointBoundingBox(sel.selectionString(geo)).center() * xform


def get_object(scene_viewer, prompt="Select Object", use_existing_selection=False):
    cur_node = scene_viewer.currentNode()
    with hou.undos.disabler():
        try:
            objects = scene_viewer.selectObjects(prompt=prompt, quick_select=True, use_existing_selection=use_existing_selection, allow_multisel=False, allowed_types=["geo", "subnet"])
            if objects:
                obj = objects[0]
                display = obj.displayNode()
                if display is not None:
                    return obj, display
        
        except hou.OperationInterrupted:
            scene_viewer.setCurrentState("select")
            return None, None
        
        finally:
            scene_viewer.setCurrentNode(cur_node)
            scene_viewer.setCurrentState("select")

        return None, None


###############################################################################
# HIT UTILS


def hit_info(scene_viewer, state_origin, state_dir, mouse_x, mouse_y, viewport, local=True):
    # GEO IS BEHIND X, Y
    hit_node = viewport.queryNodeAtPixel(int(mouse_x), int(mouse_y))
    if hit_node is not None and not hit_node.isInsideLockedHDA():
        # NODE HAS GEO
        hit_geo = hit_node.geometry()
        
        if hit_geo is not None:
            # GET HIT PWD AND XFORM
            hit_pwd = hit_node.creator()

            hit_xform = hit_pwd.worldTransform()

            # GET CURRENT PWD AND XFORM
            this_node = scene_viewer.currentNode()
            this_pwd = this_node.creator()
            this_xform = this_pwd.worldTransform()

            # CONVERT STATE O\D TO WORLD SPACE DATA
            world_cursor_origin = state_origin * this_xform
            world_cursor_dir = state_dir * this_xform.inverted().transposed()

            # CONVERT WORLD SPACE STATE O\D TO HIT GEO O\D
            hit_cursor_origin = world_cursor_origin * hit_xform.inverted()
            hit_cursor_dir = world_cursor_dir * hit_xform.transposed()

            # TMP DATA
            hit_pos = hou.Vector3()
            hit_normal = hou.Vector3()
            uvw = hou.Vector3()
            
            # TEST INTERSECT
            intersected_prim_number = hit_geo.intersect(hit_cursor_origin, hit_cursor_dir, hit_pos, hit_normal, uvw)
            
            # SOME PRIM IS BEHIND X, Y
            if intersected_prim_number > -1:
                prim = hit_geo.prim(intersected_prim_number)
                prim_center = prim.boundingBox().center()
                points = prim.points()
                points_ = points + [ points[0] ]
                nearest_snap_D = hit_pos.distanceTo(prim_center)        
                nearest_snap = prim_center
                nearest_edge_D = 9999.9999
                nearest_edge = None
                nearest_edge_pos1 = None
                nearest_edge_pos2 = None
                edge_positions = []
                positions = hou.Vector3()

                for i in range(len(points_)-1):
                    pos1 = points_[i].position()
                    pos2 = points_[i+1].position()

                    positions += pos1

                    # TEST POINT
                    d = hit_pos.distanceTo(pos1)
                    if d < nearest_snap_D:
                        nearest_snap_D = d
                        nearest_snap = pos1

                    edge_positions.append((pos1 * hit_xform * this_xform.inverted(), pos2 * hit_xform * this_xform.inverted()))

                    # TEST EDGE MIDPOS
                    midpos = (pos1 + pos2) / 2.0
                    d = hit_pos.distanceTo(midpos)
                    if d < nearest_edge_D:
                        nearest_edge_D = d
                        nearest_edge = midpos
                        nearest_edge_pos1 = pos1
                        nearest_edge_pos2 = pos2 

                # EDGE IS CLOSER
                if nearest_edge.distanceTo(hit_pos) < nearest_snap.distanceTo(hit_pos):
                    nearest_snap = nearest_edge

                hit_normal = hit_normal * hit_xform.inverted().transposed() * this_xform.transposed()
                hit_pos = hit_pos * hit_xform * this_xform.inverted()
                prim_center = prim_center * hit_xform * this_xform.inverted()
                nearest_snap = nearest_snap * hit_xform * this_xform.inverted()
                nearest_edge = nearest_edge * hit_xform * this_xform.inverted()

                kwargs = { "hit_pos": hit_pos, "prim": prim, "prim_center": prim_center, "prim_normal": hit_normal, "edge_positions": edge_positions,
                           "nearest_pos": nearest_snap, "nearest_midpos": nearest_edge, "nearest_midpos_positions": (nearest_edge_pos1, nearest_edge_pos2) }

                return kwargs


    return None


def intersect_geo(geo, ray, from_xform=None, to_xform=None):
    hit_pos = hou.Vector3()
    hit_normal = hou.Vector3()
    uvw = hou.Vector3()
    intersected = geo.intersect(ray[0], ray[1], hit_pos, hit_normal, uvw)
    if intersected > -1:
        prim = geo.prim(intersected)
        prim_center = prim.boundingBox().center()
        points = prim.points()
        points_ = points + [ points[0] ]
        nearest_perp = None
        nearest_perp_D = 9999.9999
        nearest_snap_D = hit_pos.distanceTo(prim_center)        
        nearest_snap = prim_center
        nearest_edge_D = 9999.9999
        nearest_edge = None
        positions = hou.Vector3()

        for i in range(len(points_)-1):
            pos1 = points_[i].position()
            pos2 = points_[i+1].position()

            positions += pos1

            # TEST POINT
            d = hit_pos.distanceTo(pos1)
            if d < nearest_snap_D:
                nearest_snap_D = d
                nearest_snap = pos1

            # TEST EDGE MIDPOS
            midpos = (pos1 + pos2) / 2.0
            d = hit_pos.distanceTo(midpos)
            if d < nearest_edge_D:
                nearest_edge_D = d
                nearest_edge = midpos

            # TEST PERPENDICULAR
            perp = prim_center.pointOnSegment(pos1, pos2)
            d = hit_pos.distanceTo(perp)
            if d < nearest_perp_D:
                nearest_perp_D = d
                nearest_perp = perp

        if nearest_edge.distanceTo(hit_pos) < nearest_snap.distanceTo(hit_pos):
            nearest_snap = nearest_edge

        if from_xform is not None:
            hit_pos = hit_pos * from_xform * to_xform.inverted()
            prim_center = prim_center * from_xform * to_xform.inverted()
            hit_normal = hit_normal * from_xform.inverted().transposed() * to_xform.transposed()
            nearest_snap = nearest_snap * from_xform * to_xform.inverted()
            nearest_edge = nearest_edge * from_xform * to_xform.inverted()
            nearest_perp = nearest_perp * from_xform * to_xform.inverted()

        kwargs = { "hit_pos": hit_pos, "prim": prim, "prim_center": prim_center, "prim_normal": hit_normal,
                   "nearest_pos": nearest_snap, "nearest_midpos": nearest_edge, "nearest_perpendicular": nearest_perp }

        return kwargs

    return None


###############################################################################
# EDIT SOP UTILS


def setup_edit_sop_for_symmetry(sop):
    geo = sop.geometry()
    if geo.findGlobalAttrib("sym_origin") is None:
        sop.parm("doreflect").set(False)
    else:
        sym_origin = geo.attribValue("sym_origin")
        sym_dir = geo.attribValue("sym_dir")
        sop.setParms({ "doreflect": True, "symthreshold": 0.001,
                       "symaxisx": sym_dir[0], "symaxisy": sym_dir[1], "symaxisz": sym_dir[2],
                       "symorigx": sym_origin[0], "symorigy": sym_origin[1], "symorigz": sym_origin[2] })


###############################################################################
# MISC GEO AND NETWORK UTILS


def inject_ref_objectmerge(node, object_to_inject):
    node_path = node.path()
    display = object_to_inject.displayNode()

    if display is None:
        om = object_to_inject.createNode('object_merge')
        om.setParms({ 'objpath1': node_path, 'xformtype': 1 })    
        om.moveToGoodPosition()
        
        return om

    else:
        for ancestor in display.inputAncestors():
            if ancestor.type().name() == 'object_merge' and ancestor.evalParm('objpath1') == node_path:
                return ancestor

        om = object_to_inject.createNode('object_merge')
        om.setParms({ 'objpath1': node_path, 'xformtype': 1 })    
        om.moveToGoodPosition()

        return om

def ancestor_object(node):
    parent = node.parent()
    cat = parent.type().category()
    while parent is not None and (cat == _sop_category or cat == _obj_category):
        node = parent
        parent = parent.parent()
        cat = parent.type().category()
    return node

    
def merge_with_object(src_sop, src_obj, dst_sop, dst_obj, merge_node_type, merge_node_parms={}):
    with hou.RedrawBlock() as rb:
        src_nodes = (src_sop,) + src_sop.inputAncestors()
        
        m = dst_sop.createOutputNode(merge_node_type)
        new_nodes = hou.moveNodesTo(src_nodes, dst_obj)

        xform = src_obj.worldTransform() * dst_obj.worldTransform().inverted()

        t = xform.extractTranslates()
        r = xform.extractRotates()
        s = xform.extractScales()
        sh = xform.extractShears()

        x = new_nodes[0].createOutputNode("xform")
        x.parmTuple("t").set(t)
        x.parmTuple("r").set(r)
        x.parmTuple("s").set(s)
        x.parmTuple("shear").set(sh)

        m.setParms(merge_node_parms)
        m.setInput(1, x)
        m.setCurrent(True, True)
        m.setDisplayFlag(True)
        m.setRenderFlag(True)
        m.setHighlightFlag(True)

        src_obj.destroy()

    dst_obj.layoutChildren()
    return m


def catch_node_outputs(from_node, to_node):
    for output in from_node.outputs():
        output.setInput(output.inputs().index(from_node), to_node)
    for dot in from_node.parent().networkDots():
        if not len(dot.outputs()):
            dot.destroy()


def freeze(nodes):
    for pwd in nodes:
        if pwd.worldTransform() != hou.hmath.identityTransform():
            objecttoolutils.freeze((pwd,))
            pwd.displayNode().setCurrent(True, True)
    hou.ui.waitUntil(lambda: True)


def seltype_to_grouptype(typ):
    if typ == hou.geometryType.Primitives:
        return 0
    elif typ == hou.geometryType.Points:
        return 1
    elif typ == hou.geometryType.Edges:
        return 2
    elif typ == hou.geometryType.Vertices:
        return 3


def grouptype_to_seltype(value):
    if value == 0:
        return hou.geometryType.Primitives
    elif value == 1:
        return hou.geometryType.Points
    elif value == 2:
        return hou.geometryType.Edges
    else:
        return hou.geometryType.Vertices


def is_vdb(geo):
    return geo.prim(0).type() == hou.primType.VDB


def vdb_voxel_size(geo):
    return geo.prim(0).voxelSize()


def get_bound_positions_and_directions(scene_viewer, sop, points, prompts):
    with hou.undos.disabler():
        initial_sel_type = scene_viewer.pickGeometryType()
        
        bound = sop.createOutputNode("bound")
        bound.setParms({ "group": points, "grouptype": 3, "orientedbbox": True })
        geo = bound.geometry()
        bound.setCurrent(True, True)

        directions = []
        positions = []
        for i in range(len(prompts)):
            try:
                gs = scene_viewer.selectGeometry(prompts[i], geometry_types=(hou.geometryType.Primitives,),
                                                 quick_select = True, use_existing_selection=False, consume_selections=True)
            except hou.OperationInterrupted:
                scene_viewer.setPickGeometryType(initial_sel_type)
                bound.destroy()
                return None, None

            selections = gs.selections()
            if selections:
                face = selections[0].prims(geo)[0]
                position = face.positionAtInterior(0.5, 0.5)
                direction = face.normal()
                positions.append(position)
                directions.append(direction)
            else:
                scene_viewer.setPickGeometryType(initial_sel_type)
                bound.destroy()
                return None, None

        scene_viewer.setPickGeometryType(initial_sel_type)
        bound.destroy()
        return (positions, directions)