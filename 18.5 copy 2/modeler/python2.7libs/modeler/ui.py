import hou
import shiboken2
import PySide2.QtCore as qtc
import PySide2.QtGui as qtg
import PySide2.QtWidgets as qtw
from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import QFile
from PySide2.QtTest import QTest as qtest
import os
import sys
import nodegraphview
from hdefereval import executeDeferred
from functools import partial
import numpy
import time
import pickle
qt = qtc.Qt


modeler_path = os.getenv("MODELER_PATH")
settings_path = modeler_path + "/modeler/settings"
settings = qtc.QSettings("modeler_config")

is_linux = False
is_win = False
is_mac = False

if sys.platform.startswith("linux"):
    is_linux = True
elif sys.platform == "darwin":
    is_mac = True
else:
    is_win = True

MODELER_VERSION = "2020.5.9"
qt_app = qtw.QApplication.instance()
desktop_widget = qtw.QDesktopWidget()
desktop_screen_geo = desktop_widget.screenGeometry()
x_res = desktop_screen_geo.width()
y_res = desktop_screen_geo.height()


mini_icon_size = qtc.QSize(hou.ui.scaledSize(6), hou.ui.scaledSize(6))
mid_icon_size = qtc.QSize(hou.ui.scaledSize(16), hou.ui.scaledSize(16))
mid_button_size = qtc.QSize(hou.ui.scaledSize(32), hou.ui.scaledSize(32))


def display_shelf_tool_radial_menu(menu):
    global radial_menu_viewport

    scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    if scene_viewer is not None:
        if hou.ui.paneTabUnderCursor() != scene_viewer:
            widget = get_scene_viewer_mouse_widget()
            if widget is not None:
                pos = widget.mapToGlobal( widget.rect().center() )
                qtg.QCursor.setPos(pos)
        
        radial_menu_viewport = scene_viewer.curViewport()
        scene_viewer.displayRadialMenu(menu)


def key_is_modifier(key):
    return ( key in (qt.Key_Alt, qt.Key_Control, qt.Key_Shift, qt.Key_Meta) )


def get_scene_viewer_mouse_widget():
    global main_widget

    mouse_widget = None
    main_widget = hou.qt.mainWindow()
    for widget in main_widget.findChildren(qtw.QWidget, "RE_Window"):
        if widget.windowTitle() == "DM_ViewLayout":
            for l in widget.findChildren(qtw.QVBoxLayout):
                if l.count()==1:
                    w = l.itemAt(0).widget()
                    if w.objectName() == "RE_GLDrawable":
                        i = int(shiboken2.getCppPointer(w)[0])
                        mouse_widget = shiboken2.wrapInstance(i, qtw.QWidget)
                        return mouse_widget
    return mouse_widget


def get_scene_viewer_keyboard_widget():
    global main_widget

    keyboard_widget = None
    main_widget = hou.qt.mainWindow()
    main_widget_width = main_widget.width()
    main_widget_height = main_widget.height()
    for window in qt_app.allWindows():
        i = shiboken2.getCppPointer(window)[0]
        window = shiboken2.wrapInstance(int(i), qtg.QWindow)
        if window.objectName() == "RE_WindowWindow" and window.width() == main_widget_width and window.height() == main_widget_height:
            keyboard_widget = window
            break
    return keyboard_widget


def run_internal_command(cmd):
    commands_to_restore = []

    for conflict in hou.hotkeys.findConflicts(None, "Print"):
        hou.hotkeys.removeAssignment(conflict, "Print")
        commands_to_restore.append(conflict)

    hou.hotkeys.addAssignment(cmd, "Print")

    mw = hou.qt.mainWindow()
    qtest.keyPress(mw, qt.Key_Print, qt.NoModifier)
    hou.ui.waitUntil(lambda: True)
    qtest.keyRelease(mw, qt.Key_Print, qt.NoModifier)

    hou.hotkeys.removeAssignment(cmd, "Print")
    for cmd in commands_to_restore:
        hou.hotkeys.addAssignment(cmd, "Print")


def wireframe():
    executeDeferred(_wireframe)


def _wireframe():
    run_internal_command("h.pane.gview.toggle_wireshaded")


def show_handles(scene_viewer, value):
    for viewport in scene_viewer.viewports():
        viewport.settings().enableGuide(hou.viewportGuide.NodeHandles, value)


def show_current_geo(scene_viewer, value):
    for viewport in scene_viewer.viewports():
        viewport.settings().enableGuide(hou.viewportGuide.CurrentGeometry, value)


def inc_string(string):
    digits = "".join(c for c in string if c.isdigit())
    if digits:
        return string.split(digits)[0] + str(int(digits) + 1)
    else:
        return string + "1"


def home_selected():
    try:
        hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor).homeToSelection()
    except AttributeError:
        pass


def frame_items(items):
    try:
        nodegraphview.frameItems(hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor), items)
    except AttributeError:
        pass


def get_hvd(scene_viewer, absolute=False):
    hvd = scene_viewer.curViewport().viewTransform().extractRotationMatrix3().asTupleOfTuples()

    x = numpy.abs(hvd[0])
    x_max_id = x.argmax()
    x.fill(0.0)

    y = numpy.abs(hvd[1])
    y_max_id = y.argmax()
    y.fill(0.0)

    if absolute:
        x[x_max_id] = 1.0
        y[y_max_id] = 1.0
        return hou.Vector3(x), hou.Vector3(y), hou.Vector3(numpy.abs(numpy.cross(x, y)))
    else:
        x[x_max_id] = numpy.sign(hvd[0][x_max_id])
        y[y_max_id] = numpy.sign(hvd[1][y_max_id])
        return hou.Vector3(x), hou.Vector3(y), hou.Vector3(numpy.cross(x, y))


def transform_handle(node, origin, rotation, op="translate"):
    node_type = node.type().name()
    if node_type == "edit":
        handle_name = "Edit Manipulator"
    elif node_type == "xform":
        handle_name = "Transformer"
    elif node_type == "copyxform":
        handle_name = "Copy Transformer"
    elif node_type == "polyextrude::2.0":
        handle_name = "Polygon Extruder 2"
    else:
        return
    hou.hscript('omparm "{0}" {1} {2} "{3}(1) follow_selection(0) pivot({4} {5} {6}) orientation({7} {8} {9})"'.format(handle_name, node.name(), node.path(), op, origin[0], origin[1], origin[2], rotation[0], rotation[1], rotation[2]))
