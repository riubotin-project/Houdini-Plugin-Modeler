import hou
from modeler import ui, geo_utils


class StateTemplate(object):
    prompt = ""
    node = None

    def __init__(self, state_name, scene_viewer):
        self.allow_snapping = False

        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self.onResume = self.onEnter

        self._pre_snapping_mode = None
        
        self.last_mouse_move_x = self.last_mouse_move_y = None

    def get_geometry(self):
        return self.node.inputGeometry(0)

    def onGenerate(self, kwargs):
        self.onEnter(kwargs)

    def onEnter(self, kwargs):
        self.scene_viewer.setPromptMessage(self.prompt)
        self.node = self.node or kwargs["node"]
        
        # NODE CAN BE DESTROYED ON THE INTERRUPT EVENT
        try:
            self.geo = self.get_geometry()
        except hou.ObjectWasDeleted:
            self.scene_viewer.setCurrentState("select")
            return

        # STOP STATE. FOR EXAMPLE, AFTER DISCONNECTING IT
        if self.geo is None:
            self.scene_viewer.setCurrentState("select")
            return

        self.viewport = self.scene_viewer.curViewport()

        # OBJECT MATRICES
        if self.scene_viewer.isWorldSpaceLocal():
            self._xform = hou.hmath.identityTransform()
        else:
            self._xform = self.node.creator().worldTransform()
        
        self._xform_inverted = self._xform.inverted()
        self._xform_transposed = self._xform.transposed()
        self._xform_inverted_transposed = self._xform_inverted.transposed()
        
        # VIEWPORT MATRICES
        self._viewport_xform = self.viewport.viewTransform()
        self._viewport_xform_inverted = self._viewport_xform.inverted()
        self._viewport_xform_inverted_transposed = self._viewport_xform_inverted.transposed()

        # VIEWPORT PLANE DIRS
        self._hvd = ui.get_hvd(self.scene_viewer)
        self._local_view_right_dir = hou.Vector3(1.0, 0.0, 0.0) * self._viewport_xform_inverted_transposed * self._xform_transposed
        self._local_view_plane_dir = hou.Vector3(0.0, 0.0, 1.0) * self._viewport_xform_inverted_transposed * self._xform_transposed
        self._local_view_best_plane_dir = self._hvd[2] * self._xform_transposed

        # DEFAULT VECTOR PARMS MOVING IN VIEW PLANE
        self._current_viewport_plane_dir = self._local_view_plane_dir
        self._project_dir = None

        self.drag_scale = 1

        # TURN OFF SNAPPING THAT WAS NOT UNACTIVATED NORMALLY. PROBABLY WHEN RELESING DRAG NOT ON THE VIEWPORT
        if self._pre_snapping_mode is not None:
            self.scene_viewer.setSnappingMode(self._pre_snapping_mode)
            self._pre_snapping_mode = None

    def onExit(self, kwargs):
        with hou.undos.group("Modeler: Drag Pre Exit"):
            self.pre_exit()

        # TURN OFF SNAPPING THAT WAS NOT UNACTIVATED NORMALLY. PROBABLY AFTER VOLATILE DRAG JOB
        if self._pre_snapping_mode is not None:
            self.scene_viewer.setSnappingMode(self._pre_snapping_mode)
            self._pre_snapping_mode = None

    def pre_exit(self):
        pass

    def solve_snap(self, local_snap_pos):
        pass

    def drag_release(self):
        pass

    def get_wheel_parm(self, ctrl, shift):
        return None

    def onMouseWheelEvent(self, kwargs):
        device = kwargs["ui_event"].device()
        parm = self.get_wheel_parm(device.isCtrlKey(), device.isShiftKey())
        if parm is not None:
            value = parm.eval()
            if isinstance(value, int):
                value += (1 if device.mouseWheel() > 0 else -1)
            else:    
                value = value + (hou.hmath.sign(device.mouseWheel()) * value / 10.0) if value else 0.1
            parm.set(value)

    def onMouseEvent(self, kwargs):
        ui_event = kwargs["ui_event"]
        reason = ui_event.reason()

        # POINTER DRAG
        if reason == hou.uiEventReason.Active:
            
            # VECTOR (CAN BE SNAPPED)
            if self._drag_type == 3 and self.allow_snapping:
                snap_dict = ui_event.snappingRay()
                o = snap_dict["origin_point"]
                d = snap_dict["direction"]

                # SNAPPED
                if snap_dict["snapped"]:
                    snap_type = snap_dict["geo_type"]

                    # GEO POINT
                    if snap_type == hou.snappingPriority.GeoPoint:
                        try:
                            node = hou.nodeBySessionId( snap_dict["node_id"] )
                        except KeyError:
                            x, y = self.viewport.mapToScreen(o)
                            node = self.viewport.queryNodeAtPixel(int(x), int(y))
                            if node is None:
                                return

                        node_xform = geo_utils.ancestor_object(node).worldTransform()
                        global_snap_pos = node.geometry().point( snap_dict["point_index"] ).position() * node_xform

                    # MIDPOINT
                    elif snap_type == hou.snappingPriority.Midpoint:
                        try:
                            node = hou.nodeBySessionId( snap_dict["node_id"] )
                        except KeyError:
                            x, y = self.viewport.mapToScreen(o)
                            node = self.viewport.queryNodeAtPixel(int(x), int(y))
                            if node is None:
                                return
                        
                        node_xform = geo_utils.ancestor_object(node).worldTransform()
                        node_geo = node.geometry()
                        pos1 = node_geo.point( snap_dict["edge_point_index1"] ).position()
                        pos2 = node_geo.point( snap_dict["edge_point_index2"] ).position()
                        mid_pos = (pos1 + pos2) / 2.0
                        global_snap_pos = mid_pos * node_xform

                    # PRIM
                    elif snap_type == hou.snappingPriority.GeoPrim:
                        try:
                            node = hou.nodeBySessionId( snap_dict["node_id"] )
                        except KeyError:
                            x, y = self.viewport.mapToScreen(o)
                            node = self.viewport.queryNodeAtPixel(int(x), int(y))
                            if node is None:
                                return
                        
                        node_xform = geo_utils.ancestor_object(node).worldTransform()
                        node_geo = node.geometry()
                        tmp_vec = hou.Vector3()
                        node_snap_pos = hou.Vector3()
                        intersected = node_geo.intersect(o * node_xform.inverted(), d * node_xform.transposed(), node_snap_pos, tmp_vec, tmp_vec)
                        global_snap_pos = node_snap_pos * node_xform

                    # GRID POINT, GRID EDGE 
                    elif snap_type in (hou.snappingPriority.GridPoint, hou.snappingPriority.GridEdge):
                        global_snap_pos = snap_dict["grid_pos"]


                    # OTHER SNAPPING PRIORITY NOT SUPPORTED
                    else:
                        return

                    self.solve_snap(global_snap_pos * self._xform_inverted)

                # NOT SNAPPED
                else:
                    delta_vector = hou.hmath.intersectPlane(self._start_drag_pos,  self._current_viewport_plane_dir, *ui_event.ray()) - self._start_drag_pos
                    if self._project_dir is not None:
                        delta_vector = self._project_dir * delta_vector.dot(self._project_dir)
                    self._drag_parm.set( self._drag_parm_start_value + delta_vector )
            
            elif self._drag_type == 3:
                delta_vector = hou.hmath.intersectPlane(self._start_drag_pos,  self._current_viewport_plane_dir, *ui_event.ray()) - self._start_drag_pos
                if self._project_dir is not None:
                    delta_vector = self._project_dir * delta_vector.dot(self._project_dir)
                self._drag_parm.set( self._drag_parm_start_value + delta_vector )

            # FLOAT DISTANCE
            elif self._drag_type == 0:
                delta_vector = hou.hmath.intersectPlane(self._start_drag_pos,  hou.Vector3(0.0, 0.0, 1.0) * self._viewport_xform_inverted_transposed * self._xform_transposed, *ui_event.ray()) - self._start_drag_pos
                self._drag_parm.set( self._drag_parm_start_value + delta_vector.dot(hou.Vector3(1.0, 0.0, 0.0) * self._viewport_xform_inverted_transposed * self._xform_transposed) )

            # FLOAT
            elif self._drag_type == 1:
                self._drag_parm.set( self._drag_start_value + self._drag_scale * (ui_event.device().mouseX() - self._drag_start_x) )
                
            # INT
            elif self._drag_type == 2:
                value = int(self._drag_scale * (ui_event.device().mouseX() - self._drag_start_x)) + self._drag_start_value
                self._drag_parm.set(value)

        # POINTER PRESS
        elif reason == hou.uiEventReason.Start:
            device = ui_event.device()

            # PRE PRESS INTERSECTION WITH VIEWPORT
            self._start_drag_ray_origin, self._start_drag_ray_direction = ui_event.ray()

            hit_info = geo_utils.hit_info(self.scene_viewer, self._start_drag_ray_origin, self._start_drag_ray_direction, device.mouseX(), device.mouseY(), self.viewport, local=True)
            if hit_info is None:
                self._start_drag_pos = hou.hmath.intersectPlane(self.geo.boundingBox().center(), hou.Vector3(0.0, 0.0, 1.0) * self._viewport_xform_inverted_transposed * self._xform_transposed, self._start_drag_ray_origin, self._start_drag_ray_direction)
            else:
                self._start_drag_pos = hit_info["hit_pos"]
            
            self._drag_parm, self._drag_type = self.get_drag_parm(device.isCtrlKey(), device.isShiftKey())

            if self._drag_parm is not None:
                self.scene_viewer.beginStateUndo(self.__class__.__name__ + " Drag")

                # VECTOR
                if self._drag_type == 3:
                    self._drag_parm_start_value = hou.Vector3(self._drag_parm.eval())

                # DISTANCE
                elif self._drag_type == 0:
                    self._drag_parm_start_value = self._drag_parm.eval()

                # FLOAT
                elif self._drag_type == 1:
                    self._drag_scale = self.drag_scale * hou.ui.globalScaleFactor() * 0.01
                    self._drag_start_x = device.mouseX()
                    self._drag_start_value = self._drag_parm.eval()

                # INT
                else:
                    self._drag_scale = self.drag_scale * hou.ui.globalScaleFactor() * 0.05
                    self._drag_start_x = device.mouseX()
                    self._drag_start_value = self._drag_parm.eval()

        # POINTER RELEASE
        elif reason == hou.uiEventReason.Changed:
            if self._drag_parm is not None:
                self.scene_viewer.endStateUndo()

                self.drag_release()
                self.drag_scale = 1


###############################################################################
# NODE STATES


class QPrimitive(StateTemplate):
    prompt = "LMB: uniform scale; Ctrl+LMB: uniform resolution; Shift+LMB: crease; Wheel: uniform resolution."

    def get_geometry(self):
        return self.node.geometry()

    def get_drag_parm(self, ctrl, shift):
        if not ctrl and not shift:
            return self.node.parm("scale"), 0

        elif not ctrl and shift:
            return self.node.parm("crease"), 0

        elif ctrl and not shift:
            return self.node.parm("res"), 2
        
        elif ctrl and shift:
            return self.node.parm("type"), 2
        
        return None, None

def _QPrimitive():
    template = hou.ViewerStateTemplate("modeler::qprimitive", "QPrimitive", geo_utils._sop_category)
    template.bindFactory(QPrimitive)
    template.bindIcon("opdef:/Sop/modeler::qprimitive?IconSVG")
    return template


#------------------------------------------------------------------------------


class Extrude(StateTemplate):
    prompt = "LMB: offset; Ctrl+LMB: divisions; Shift+LMB: inset; Ctrl+Shift+LMB: immediate ramp offset."

    def get_drag_parm(self, ctrl, shift):
        if not ctrl and not shift:
            return self.node.parm("offset"), 0
        
        elif not ctrl and shift:
            return self.node.parm("inset"), 0
        
        elif ctrl and shift:
            return self.node.parm("thicknessramp2value"), 1
        
        elif ctrl and not shift:
            return self.node.parm("divisions"), 2

        return None, None

def _Extrude():
    template = hou.ViewerStateTemplate("modeler::extrude", "Modeler Extrude", geo_utils._sop_category)
    template.bindFactory(Extrude)
    template.bindIcon("opdef:/Sop/modeler::extrude?IconSVG")
    return template


#------------------------------------------------------------------------------


class ExtrudePoints(StateTemplate):
    prompt = "LMB: offset by view plane; Shift+LMB: horizontally; Ctrl+LMB: vertically; Ctrl+Shift+LMB: by closest view plane."

    def get_drag_parm(self, ctrl, shift):
        self.allow_snapping = True

        self._initial_offset = hou.Vector3(self.node.evalParmTuple("offset"))

        # VIEW
        if not ctrl and not shift:
            self._project_dir = None
            self._current_viewport_plane_dir = self._local_view_plane_dir

        # H
        elif not ctrl and shift:
            self._project_dir = self._hvd[0] * self._xform_transposed
            self._current_viewport_plane_dir = self._local_view_best_plane_dir
                    
        # V
        elif ctrl and not shift:
            self._project_dir = self._hvd[1] * self._xform_transposed
            self._current_viewport_plane_dir = self._local_view_best_plane_dir
        
        # BEST PLANE
        elif ctrl and shift:
            self._project_dir = None
            self._current_viewport_plane_dir = self._local_view_best_plane_dir

        else:
            return None, None

        return self.node.parmTuple("offset"), 3

    def solve_snap(self, local_snap_pos):
        if self._project_dir is not None:
            vec = self.node.geometry().pointBoundingBox(self.node.evalParm("group")).center() + self._initial_offset - local_snap_pos
            dot = vec.dot(self._project_dir)
            value = self._initial_offset - self._project_dir * dot
        else:
            pts_center = self.node.geometry().pointBoundingBox(self.node.evalParm("group")).center()
            value = local_snap_pos - pts_center

        self.node.parmTuple("offset").set(value)

def _ExtrudePoints():
    template = hou.ViewerStateTemplate("modeler::extrude_points", "Extrude Points", geo_utils._sop_category)
    template.bindFactory(ExtrudePoints)
    template.bindIcon("opdef:/Sop/modeler::extrude_points?IconSVG")
    return template


#------------------------------------------------------------------------------


class Thickness(Extrude):
    prompt = "LMB: thickness; Shift+LMB: offset; Ctrl+LMB: divisions; Ctrl+Shift+LMB: scale."

    def get_drag_parm(self, ctrl, shift):
        if not ctrl and not shift:
            return self.node.parm("thickness"), 0
        
        elif not ctrl and shift:
            return self.node.parm("offset"), 0
        
        elif ctrl and shift:
            return self.node.parm("scale"), 1
        
        elif ctrl and not shift:
            return self.node.parm("divisions"), 2

        return None, None

def _Thickness():
    template = hou.ViewerStateTemplate("modeler::thickness", "Thickness", geo_utils._sop_category)
    template.bindFactory(Thickness)
    template.bindIcon("opdef:/Sop/modeler::thickness?IconSVG")
    return template


#------------------------------------------------------------------------------


class Bevel(Extrude):
    prompt = "LMB: offset; Ctrl+LMB: divisions; Shift+LMB: ignore flat angle; Ctrl+Shift+LMB: immediate ramp offset."

    def get_drag_parm(self, ctrl, shift):
        if not ctrl and not shift:
            return self.node.parm("offset"), 0
        
        elif not ctrl and shift:
            if not self.node.evalParm("ignoreflatedges"):
                self.node.parm("ignoreflatedges").set(True)

            self.drag_scale = 10.0
            return self.node.parm("flatangle"), 1
        
        elif ctrl and shift:
            if not self.node.evalParm("doramp"):
                self.node.parm("doramp").set(True)
                
            if self.node.evalParm("filletshape") != 4:
                self.node.parm("filletshape").set(4)
            return self.node.parm("profilescale"), 1
        
        elif ctrl and not shift:
            return self.node.parm("divisions"), 2

        return None, None

def _Bevel():
    template = hou.ViewerStateTemplate("modeler::bevel", "Modeler Bevel", geo_utils._sop_category)
    template.bindFactory(Bevel)
    template.bindIcon("opdef:/Sop/modeler::bevel?IconSVG")
    return template


#------------------------------------------------------------------------------


class Bridge(StateTemplate):
    prompt = "LMB: magnitude; Ctrl+LMB: divisions; Shift+LMB: stiffness; Ctrl+Shift+LMB: shift connection."

    def get_drag_parm(self, ctrl, shift):
        if not ctrl and not shift:
            return self.node.parm("magnitude"), 1
        
        elif not ctrl and shift:
            return self.node.parm("stiffness"), 1
                
        elif ctrl and not shift:
            return self.node.parm("divisions"), 2

        elif ctrl and shift:
            return self.node.parm("pairingshift"), 2

        return None, None

def _Bridge():
    template = hou.ViewerStateTemplate("modeler::bridge", "Modeler Bridge", geo_utils._sop_category)
    template.bindFactory(Bridge)
    template.bindIcon("opdef:/Sop/modeler::bridge?IconSVG")
    return template


#------------------------------------------------------------------------------


class Array(StateTemplate):
    prompt = "LMB: array radius; Ctrl+LMB: count 1; Shift+LMB: count 2; Ctrl+Shift+LMB: scale instance. Wheel: count 1."

    def get_drag_parm(self, ctrl, shift):
        if not ctrl and not shift:
            return self.node.parm("rad"), 0
        
        elif not ctrl and shift:
            return self.node.parm("count2"), 2
        
        elif ctrl and not shift:
            return self.node.parm("count1"), 2
        
        elif ctrl and shift:
            return self.node.parm("scale"), 1

        return None, None

def _Array():
    template = hou.ViewerStateTemplate("modeler::array", "Array", geo_utils._sop_category)
    template.bindFactory(Array)
    template.bindIcon("opdef:/Sop/modeler::array?IconSVG")
    return template


#------------------------------------------------------------------------------


class Hose(StateTemplate):
    prompt = "LMB: radius; Shift+LMB: smooth; Ctrl+LMB: divisions; Ctrl+Shift+LMB: resample. Wheel: divisions."

    def get_drag_parm(self, ctrl, shift):
        if not ctrl and not shift:
            return self.node.parm("rad"), 0

        elif ctrl and not shift:
            return self.node.parm("divisions"), 2
        
        elif not ctrl and shift:
            return self.node.parm("smooth"), 1
        
        elif ctrl and shift:
            return self.node.parm("resample"), 0
        
        return None, None

def _Hose():
    template = hou.ViewerStateTemplate("modeler::hose", "Thickness", geo_utils._sop_category)
    template.bindFactory(Hose)
    template.bindIcon("opdef:/Sop/modeler::hose?IconSVG")
    return template


#------------------------------------------------------------------------------


class Relax(StateTemplate):
    prompt = "LMB: size; Ctrl+LMB: iterations; Wheel: iterations."

    def get_drag_parm(self, ctrl, shift):
        if not ctrl and not shift:
            return self.node.parm("size"), 1
        
        elif ctrl and not shift:
            return self.node.parm("iterations"), 2

        return None, None

def _Relax():
    template = hou.ViewerStateTemplate("modeler::relax", "Relax", geo_utils._sop_category)
    template.bindFactory(Relax)
    template.bindIcon("opdef:/Sop/modeler::relax?IconSVG")
    return template


#------------------------------------------------------------------------------


class FalloffTransform(StateTemplate):
    prompt = "LMB: move nearest limit point; Shift+LMB: horizontally; Ctrl+LMB: vertically; Ctrl+Shift+LMB: by closest view plane."

    def get_drag_parm(self, ctrl, shift):
        # VIEW
        if not ctrl and not shift:
            self._project_dir = None
            self._current_viewport_plane_dir = self._local_view_plane_dir

        # H
        elif not ctrl and shift:
            self._project_dir = self._hvd[0] * self._xform_transposed
            self._current_viewport_plane_dir = self._local_view_best_plane_dir
                    
        # V
        elif ctrl and not shift:
            self._project_dir = self._hvd[1] * self._xform_transposed
            self._current_viewport_plane_dir = self._local_view_best_plane_dir
        
        # BEST PLANE
        elif ctrl and shift:
            self._project_dir = None
            self._current_viewport_plane_dir = self._local_view_best_plane_dir
        
        else:
            return None, None

        pt0 = hou.Vector3( self.node.evalParmTuple("pt0") )
        pt1 = hou.Vector3( self.node.evalParmTuple("pt1") )
        vec = pt1 - pt0
    
        # SAME POSITIONS -> DRAW
        if vec.length() == 0.0:
            self.allow_snapping = False
            self.node.parmTuple("pt0").set(self._start_drag_pos)
            self.node.parmTuple("pt1").set(self._start_drag_pos)
            return self.node.parmTuple("pt1"), 3

        # DIFFERENT POSITIONS -> DRAG NEAREST POINT
        else:
            self.allow_snapping = True
            
            if self._start_drag_pos.distanceTo(pt0) < self._start_drag_pos.distanceTo(pt1):
                self._snap_center = pt0
                self._snap_parm = self.node.parmTuple("pt0")
                return self._snap_parm, 3
            else:
                self._snap_center = pt1
                self._snap_parm = self.node.parmTuple("pt1")
                return self._snap_parm, 3

    def solve_snap(self, local_snap_pos):
        if self._project_dir is not None:
            v = local_snap_pos - self._snap_center
            dot = v.dot(self._project_dir)
            value = self._snap_center + self._project_dir * dot
        else:
            value = local_snap_pos

        self._snap_parm.set(value)

def _FalloffTransform():
    template = hou.ViewerStateTemplate("modeler::falloff_xform", "Falloff Transform", geo_utils._sop_category)
    template.bindFactory(FalloffTransform)
    template.bindIcon("opdef:/Sop/modeler::falloff_xform?IconSVG")
    return template


#------------------------------------------------------------------------------


class InsertMesh(StateTemplate):
    prompt = "LMB: scale; Shift+LMB: offset; Ctrl+LMB: subdivide inserted mesh; Ctrl+Shift+LMB: rotate. Wheel: subdivide inserted mesh."

    def get_drag_parm(self, ctrl, shift):
        if self.node.evalParm("per_poly"):
            with hou.undos.disabler():
                self.node.parm("do_setup").set(True)

        if not ctrl and not shift:
            return self.node.parm("scale"), 1

        elif ctrl and not shift:
            return self.node.parm("subdivide_inserted"), 2
        
        elif not ctrl and shift:
            return self.node.parm("offset"), 0
        
        elif ctrl and shift:
            return self.node.parm("rotate"), 2

        return None, None

    def drag_release(self):
        if self.node.evalParm("do_setup"):
            with hou.undos.disabler():
                self.node.parm("do_setup").set(False)

def _InsertMesh():
    template = hou.ViewerStateTemplate("modeler::insert_mesh", "Insert Mesh", geo_utils._sop_category)
    template.bindFactory(InsertMesh)
    template.bindIcon("opdef:/Sop/modeler::insert_mesh?IconSVG")
    return template


#------------------------------------------------------------------------------


class SoftBoolean(StateTemplate):
    prompt = "LMB: fillet radius; Shift+LMB: fillet flatness; Ctrl+LMB: profile quility; Ctrl+Shift+LMB: fillet seam width. Wheel: profile quility."

    def get_drag_parm(self, ctrl, shift):
        if not ctrl and not shift:
            self.pre_rt_mode = self.node.evalParm("mode")
            with hou.undos.disabler():
                self.node.parm("mode").set(2)
            return self.node.parm("fillet_radius"), 0

        elif ctrl and not shift:
            self.pre_rt_mode = None
            return self.node.parm("fillet_profile_quality"), 2
        
        elif not ctrl and shift:
            self.pre_rt_mode = None
            return self.node.parm("fillet_flatness"), 1
        
        elif ctrl and shift:
            self.pre_rt_mode = None
            return self.node.parm("seam_width_mult"), 1
        

        return None, None

    def drag_release(self):
        if self.pre_rt_mode is not None:
            with hou.undos.disabler():
                self.node.parm("mode").set(self.pre_rt_mode)
            self.pre_rt_mode = None

def _SoftBoolean():
    template = hou.ViewerStateTemplate("modeler::soft_boolean", "Soft Boolean", geo_utils._sop_category)
    template.bindFactory(SoftBoolean)
    template.bindIcon("opdef:/Sop/modeler::soft_boolean?IconSVG")
    return template


###############################################################################
# GRAB NODELESS STATES BASED ON THE EDIT SOP


class Grab(StateTemplate):
    _new_edit = False
    prompt = "LMB: grab by view plane; Shift+LMB: horizontally; Ctrl+LMB: vertically; Ctrl+Shift+LMB: by cosest view plane."


    def get_geometry(self):
        return self.node.geometry()

    def get_drag_parm(self, ctrl, shift):
        self.allow_snapping = True
        
        # VIEW
        if not ctrl and not shift:
            self._project_dir = None
            self._current_viewport_plane_dir = self._local_view_plane_dir

        # H
        elif not ctrl and shift:
            self._project_dir = self._hvd[0] * self._xform_transposed
            self._current_viewport_plane_dir = self._local_view_best_plane_dir
                    
        # V
        elif ctrl and not shift:
            self._project_dir = self._hvd[1] * self._xform_transposed
            self._current_viewport_plane_dir = self._local_view_best_plane_dir
        
        # BEST PLANE
        else:
            self._project_dir = None
            self._current_viewport_plane_dir = self._local_view_best_plane_dir

        return self.node.parmTuple("t"), 3

    def solve_snap(self, local_snap_pos):
        if self._project_dir is None:
            value = local_snap_pos - hou.Vector3(self.node.evalParmTuple("p"))
        else:
            value = local_snap_pos - hou.Vector3(self.node.evalParmTuple("p"))
            dot = value.dot(self._project_dir)
            value = self._project_dir * dot

        self.node.parmTuple("t").set(value)

    def pre_exit(self):
        try:
            self.node.cookCount()
        except hou.ObjectWasDeleted:
            return

        if self.node.evalParm("slideonsurface"):
            self.node.parm("apply").pressButton()
            self.node.parm("slideonsurface").set(False)
            self.node.parm("switcher1").set(0)
        
        if self.node.cookCount() < 3:
            inputs = self.node.inputs()
            self.node.destroy()
            inputs[0].setCurrent(True, True)


class Slide(Grab):
    prompt = "LMB: slide."

    def get_drag_parm(self, ctrl, shift):
        return self.node.parmTuple("t"), 3


class Peak(Grab):
    prompt = "LMB: peak."

    def get_drag_parm(self, ctrl, shift):
        return self.node.parm("dist"), 0


def register_grab():
    template = hou.ViewerStateTemplate("modeler::grab", "Grab", geo_utils._sop_category)
    template.bindFactory(Grab)
    hou.ui.registerViewerState(template)

def register_slide():
    template = hou.ViewerStateTemplate("modeler::slide", "Slide", geo_utils._sop_category)
    template.bindFactory(Slide)
    hou.ui.registerViewerState(template)

def register_peak():
    template = hou.ViewerStateTemplate("modeler::peak", "Peak", geo_utils._sop_category)
    template.bindFactory(Peak)
    hou.ui.registerViewerState(template)


register_grab()
register_slide()
register_peak()


###############################################################################
# PUSH NODELESS STATE BASED ON THE EDIT SOP


def Push(mode, from_menu_action=False):
    # global _smooth_opacity

    sop = geo_utils.get_sop(mode.scene_viewer)
    if sop is not None:
        state = mode.scene_viewer.currentState()

        with hou.RedrawBlock() as rb:
            # UV BRUSH EDITING
            if mode.scene_viewer.curViewport().type() == hou.geometryViewportType.UV:
                if state != "uvbrush":
                    with hou.undos.group("Modeler: Push UVs"):
                        if sop.type().name() == "uvbrush":
                            sop.parm("flood").pressButton()
                            sop.parm("group").set("")
                            mode.scene_viewer.enterCurrentNodeState()
                        else:
                            sop = sop.createOutputNode("uvbrush")
                            sop.setCurrent(True, True)
                            sop.setDisplayFlag(True)
                            sop.setRenderFlag(True)
                            mode.scene_viewer.enterCurrentNodeState()

                return True
            
            else:
                try:
                    PushStateTemplate.highres_sop = hou.node("/obj/__topo_highres__").displayNode()
                except:
                    PushStateTemplate.highres_sop = None
                
                with hou.undos.group("Modeler: Push State"):
                    # sop = mode.scene_viewer.currentNode()
                    
                    # EXISTING EDIT SOP
                    if sop.type().name() == "edit":
                        PushStateTemplate.new_edit = False
                        sop.parm("apply").pressButton()

                        if sop.evalParm("modeswitcher1"):
                        #     node.removeAllEventCallbacks()
                            rad = sop.evalParm("sculptrad")
                        else:
                            rad = geo_utils.global_brush_radius
                        
                        sop.setParms({ "grouptype": 3, "slideonsurface": False, "switcher1": 0, "modeswitcher1": 0, "rad": geo_utils.global_brush_radius, "distmetric": PushStateTemplate.initial_distmetric })
                    
                    # NEEDS NEW EDIT SOP
                    else:
                        PushStateTemplate.new_edit = True
                        sop = sop.createOutputNode("edit")
                        sop.setParms({ "grouptype": 3, "rad": geo_utils.global_brush_radius, "distmetric": PushStateTemplate.initial_distmetric })


                    # NON TOPO
                    if PushStateTemplate.highres_sop is None:
                        PushStateTemplate.ray_sop = None
                        display = sop

                    # TOPO -> CREATE RAY SOP AND CONNECT TOPO NODE TO IT
                    else:
                        PushStateTemplate.ray_sop = sop.createOutputNode("modeler::project")
                        om = geo_utils.inject_ref_objectmerge(PushStateTemplate.highres_sop, sop.parent())
                        PushStateTemplate.ray_sop.setInput(1, om)
                        display = PushStateTemplate.ray_sop


                    display.setCurrent(True, True)
                    display.setHighlightFlag(False)
                    display.setRenderFlag(True)
                    display.setDisplayFlag(True)

                    hou.ui.waitUntil(lambda: True)


                    PushStateTemplate.sop = sop
                    PushStateTemplate.geo = mode.scene_viewer.pwd().displayNode().geometry()
                    PushStateTemplate.dirt = False
                    PushStateTemplate.xform = PushStateTemplate.sop.creator().worldTransform()
                    PushStateTemplate.xform_inverted = PushStateTemplate.xform.inverted()
                    PushStateTemplate.xform_transposed = PushStateTemplate.xform.transposed()

                    PushStateTemplate.mode = mode
                    
                    mode.block_mouse_events(True)
                    geo_utils.setup_edit_sop_for_symmetry(sop)
                    mode.scene_viewer.setCurrentState("modeler::push")
                    
                    ui.qtg.QCursor.setPos(ui.qtg.QCursor.pos() - ui.qtc.QPoint(0, 1))

    return True


class PushStateTemplate(object):
    _hit_point = _hit_point_string = _hit_edge = _hit_edge_string = _hit_prim = _hit_prim_string = None

    initial_distmetric = 4
    last_mouse_move_x = _last_mouse_move_y = None

    # CREATE AND STORE DRAWABLE GEOMETRY OBJECTS
    radius_drawable_geo = hou.Geometry()
    circle = geo_utils._sop_category.nodeVerb("circle")
    circle.setParms({ "type": 2 })
    circle.execute(radius_drawable_geo, [])
    del circle

    def show_prompt_message(self):
        self.scene_viewer.setPromptMessage("LMB: move; Ctrl+LMB: move one point; Shift+LMB: change radius; Ctrl+Shift+LMB: slide loop; MMB: peak; Shift+MMB: scale. For smoothing run the Smooth Brush tool.")

    def __init__(self, scene_viewer, state_name):
        self.scene_viewer = scene_viewer

        # CREATE DRAWABLES
        self.radius_drawable = hou.SimpleDrawable(self.scene_viewer, self.radius_drawable_geo, "mb_radius_circle")
        self.radius_drawable.setWireframeColor(hou.Color(0,0,0))
        self.radius_drawable.setDisplayMode(hou.drawableDisplayMode.WireframeMode)

        # ENABLE AND SHOW DRAWABLES
        self.radius_drawable.enable(True)
        self.radius_drawable.show(True)

        # NULL DEFAULT MODE
        self.transform_mode = 0

    def is_edit_sop_fresh(self):
        return not self.dirt and self.new_edit

    def onExit(self, kwargs):
        try:
            if self.is_edit_sop_fresh():
                self.sop.destroy()
        
        except hou.ObjectWasDeleted:
            pass

        self.radius_drawable.enable(False)
        self.mode.block_mouse_events(False)

    def onGenerate(self, kwargs):
        self.viewport = self.scene_viewer.curViewport()
        ui.executeDeferred(self.show_prompt_message)

    def onInterrupt(self, kwargs):
        self.radius_drawable.show(False)
        self.scene_viewer.clearPromptMessage()

        self.mode.block_mouse_events(False)
        interrupted_on_viewer = self.mode.mouse_widget.rect().contains( self.mode.mouse_widget.mapFromGlobal(ui.qtg.QCursor.pos()) )
        if not interrupted_on_viewer:
            self.mode.block_keyboard_events(True)

    def onResume(self, kwargs):
        self.viewport = self.scene_viewer.curViewport()
        self.mode.block_mouse_events(True)
        self.mode.block_keyboard_events(False)
        ui.executeDeferred(self.show_prompt_message)

    def onMouseEvent(self, kwargs):
        event = kwargs["ui_event"]
        reason = event.reason()

        # MOUSE DRAG
        # MODE: 0 - OFF, 1 - MOVE (SLIDE), 2 - SCALE, 3 - PEAK, 4 - CHANGE SOFT RADIUS
        if reason == hou.uiEventReason.Active:
            # MOVE
            if self.transform_mode == 1:
                o, d = event.ray()
                intersection = hou.hmath.intersectPlane(self._start_intersection, self._view_normal_local, o, d)

                if self._is_sym:
                    intersection = hou.hmath.intersectPlane(self._start_intersection, self._sym_dir, intersection, self._sym_dir)
            
                self.sop.parmTuple("t").set(intersection - self._start_intersection)

            # SCALE
            elif self.transform_mode == 2:
                o, d = event.ray()
                intersection = hou.hmath.intersectPlane(self._start_intersection, self._view_normal_local, o, d)

                if self._is_sym:
                    intersection = hou.hmath.intersectPlane(self._start_intersection, self._sym_dir, intersection, self._sym_dir)

                v = intersection - self._start_intersection
                scale = 1 + v.dot(self._view_right_local) * 4.0
                self.sop.parmTuple("s").set((scale, scale, scale))

            # PEAK
            elif self.transform_mode == 3:
                o, d = event.ray()
                intersection = hou.hmath.intersectPlane(self._start_intersection, self._view_normal_local, o, d)
                self.sop.parmTuple("t").set(self._peak_normal * (intersection - self._start_intersection).dot(self._view_right_local))

            # RADIUS
            elif self.transform_mode == 4:
                o, d = event.ray()
                intersection = hou.hmath.intersectPlane(self._start_intersection, self._view_normal_local, o, d)
                offset = intersection - self._start_intersection
                geo_utils.global_brush_radius = max(self._pre_radius + offset.dot(self._view_right_local), 0.0001)
                self._update_radius(force_radius = geo_utils.global_brush_radius)


        # MOUSE PRESS
        elif reason == hou.uiEventReason.Start and self._hit_point is not None:
            self._press_device = event.device()

            is_ctrl = self._press_device.isCtrlKey()
            is_shift = self._press_device.isShiftKey()

            # LMB
            if self._press_device.isLeftButton() and self._hit_point is not None:
                # MOVE
                if not is_ctrl and not is_shift:
                    self.scene_viewer.beginStateUndo("Modeler: Push Drag")
                    self.sop.parm("group").set(self._hit_point_string)
                    self.radius_drawable.show(False)
                    self._move_one_point_initial_radius = None
                    self.transform_mode = 1

                # CTRL -> MOVE ONE POINT
                elif is_ctrl and not is_shift:
                    self.scene_viewer.beginStateUndo("Modeler: Push Drag")
                    self._move_one_point_initial_radius = self.sop.evalParm("rad")
                    self.sop.setParms({ "group": self._hit_point_string, "rad": 0.0 })
                    self.radius_drawable.show(False)
                    self.transform_mode = 1

                # CTRL+SHIFT -> SLIDE EDGE LOOP
                elif is_ctrl and is_shift:
                    loop = self.geo.edgeLoop((self._hit_edge, self._hit_edge), hou.componentLoopType.Extended, True, False, False)
                    edges = " ".join([edge.edgeId() for edge in loop if edge is not None])
                    self.scene_viewer.beginStateUndo("Push: Slide Edge Loop")
                    self.sop.setParms({ "grouptype": 2, "group": edges, "slideonsurface": True })
                    self.sop.parmTuple("p").set(self._hit_pos)
                    self.radius_drawable.show(False)
                    self._move_one_point_initial_radius = None
                    self.transform_mode = 1

                # SHIFT -> CHANGE RADIUS
                elif not is_ctrl and is_shift:
                    self._peak_normal = self._view_normal_local
                    self._pre_radius = self.sop.parm("rad").eval()
                    self.transform_mode = 4

            # MMB
            elif self._press_device.isMiddleButton() and self._hit_point is not None:
                self.transform_mode = 0
                self._move_one_point_initial_radius = None

                # PEAK
                if not is_ctrl and not is_shift:
                    self.scene_viewer.beginStateUndo("Push: Peak")
                    self.sop.parm("group").set(self._hit_point_string)
                    self.radius_drawable.show(False)
                    self.transform_mode = 3

                # SHIFT -> SCALE
                elif not is_ctrl and is_shift:
                    self.scene_viewer.beginStateUndo("Modeler: Push Drag")
                    self.sop.parm("group").set(self._hit_point_string)
                    self.sop.parmTuple("p").set(self._hit_pos)
                    self.radius_drawable.show(False)
                    self.transform_mode = 2


        # MOUSE RELEASE
        elif reason == hou.uiEventReason.Changed:
            # FINISH RADIUS
            if self.transform_mode == 4:
                self.sop.parm("rad").set(geo_utils.global_brush_radius)

            # TRANSFORM OPERATIONS
            elif self.transform_mode in (1, 2, 3):
                self.sop.parm("apply").pressButton()
                self.sop.setParms({ "grouptype": 3, "switcher1": 0, "slideonsurface": False })

                if self._move_one_point_initial_radius is not None:
                    self.sop.parm("rad").set(self._move_one_point_initial_radius)

                self.scene_viewer.endStateUndo()
                self.dirt = True

            self.transform_mode = 0

        # MOUSE MOVE
        elif reason == hou.uiEventReason.Located:
            event_value = event.value()
            x = event_value[0]
            y = event_value[1]

            # CALCULATE ONLY ON MOUSE MOVE. MOUSE PRESS ALSO EMIT LOCATED EVENT.
            if x != self.last_mouse_move_x or y != self._last_mouse_move_y:   
                # GET CURRENT VIEWPORT AND IT'S NORMAL 
                xform_inverted_transposed = self.viewport.viewTransform().inverted().transposed()
                self._view_normal = hou.Vector3(0.0, 0.0, 1.0) * xform_inverted_transposed
                self._view_normal_local = self._view_normal * self.xform_transposed
                self._view_right = hou.Vector3(1.0, 0.0, 0.0) * xform_inverted_transposed 
                self._view_right_local = self._view_right * self.xform_transposed

                self._hit_point = self._hit_point_string = self._hit_edge = self._hit_edge_string = self._hit_prim = self._hit_prim_string = None
                
                self.last_mouse_move_x = x
                self._last_mouse_move_y = y
                
                self._cursor_origin, self._cursor_dir = event.ray()
                
                normal = hou.Vector3()
                uvw = hou.Vector3()
                self._start_intersection = hou.Vector3()
                intersected = self.geo.intersect(self._cursor_origin, self._cursor_dir, self._start_intersection, normal, uvw)

                if intersected > -1:
                    self._hit_pos = self._start_intersection
                    self._hit_prim = self.geo.prim(intersected)
                    prim_points = self._hit_prim.points()

                    points_count = len(prim_points)
                    
                    # FIND NEAREST POINT
                    d = 999999.0
                    nearest_id = -1
                    for i in range(points_count):
                        pos = prim_points[i].position()
                        d1 = self._start_intersection.distanceTo(pos)
                        if d1 < d:
                            d = d1
                            nearest_id = i

                    self._hit_point = prim_points[nearest_id]

                    last_id = points_count - 1
                    
                    if nearest_id == 0:
                        nb1 = last_id
                        nb2 = 1
                    elif nearest_id == last_id:
                        nb1 = nearest_id - 1
                        nb2 = 0
                    else:
                        nb1 = nearest_id - 1
                        nb2 = nearest_id + 1

                    self._hit_prim_string = str(intersected)
                    self._hit_point_pos = self._hit_point.position()
                    self._hit_point_string = str(self._hit_point.number())

                    # FIND HIT EDGE ON CLOSED FACE
                    if self._hit_prim.isClosed():
                        nb1 = prim_points[nb1]
                        nb2 = prim_points[nb2]
                        nb1_pos = nb1.position()
                        nb2_pos = nb2.position()
                        d1 = self._start_intersection.distanceToSegment(self._hit_point_pos, nb1_pos)
                        d2 = self._start_intersection.distanceToSegment(self._hit_point_pos, nb2_pos)
                        if d1 < d2:
                            self._hit_edge = self.geo.findEdge(self._hit_point, nb1)
                            self._hit_edge_next_point_pos = nb1_pos
                        else:
                            self._hit_edge = self.geo.findEdge(self._hit_point, nb2)
                            self._hit_edge_next_point_pos = nb2_pos

                        self._hit_edge_string = self._hit_edge.edgeId()

                    self._peak_normal = self.geo.pointNormals((self._hit_point,))[0]

                    # SYMMETRY ACTIVATED
                    if self.sop.evalParm("doreflect"):
                        sym_origin = hou.Vector3(self.sop.evalParmTuple("symorig"))
                        self._sym_dir = hou.Vector3(self.sop.evalParmTuple("symaxis"))
                        
                        i = hou.hmath.intersectPlane(sym_origin, self._sym_dir, self._hit_point_pos, -self._sym_dir)
                        d = i.distanceTo(self._hit_point_pos)

                        dot = self._view_normal_local.dot(self._sym_dir)

                        # ACTIVATE SYM PROJECT IN SOME CASES
                        if d == 0 or ( dot > 0.8 and (d < self.sop.evalParm("rad")) ):
                            self._is_sym =  True
                        else:
                            self._is_sym =  False

                    # SYMMETRY NOT ACTIVATED
                    else:
                        self._is_sym = False

                else:
                    self._hit_point = None

                # REDRAW RADIUS DRAWABLE
                self._update_radius()

    def onMouseWheelEvent(self, kwargs):
        if self._hit_point is not None:
            event = kwargs["ui_event"]
            device = event.device()
            delta = device.mouseWheel()
            
            with hou.undos.disabler():
                is_ctrl = device.isCtrlKey()
                is_shift = device.isShiftKey()

                # CHANGE RADIUS
                if not is_ctrl and not is_shift:
                    rad = self.sop.evalParm("rad")
                    geo_utils.global_brush_radius = rad + hou.hmath.sign(delta) * rad / 10.0
                    self.sop.parm("rad").set(geo_utils.global_brush_radius)
                    self._update_radius()

    def _update_radius(self, force_radius=None):
        if self._hit_point is not None:
            # RADIUS
            rad = force_radius or self.sop.parm("rad").eval()
            
            viewport_rot_xform = hou.Matrix4(self.viewport.viewTransform().extractRotationMatrix3())
            
            # RADIUS
            if self.scene_viewer.isWorldSpaceLocal():
                x, y = self.viewport.mapToScreen(self._start_intersection + self._view_right * rad)
                cpos = (self._cursor_origin + self._cursor_dir * 0.01)
                rot = hou.Vector3(0, 0, 1).matrixToRotateTo(self._peak_normal)
            else:
                x, y = self.viewport.mapToScreen(self._start_intersection * self.xform + self._view_right * rad)
                cpos = (self._cursor_origin * self.xform + self._cursor_dir * self.xform_inverted.transposed() * 0.01)
                rot = hou.Vector3(0, 0, 1).matrixToRotateTo(self._peak_normal * self.xform_inverted.transposed())
        
            d_, o_ = self.viewport.mapToWorld(x, y)
            scale = cpos.distanceTo(o_ + d_ * 0.01)
            xform = hou.hmath.identityTransform() * rot * viewport_rot_xform.inverted() * hou.hmath.buildScale(scale, scale, 0.0001) * viewport_rot_xform * hou.hmath.buildTranslate(cpos)
            
            self.radius_drawable.setTransform(xform)
            self.radius_drawable.show(True)

        else:
            self.radius_drawable.show(False)

        self.viewport.draw()

    def onMenuAction(self, kwargs):
        item = kwargs["menu_item"]
        if item == "toggle_connectivity":
            if self.__class__.initial_distmetric == 4:
                self.__class__.initial_distmetric = 2
            else:
                self.__class__.initial_distmetric = 4

            self.sop.parm("distmetric").set(self.__class__.initial_distmetric)


def register_push_state():
    template = hou.ViewerStateTemplate("modeler::push", "Push", hou.sopNodeTypeCategory())
    template.bindFactory(PushStateTemplate)
    template.bindIcon("opdef:/Sop/modeler::soft_boolean?mb_state_icon.svg")
    
    menu = hou.ViewerStateMenu("mb_menu", "")
    menu.addActionItem("toggle_connectivity", "Toggle Connectivity")
    template.bindMenu(menu)

    hou.ui.registerViewerState(template)


register_push_state()