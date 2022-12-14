import hou
from modeler import ui, geo_utils, tools
from modeler.default_keyboard_hotkeys import default_hotkeys


keyboard_file_path = hou.expandString("$HOUDINI_USER_PREF_DIR") + "/m_keyboard_hotkeys.pref"
mouse_file_path = hou.expandString("$HOUDINI_USER_PREF_DIR") + "/m_mouse_hotkeys.pref"


#########################################################################################
# MODELER UI VALUES


LAUNCHER_FONT_SIZE = ui.x_res / 150
LAUNCHER_CATEGORY_FONT_SIZE = ui.x_res / 120
LAUNCHER_STATUS_FONT_SIZE = ui.x_res / 100
LAUNCHER_CATEGORY_LABEL_HEIGHT = ui.x_res / 100
LAUNCHER_TOOL_HEIGHT = ui.y_res / 50
LAUNCHER_SEPARATOR_HEIGHT = ui.y_res / 500
LAUNCHER_COLUMN_SPACING = ui.x_res / 20
LAUNCHER_MARGIN = ui.x_res / 100
LAUNCHER_OPACITY = 0.9


#########################################################################################
# MOUSE INTERNAL VARIABLES AND DEFAULT HOTKEYS DICTS (STANDARD, PRO)


LMB = int(ui.qt.LeftButton)
MMB = int(ui.qt.MiddleButton)
RMB = int(ui.qt.RightButton)
X1MB = int(ui.qt.MouseButton.XButton1)
X2MB = int(ui.qt.MouseButton.XButton2)
ALT = int(ui.qt.AltModifier)
CTRL = int(ui.qt.ControlModifier)
SHIFT = int(ui.qt.ShiftModifier)
NOMOD = 0
WHEEL_UP = 123456789
WHEEL_DOWN = -123456789


MOUSE_HOTKEYS_LABELS = [
"LMB", "LMB + Ctrl", "LMB + Shift", "LMB + Ctrl + Shift",
"MMB", "MMB + Ctrl", "MMB + Shift", "MMB + Ctrl + Shift",
"RMB", "RMB + Ctrl", "RMB + Shift", "RMB + Ctrl + Shift",
"X1", "X1 + Ctrl", "X1 + Shift", "X1 + Ctrl + Shift",
"X2", "X2 + Ctrl", "X2 + Shift", "X2 + Ctrl + Shift",
"Wheel Up", "Wheel Up + Ctrl", "Wheel Up + Shift", "Wheel Up + Ctrl + Shift",
"Wheel Down", "Wheel Down + Ctrl", "Wheel Down + Shift", "Wheel Down + Ctrl + Shift"
]


MOUSE_HOTKEYS_ACTIONS = [
LMB, LMB + CTRL, LMB + SHIFT, LMB + CTRL + SHIFT,
MMB, MMB + CTRL, MMB + SHIFT, MMB + CTRL + SHIFT,
RMB, RMB + CTRL, RMB + SHIFT, RMB + CTRL + SHIFT,
X1MB, X1MB + CTRL, X1MB + SHIFT, X1MB + CTRL + SHIFT,
X2MB, X2MB + CTRL, X2MB + SHIFT, X2MB + CTRL + SHIFT,
WHEEL_UP, WHEEL_UP + CTRL, WHEEL_UP + SHIFT, WHEEL_UP + CTRL + SHIFT,
WHEEL_DOWN, WHEEL_DOWN + CTRL, WHEEL_DOWN + SHIFT, WHEEL_DOWN + CTRL + SHIFT,
]


###############################################################################


default_mouse_hotkeys = {

LMB + NOMOD : "",
LMB + CTRL : "",
LMB + SHIFT : "",
LMB + CTRL + SHIFT : "",

MMB + NOMOD : "Grab",
MMB + CTRL : "GrabVertical",
MMB + SHIFT : "GrabHorizontal",
MMB + CTRL + SHIFT : "GrabBestPlane",

RMB + NOMOD : "",
RMB + CTRL : "",
RMB + SHIFT : "",
RMB + CTRL + SHIFT : "",

X1MB + NOMOD : "",
X1MB + CTRL : "",
X1MB + SHIFT : "",
X1MB + CTRL + SHIFT : "",

X2MB + NOMOD : "",
X2MB + CTRL : "",
X2MB + SHIFT : "",
X2MB + CTRL + SHIFT : "",

WHEEL_UP + NOMOD : "WheelUp",
WHEEL_UP + CTRL : "",
WHEEL_UP + SHIFT : "",
WHEEL_UP + CTRL + SHIFT : "",

WHEEL_DOWN + NOMOD : "WheelDown",
WHEEL_DOWN + CTRL : "",
WHEEL_DOWN + SHIFT : "",
WHEEL_DOWN + CTRL + SHIFT : "",

}


###############################################################################


default_mouse_hotkeys_pro = {

LMB + NOMOD : "Grab",
LMB + CTRL : "GrabVertical",
LMB + SHIFT : "GrabHorizontal",
LMB + CTRL + SHIFT : "GrabBestPlane",

MMB + NOMOD : "SelectThroughReplace",
MMB + CTRL : "SelectThroughRemove",
MMB + SHIFT : "SelectThroughAdd",
MMB + CTRL + SHIFT : "MiddleButtonDrag",

RMB + NOMOD : "SelectReplace",
RMB + CTRL : "SelectRemove",
RMB + SHIFT : "SelectAdd",
RMB + CTRL + SHIFT : "RightButtonDrag",

X1MB + NOMOD : "",
X1MB + CTRL : "",
X1MB + SHIFT : "",
X1MB + CTRL + SHIFT : "",

X2MB + NOMOD : "",
X2MB + CTRL : "",
X2MB + SHIFT : "",
X2MB + CTRL + SHIFT : "",

WHEEL_UP + NOMOD : "WheelUp",
WHEEL_UP + CTRL : "",
WHEEL_UP + SHIFT : "",
WHEEL_UP + CTRL + SHIFT : "",

WHEEL_DOWN + NOMOD : "WheelDown",
WHEEL_DOWN + CTRL : "",
WHEEL_DOWN + SHIFT : "",
WHEEL_DOWN + CTRL + SHIFT : "",

}


#########################################################################################
# HELPER CLASSES

def _shift_cursor():
    ui.qtg.QCursor.setPos(ui.qtg.QCursor.pos() + ui.qtc.QPoint(0, 1))

class RadialMenuEventFilter(ui.qtc.QObject):
    def eventFilter(self, obj, event):
        e_type = event.type()

        # IGNORE KEY PRESS
        if e_type == ui.qtc.QEvent.KeyPress:
            return True
        
        # IGNORE MOUSE PRESS
        elif e_type == ui.qtc.QEvent.MouseButtonPress:
            return True

        # FINISH ON KEY RELEASE
        elif e_type == ui.qtc.QEvent.KeyRelease:
            if not event.isAutoRepeat():
                ui.qt_app.removeEventFilter(self)
                ui.qtest.keyClick(obj, ui.qt.Key_Return, ui.qt.NoModifier)
                _mode.mouse_widget.installEventFilter(_mode)
                _mode.keyboard_widget.installEventFilter(_mode)
                ui.executeDeferred(_shift_cursor)

            return True
        
        # FINISH ON MOUSE RELEASE (MENU CALLED FROM LAUNCHER)
        elif e_type == ui.qtc.QEvent.MouseButtonRelease:
            ui.qt_app.removeEventFilter(self)
            ui.qtest.keyClick(obj, ui.qt.Key_Return, ui.qt.NoModifier)
            _mode.mouse_widget.installEventFilter(_mode)
            _mode.keyboard_widget.installEventFilter(_mode)
            ui.executeDeferred(_shift_cursor)

            return True
        
        return False


class Launcher(ui.qtw.QWidget):
    def __init__(self, mode):
        self.mode = mode

        super(Launcher, self).__init__()
        self.setParent(hou.qt.mainWindow())

        self.setWindowFlags(ui.qt.ToolTip | ui.qt.FramelessWindowHint)
        self.setWindowOpacity(LAUNCHER_OPACITY)
        self.setWindowTitle("Modeler Launcher")
        
        margin = hou.ui.scaledSize(6)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setStyleSheet('''QWidget { padding: 0px; font-size: %dpx; text-align: left; valign: center; background: black; font-weight: bold; border: none; }\
                                        QFrame { border: none; background: #222222; }\
                                        QLabel { border: none; color: #666666; background: none; }''' % (LAUNCHER_FONT_SIZE,))

        self.setStyleSheet( self.styleSheet() + "QPushButton {border: none; color: #aaaaaa;  padding: %dpx;} QPushButton::hover {border-radius: %dpx; background: #181818;}" % (hou.ui.scaledSize(4), hou.ui.scaledSize(4)) )

        self.hotkeys_qlabels = {}
        self.custom_shelf_hotkeys = {}

        main_layout = ui.qtw.QHBoxLayout(self)
        main_layout.setContentsMargins(LAUNCHER_MARGIN, LAUNCHER_MARGIN, LAUNCHER_MARGIN, LAUNCHER_MARGIN)
        main_layout.setSpacing(LAUNCHER_COLUMN_SPACING)
        label_padding = 0
        cat_border_radius = hou.ui.scaledSize(4)
        for cat in ("Edit", "View", "Select", "Radial Menus", "Mesh", "Mesh States", "Deform", "Deform States", "State", "Custom Shelf Tools"):
            if cat == "Custom Shelf Tools":
                items = []
                shelves = hou.shelves.shelves()
                if "modeler_custom" in shelves:
                    for tool in shelves["modeler_custom"].tools():
                        items.append(tool.name())
            else:
                # GET CATEGORY ITEMS
                try:
                    items = tools.CATEGORIES[cat]
                # NO CATEGORY ITEMS
                except:
                    items = []

            # START NEW CATEGORY IN A NEW LAYOUT
            if cat in ("Edit", "Select", "Mesh", "Deform", "Custom Shelf Tools"):
                layout = ui.qtw.QVBoxLayout()
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(hou.ui.scaledSize(0))
                main_layout.addLayout(layout)

            # CATEGORY LABEL
            label = ui.qtw.QLabel(cat)
            label.setStyleSheet("QLabel { font-size: %dpx; color: #777777; border-radius: %dpx; padding-left: %dpx; padding-right: %dpx; }" % (LAUNCHER_CATEGORY_FONT_SIZE, 0, label_padding, label_padding))
            label.adjustSize()
            label.setFixedHeight(LAUNCHER_CATEGORY_LABEL_HEIGHT)
            label.setAlignment(ui.qt.AlignHCenter | ui.qt.AlignVCenter)
            label.setFocusPolicy(ui.qt.NoFocus)
            layout.addWidget(label)

            if cat == "Edit":
                button = self.add_tool_button("Hotkey Editor", self.show_hotkey_editor)
                layout.addLayout(button)
                # self.add_separator(layout)
            
            for item in items:
                # CUSTOM SHELF TOOL
                if isinstance(item, str):
                    initial_name = hou.shelves.tool(item).label()

                # MODELER TOOL
                else:
                    initial_name = item.__name__

                button = self.add_tool_button(initial_name, item)
                layout.addLayout(button)

                # ADD SEPARATORS
                if initial_name in (
                                     "NodeState", "CycleHandleAlignment", "SelectThroughRemove", "MiddleButtonDrag",
                                     "OrthoView", "WireShadeObjects", "GhostOtherObjects", "ViewInstanceSubdivide", "MaximizeViewer",
                                     "SelectState", "SelectVisibleOnly", "SelectFaces", "ConvertToBoundary", "SelectOpenFaces", "SelectByFaceGroups",
                                     "Scale", "LocalScale", "EvenlySpace",
                                     "GrabBestPlane", "Relax",
                                     "Launcher", "RepeatNodeParms", "SaveScene", "WalkHistoryDown", "CenterObjectPivot"
                                     "Array", "SymmetryOff", "FixNormals", "TopoMode"
                ):

                    self.add_separator(layout)

            layout.addStretch(1)

        v_label = ui.qtw.QLabel("MODELER " + ui.MODELER_VERSION, self)
        v_label.setStyleSheet("font-size: %dpx; color: #444444;" % LAUNCHER_STATUS_FONT_SIZE)
        v_label.adjustSize()
        v_label.move(ui.x_res / 100, ui.y_res - v_label.height() - ui.x_res / 100)
        rect = ui.desktop_widget.screenGeometry(hou.qt.mainWindow())
        self.move(rect.topLeft())
        self.setFixedSize(rect.size())
        
    def show_hotkey_editor(self, mode):
        mode.hotkey_editor.show()

    def start(self):
        self.mode.finish_key_press()

        self._cursor_pos = ui.qtg.QCursor.pos()
        self.show()
        self.activateWindow()
        self.grabKeyboard()

    def hotkey_name(self, string):
        for i in range(len(string) - 1)[::-1]:
            if string[i].isupper() and string[i + 1].islower():
                string = string[:i] + " " + string[i:]
            if string[i].isupper() and string[i - 1].islower():
                string = string[:i] + " " + string[i:]
        return " ".join(string.split())
    
    def rebuild_hotkeys(self):
        for tool_name, qlabel in self.hotkeys_qlabels.items():
            if tool_name in hotkeys:
                qlabel.setText( hotkeys[tool_name] )
            else:
                qlabel.setText("")

    def add_tool_button(self, name, callback=None):
        layout = ui.qtw.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        custom_hotkey = ""

        # CUSTOM SHELF TOOL
        if isinstance(callback, str):
            tool = hou.shelves.tools()[callback]
            assignments = hou.hotkeys.assignments("h.pane.gview.tool:" + callback)
            if assignments:
                custom_hotkey = assignments[0]
                self.custom_shelf_hotkeys[custom_hotkey] = ui.partial(self.run_shelf_tool_from_hotkey, callback)

        tool_button = ui.qtw.QPushButton(self.hotkey_name(name))
        tool_button.callback = callback
        tool_button.setFixedHeight(LAUNCHER_TOOL_HEIGHT)
        layout.addWidget(tool_button)
        layout.addStretch(1)
        hotkey_label = ui.qtw.QLabel(custom_hotkey)
        tool_button.setFixedHeight(LAUNCHER_TOOL_HEIGHT)
        layout.addWidget(hotkey_label)
        tool_button.clicked.connect(self.run_tool)

        # ADD ONLY MODELER HOTKEY
        if not custom_hotkey:
            self.hotkeys_qlabels[name] = hotkey_label
        
        return layout

    def run_tool(self):
        tool_button = self.sender()
        if ui.qt_app.queryKeyboardModifiers() != ui.qt.ShiftModifier:
            self.finish()
        
        callback = tool_button.callback
        if isinstance(callback, str):
            ui.executeDeferred(ui.partial(self.run_shelf_tool_from_hotkey, callback))
        else:
            callback(self.mode)

    def run_shelf_tool_from_hotkey(self, tool):
        self.mode.scene_viewer.runShelfTool(tool)

    def add_separator(self, layout):
        sep = ui.qtw.QFrame()
        sep.setFixedHeight(LAUNCHER_SEPARATOR_HEIGHT)
        layout.addSpacing(LAUNCHER_COLUMN_SPACING / 20)
        layout.addWidget(sep)
        layout.addSpacing(LAUNCHER_COLUMN_SPACING / 20)

    def keyReleaseEvent(self, event):
        event.ignore()

    def keyPressEvent(self, event):
        if not event.isAutoRepeat() and event.key() != ui.qt.Key_Shift:
            self.finish()

    def finish(self):
        self.releaseKeyboard()
        self.mode.mouse_widget.setFocus()
        self.mode.mouse_widget.activateWindow()
        pos = ui.qtg.QCursor.pos()
        
        self.hide()
        
        if pos == self._cursor_pos:
            ui.executeDeferred(_shift_cursor)
        else:
            ui.qtg.QCursor.setPos(self._cursor_pos)

    def mousePressEvent(self, event):
        self.finish()


class HotkeyEditor(ui.qtw.QWidget):
    def __init__(self, mode):
        super(HotkeyEditor, self).__init__(hou.qt.mainWindow())

        self.mode = mode

        # SETUP WIDGET
        self.setWindowTitle("Double click to set the hotkey. Ctrl + Double click to clear it.")
        
        self.setWindowFlags( ui.qt.Window )

        self.setStyleSheet("QWidget { font-size: %dpx; border: none;} \
                            QPushButton { height: %dpx; } \
                            QPushButton::hover { background: #222222; } \
                            QLineEdit { height: %dpx; background: #191919; } \
                            QListView { background: #222222; } \
                            QListView::item { padding: %dpx; } \
                            QListView::item:selected {background: #111111; border: none; } " % (hou.ui.scaledSize(10), hou.ui.scaledSize(20), hou.ui.scaledSize(16), hou.ui.scaledSize(2)) )

        # KEYBOARD AND MOUSE LABELS
        label_height = hou.ui.scaledSize(20)
        k_label = ui.qtw.QLabel("Keyboard")
        k_label.setAlignment(ui.qt.AlignCenter)
        k_label.setFixedHeight(label_height)
        
        m_label = ui.qtw.QLabel("Mouse")
        m_label.setAlignment(ui.qt.AlignCenter)
        m_label.setFixedHeight(label_height)

        # KEYBOARD QLISTVIEW WITH FILTER PROXY MODEL
        self.k_list_view = ui.qtw.QListView()
        self.k_list_view.setVerticalScrollBarPolicy(ui.qt.ScrollBarAlwaysOff)
        self.k_list_view.setHorizontalScrollBarPolicy(ui.qt.ScrollBarAlwaysOff)
        self.k_list_view.doubleClicked.connect(self.k_set)
        self.k_list_view.setEditTriggers(self.k_list_view.NoEditTriggers)
        self.k_list_view.setToolTip('')
        self.proxy_model = ui.qtc.QSortFilterProxyModel()
        self.model = ui.qtc.QStringListModel()
        self.proxy_model.setSourceModel(self.model)
        self.k_list_view.setModel(self.proxy_model)

        # MOUSE QLISTWIDGET WITHOT FILTERING
        self.m_list_widget = ui.qtw.QListWidget()
        self.m_list_widget.setVerticalScrollBarPolicy(ui.qt.ScrollBarAlwaysOff)
        self.m_list_widget.setHorizontalScrollBarPolicy(ui.qt.ScrollBarAlwaysOff)

        self.m_list_widget.itemDoubleClicked.connect(self.m_set)

        # CREATE INITIAL UI ELEMENTS IN KEYBOARD WIDGET
        for cat in tools.CATEGORIES.keys():
            for tool in tools.CATEGORIES[cat]:
                tool_name = tool.__name__
                self.model.insertRow(self.model.rowCount())
                index = self.model.index(self.model.rowCount()-1)
                self.model.setData(index, tool_name)

        # CREATE INITIAL UI ELEMENTS IN MOUSE WIDGET
        for label in MOUSE_HOTKEYS_LABELS:
            item = ui.qtw.QListWidgetItem(self.m_list_widget)
            item.m_label = label
            item.m_action = MOUSE_HOTKEYS_ACTIONS[ MOUSE_HOTKEYS_LABELS.index(label) ]
            self.m_list_widget.addItem(item)
        
        # CREATE LAYOUTS
        margin = hou.ui.scaledSize(2)

        # OTHER UI ELEMENTS
        filter_field_height = hou.ui.scaledSize(20)
        self.filter_field = ui.qtw.QLineEdit("")
        self.filter_field.textChanged.connect(self.filter_slot)
        self.clear_filter_button = ui.qtw.QPushButton(hou.qt.createIcon("BUTTONS_delete"), "")
        self.clear_filter_button.setFixedWidth(filter_field_height)
        self.clear_filter_button.setFixedHeight(filter_field_height)
        self.clear_filter_button.clicked.connect(self.filter_field.clear)
        self.clear_filter_button.setFocusPolicy(ui.qt.NoFocus)
        filter_layout = ui.qtw.QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(hou.ui.scaledSize(2))
        filter_layout.addWidget(self.filter_field)
        filter_layout.addWidget(self.clear_filter_button)

        # KEYBOARD BUTTONS
        export_button = ui.qtw.QPushButton("Export") 
        export_button.setFocusPolicy(ui.qt.NoFocus)
        load_button = ui.qtw.QPushButton("Load")
        load_button.setFocusPolicy(ui.qt.NoFocus)
        reset_button = ui.qtw.QPushButton("Reset")
        reset_button.setFocusPolicy(ui.qt.NoFocus)
        export_button.clicked.connect(self.k_export)
        load_button.clicked.connect(self.k_load)
        reset_button.clicked.connect(self.k_reset_hotkeys)
        k_buttons_layout = ui.qtw.QHBoxLayout()
        k_buttons_layout.setContentsMargins(margin, margin, margin, margin)
        k_buttons_layout.setSpacing(margin)
        k_buttons_layout.addWidget(export_button)
        k_buttons_layout.addWidget(load_button)
        k_buttons_layout.addWidget(reset_button)

        # MOUSE BUTTONS
        export_button = ui.qtw.QPushButton("Export") 
        export_button.setFocusPolicy(ui.qt.NoFocus)
        load_button = ui.qtw.QPushButton("Load") 
        load_button.setFocusPolicy(ui.qt.NoFocus)
        reset_button = ui.qtw.QPushButton("Reset")
        reset_button.setFocusPolicy(ui.qt.NoFocus)
        export_button.clicked.connect(self.m_export)
        load_button.clicked.connect(self.m_load)
        reset_button.clicked.connect(self.m_reset_hotkeys)
        m_buttons_layout = ui.qtw.QHBoxLayout()
        m_buttons_layout.setContentsMargins(margin, margin, margin, margin)
        m_buttons_layout.setSpacing(margin)
        m_buttons_layout.addWidget(export_button)
        m_buttons_layout.addWidget(load_button)
        m_buttons_layout.addWidget(reset_button)

        # CREATE LAYOUTS
        main_layout = ui.qtw.QHBoxLayout(self)
        main_layout.setContentsMargins(margin, margin, margin, margin)
        main_layout.setSpacing(margin)
        k_layout = ui.qtw.QVBoxLayout()
        k_layout.setContentsMargins(margin, margin, margin, margin)
        k_layout.setSpacing(margin)
        m_layout = ui.qtw.QVBoxLayout()
        m_layout.setContentsMargins(margin, margin, margin, margin)
        m_layout.setSpacing(margin)

        # LAYOUT
        k_layout.addWidget(k_label)
        k_layout.addWidget(self.k_list_view)
        k_layout.addLayout(filter_layout)
        k_layout.addLayout(k_buttons_layout)
        m_layout.addWidget(m_label)
        m_layout.addWidget(self.m_list_widget)
        m_layout.addLayout(m_buttons_layout)
        main_layout.addLayout(k_layout)
        main_layout.addLayout(m_layout)

        # FIRST UPDATE
        self.update_hotkeys_list()

        self.showed = False

    def show(self):
        if not self.showed:
            pos = self.mode.mouse_widget.mapToGlobal(ui.qtc.QPoint(0, 0))
            self.setGeometry(pos.x(), pos.y(), hou.ui.scaledSize(500), self.mode.mouse_widget.height())
            self.showed = True

        super(HotkeyEditor, self).show()

    def eventFilter(self, obj, event):
        e_type = event.type()

        if e_type == ui.qtc.QEvent.MouseButtonPress:
            self.k_set_cancel()
        
        elif e_type == ui.qtc.QEvent.KeyPress:
            if event.isAutoRepeat():
                return True

            key = event.key()
            mods = event.modifiers()

            if key in (ui.qt.Key_Tab, ui.qt.Key_Return):
                self.k_set_cancel()

            elif key not in (ui.qt.Key_Alt, ui.qt.Key_Control, ui.qt.Key_Shift, ui.qt.Key_Meta):
                hotkey_string = self.mode.qt_keys_to_modeler_hotkey_string(key, mods)

                self.k_set_apply(hotkey_string)

            return True

        elif e_type in (ui.qtc.QEvent.KeyRelease, ui.qtc.QEvent.MouseButtonRelease, ui.qtc.QEvent.Wheel):
            return True

        return False

    def filter_slot(self, text):
        re = ui.qtc.QRegExp("*" + text + "*", ui.qt.CaseInsensitive, ui.qtc.QRegExp.Wildcard);
        self.proxy_model.setFilterRegExp(re)

    def k_set(self, index):
        index = self.proxy_model.mapToSource(index)
        
        # CLEAR HOTKEY
        if ui.qt_app.queryKeyboardModifiers() == ui.qt.ControlModifier:
            tool_name = self.mode.tools_labels[index.row()]
            if tool_name in list(hotkeys):
                if not hou.ui.displayMessage("Clear " + tool_name + " hotkey?", buttons=("Yes", "No"), default_choice=1, close_choice=1):
                    del hotkeys[tool_name]
                    self.commit_changes()
        
        # TRY TO SET HOTKEY
        else:
            ui.qt_app.installEventFilter(self)
            self.k_list_view.setStyleSheet("QListView::item:selected { background: #444444; }")
            self.change_index = index

    def k_set_finish(self):
        self.clear_filter_button.setEnabled(True)
        ui.qt_app.removeEventFilter(self)
        self.k_list_view.setStyleSheet("QListView::item:selected {background: #111111;}")

    def k_set_apply(self, hotkey_string):
        self.k_set_finish()
        
        for tool_name, hotkey in list(hotkeys.items()):
            if hotkey == hotkey_string:
                result = hou.ui.displayMessage(hotkey_string + "  =  " + tool_name + '. Overwrite?', title="Already Assigned", buttons=("Yes", "No"), default_choice=1, close_choice=1)
                if result == 0:
                    del hotkeys[tool_name]
                    break
                else:
                    self.update_hotkeys_list()
                    return

        tool_name = self.mode.tools_labels[self.change_index.row()]
        hotkeys[tool_name] = hotkey_string
        self.commit_changes()

    def k_set_cancel(self):
        self.k_set_finish()
        self.update_hotkeys_list()

    def k_reset_hotkeys(self):
        global hotkeys, default_hotkeys

        result = hou.ui.displayMessage("Reset all hotkeys?", title="Reset Hotkeys", buttons=("Yes", "No"), default_choice=1, close_choice=1)
        if result == 0:
            hotkeys = default_hotkeys.copy()
            self.commit_changes()

    def k_load(self):
        global hotkeys
        f = hou.ui.selectFile(chooser_mode=hou.fileChooserMode.Read)
        if f:
            f = hou.expandString(f)
            with open(f, 'rb') as f:
                hotkeys = ui.pickle.loads(f.read())
            self.commit_changes()

    def k_export(self):
        f = hou.ui.selectFile(chooser_mode=hou.fileChooserMode.Write, default_value="user_keyboard_hotkeys.pref")
        if f:
            f = hou.expandString(f)
            with open(f, 'wb') as f:
                f.write(ui.pickle.dumps(hotkeys))

    def m_set(self, item):
        if ui.qt_app.queryKeyboardModifiers() == ui.qt.ControlModifier:
            if not hou.ui.displayMessage("Clear " + item.m_label + " hotkey?", buttons=("Yes", "No"), default_choice=1, close_choice=1):
                mouse_hotkeys[item.m_action] = ""
                self.commit_changes()
        else:
            self.change_mouse_action = item.m_action
            self.k_list_view.clicked.connect(self.m_select_tool)
            item.setText(item.m_label)
            self.m_list_widget.setEnabled(False)
            self.m_list_widget.setStyleSheet("QListView::item:selected { background: #444444; }")

    def m_select_tool(self, index):
        global mouse_hotkeys

        index = self.proxy_model.mapToSource(index)
        tool_name = self.mode.tools_labels[index.row()]
        self.k_list_view.clicked.disconnect(self.m_select_tool)
        mouse_hotkeys[self.change_mouse_action] = tool_name
        self.update_hotkeys_list()
        self.commit_changes()
        self.m_list_widget.setEnabled(True)
        self.m_list_widget.setStyleSheet("QListView::item:selected {background: #111111;}")

    def m_load(self):
        global mouse_hotkeys

        f = hou.ui.selectFile(chooser_mode=hou.fileChooserMode.Read)
        if f:
            f = hou.expandString(f)
            with open(f, 'rb') as f:
                mouse_hotkeys = ui.pickle.loads(f.read())
            self.commit_changes()

    def m_export(self):
        f = hou.ui.selectFile(chooser_mode=hou.fileChooserMode.Write, default_value="user_mouse_hotkeys.pref")
        if f:
            f = hou.expandString(f)
            with open(f, 'wb') as f:
                f.write(ui.pickle.dumps(mouse_hotkeys))

    def m_reset_hotkeys(self):
        global mouse_hotkeys

        result = hou.ui.displayMessage("Select Mouse Layout:\n\n1. Default: LMB=Select; MMB=Drag; RMB=Standard behavior.\n2. Pro: LMB=Drag; MMB=Select Through; RMB=Select; Ctrl+Shift+RMB=menu", title="Reset Hotkeys", buttons=("Default", "Pro", "Cancel"), default_choice=2, close_choice=2)
        if result == 0:
            mouse_hotkeys = default_mouse_hotkeys.copy()
        elif result == 1:
            mouse_hotkeys = default_mouse_hotkeys_pro.copy()
        else:
            return
        self.commit_changes()

    def commit_changes(self):
        self.update_hotkeys_list()
        self.mode.rebuild_hotkeys()
        self.mode.launcher.rebuild_hotkeys()

        with open(self.mode.keyboard_file_path, 'wb') as f:
            f.write(ui.pickle.dumps(hotkeys))

        with open(self.mode.mouse_file_path, 'wb') as f:
            f.write(ui.pickle.dumps(mouse_hotkeys))

    def update_hotkeys_list(self):
        model = self.k_list_view.model()
        for i, tool_name in enumerate(self.mode.tools_labels):
            if tool_name in hotkeys:
                text = tool_name + "          [ " + hotkeys[tool_name] + " ]"
            else:
                text = tool_name

            index = self.model.index(i)
            self.model.setData(index, text)
 
        for i in range(self.m_list_widget.count()):
            item = self.m_list_widget.item(i)
            tool = mouse_hotkeys[item.m_action]
            if tool:
                text = item.m_label + "          [ " + tool + " ]"
            else:
                text = item.m_label

            item.setText(text)


class TabMenuEventFilter(ui.qtc.QObject):
    def finish(self):
        ui.qt_app.removeEventFilter(self)
        _mode.mouse_widget.installEventFilter(_mode)
        _mode.keyboard_widget.installEventFilter(_mode)

        ui.qtg.QCursor.setPos(ui.qtg.QCursor.pos() + ui.qtc.QPoint(0, 1))
    
    def eventFilter(self, obj, event):
        if event.type() == ui.qtc.QEvent.MouseButtonRelease:
            self.finish()
    
        elif event.type() == ui.qtc.QEvent.KeyRelease and not event.isAutoRepeat():
            if event.key() in (ui.qt.Key_Tab, ui.qt.Key_Return, ui.qt.Key_Escape):
                self.finish()
    
        return False


class Mode(ui.qtc.QObject):
    def eventFilter_standard(self, obj, event):
        e_type = event.type()

        # MOUSE PRESS
        if e_type == ui.qtc.QEvent.MouseButtonPress:
            self.press_mouse_button = event.button()
            self.press_mods = event.modifiers()
            
            # USE IN OPTIMIZATION PURPOSES + WORKABLE NON-INTERACTIVE TOOLS ASSIGNED TO MOUSE BUTTONS
            self.mouse_tool = self.bypass

            # IGNORE ANY BUTTON WITH ALT. IF LMB - TRY TO RESTORE ALIGNED VIEW 
            if ui.qt.AltModifier & self.press_mods:
                if self.press_mouse_button == ui.qt.LeftButton:
                    tools.RestoreView()

                return False           
            
            # TOOL IS IN ACTION
            elif not hou.ui.ALLOW_MODELER_TOOL:
                if hou.ui.paneTabUnderCursor() != self.scene_viewer:
                    return False
                return True

            # TOPOBUILD
            elif self.scene_viewer.currentState() == "topobuild":
                return False
            
            # MORE THEN ONE BUTTON PRESSED OR META IS IN MODIFIERS
            elif self.press_mouse_button != event.buttons() or self.press_mods & ui.qt.MetaModifier:
                return True
            
            # LMB OVERRIDES WORK ONLY IN SELECT MODE
            elif self.press_mouse_button == ui.qt.LeftButton and self.scene_viewer.currentState() != "select":
                return False
            
            # MMB OVERRIDE IGNORES ON INTERACTIVE LOOPS SELECTION
            elif self.press_mouse_button == ui.qt.MiddleButton and self.loop:
                return False

            hou.ui.ALLOW_MODELER_TOOL = False

            self.press_pos = event.pos()
            self.mouse_tool = self.mouse_hotkeys[ int(self.press_mouse_button) + int(self.press_mods) ]

            return self.mouse_tool(self)

        # MOUSE RELEASE
        elif e_type == ui.qtc.QEvent.MouseButtonRelease:
            self.press_mouse_button = None
            
            hou.ui.ALLOW_MODELER_TOOL = True

            if self.mouse_release_callback is not None:
                self.release_pos = event.pos()
                result = self.mouse_release_callback(self)
                self.mouse_release_callback = None
                return result

            # CORRECT FINISHING NON-INTERACTIVE ASSIGNED TO MOUSE BUTTONS
            elif self.mouse_tool != self.bypass:
                return True

            return False

        # KEY PRESS
        elif e_type == ui.qtc.QEvent.KeyPress:
            key = event.key()
            mods = event.modifiers()
            
            # ALT KEY
            if key == ui.qt.Key_Alt:
                self._pre_alt_state = self.scene_viewer.currentState()
                if self._pre_volatile_snapping_mode is None and self.press_mouse_button is not None or self.key_tool is not None:
                    self._pre_volatile_snapping_mode = self.scene_viewer.snappingMode()
                    self.scene_viewer.setSnappingMode(hou.snappingMode.Multi)
                else:
                    return False
            
            # IGNORE AUTOREPEAT PRESS
            elif event.isAutoRepeat():
                return True

            elif key == ui.qt.Key_Shift and self.scene_viewer.currentState().endswith("view") and self.press_mouse_button == ui.qt.LeftButton:
                self.mouse_widget.removeEventFilter(self)
                self.keyboard_widget.removeEventFilter(self)
                ui.qtest.mouseRelease(self.mouse_widget, self.press_mouse_button, ui.qt.AltModifier | ui.qt.ShiftModifier, self.mouse_widget.mapFromGlobal(ui.qtg.QCursor.pos()))
                self.mouse_widget.installEventFilter(self)
                self.keyboard_widget.installEventFilter(self)
                ui.executeDeferred(ui.partial(tools.AlignView, self))
                return True

            # INTERACTIVE TOOL IS IN PROGRESS
            elif not hou.ui.ALLOW_MODELER_TOOL:
                
                # ALLOW KEY PRESS ON OTHER WIDGETS
                if hou.ui.paneTabUnderCursor() != self.scene_viewer:
                    return False
                

            # IGNORE META KEY (MAC)
            elif key == ui.qt.Key_Meta:
                return True

            # IGNORE TAB PRESS
            elif key == ui.qt.Key_Tab:
                return True
           
            # ESCAPE KEY
            elif key == ui.qt.Key_Escape and self.scene_viewer.currentState() == "topobuild":
                with hou.RedrawBlock() as rb:
                    self.mouse_widget.removeEventFilter(self)
                    self.keyboard_widget.removeEventFilter(self)
                    ui.qtest.keyClick(self.keyboard_widget, ui.qt.Key_Escape, ui.qt.NoModifier)
                    self.mouse_widget.installEventFilter(self)
                    self.keyboard_widget.installEventFilter(self)
                    hou.ui.waitUntil(lambda: True)
                    if self.scene_viewer.currentState() == "sopview":
                        self.scene_viewer.setCurrentState("select")

            # IGNORE DELETE KEY IN SOME CASES
            elif key == ui.qt.Key_Delete and self.scene_viewer.currentState() == "topobuild":
                return False

            # USE NATIVE RETURN KEY
            elif key == ui.qt.Key_Escape and self.scene_viewer.currentState() in ("scriptselect", "scriptposition"):
                return False

            # USE NATIVE RETURN KEY
            elif key == ui.qt.Key_Return:
                return False

            # TEST FOR TOOLS HOTKEY
            else:
                string = self.qt_keys_to_modeler_hotkey_string(key, mods)

                # MODELER HOTKEY
                if string in self.hotkeys:
                    self.key_tool = self.hotkeys[string]
                    self.press_pos = self.mouse_widget.mapFromGlobal(ui.qtg.QCursor.pos())

                    # PRECESS LOOP KEYS
                    if self.key_tool.__name__.startswith("LoopSelection"):
                        key = hou.hotkeys.assignments("h.pane.gview.model.sel.loop")[0]
                        self.loop_key = eval("ui.qt.Key_" + key)
                        self.mouse_widget.removeEventFilter(self)
                        self.keyboard_widget.removeEventFilter(self)
                        ui.qtest.keyPress(self.keyboard_widget, self.loop_key, ui.qt.NoModifier)
                        self.mouse_widget.installEventFilter(self)
                        self.keyboard_widget.installEventFilter(self)
                        self.loop = True
                    else:
                        self.key_tool_time = ui.time.time()
                        self.key_tool(self)

                # CUSTOM SHELF TOOL 
                elif string in self.launcher.custom_shelf_hotkeys:
                    self.launcher.custom_shelf_hotkeys[string]()
            
            return True

        # KEY RELEASE
        elif e_type == ui.qtc.QEvent.KeyRelease:
            key = event.key()

            if obj.objectName() == "RE_GLDrawable":
                if self._pre_volatile_snapping_mode is not None:
                    self.scene_viewer.setSnappingMode(self._pre_volatile_snapping_mode)
                    self._pre_volatile_snapping_mode = None
                return False

            elif event.isAutoRepeat():
                return True

            # TAB
            elif key == ui.qt.Key_Tab:
                self.keyboard_widget.removeEventFilter(self)
                self.mouse_widget.removeEventFilter(self)
                ui.qtest.keyClick(self.mouse_widget, ui.qt.Key_Tab, ui.qt.NoModifier)
                ui.qt_app.installEventFilter(self.tab_menu_ef)
                return True
                
            elif self.loop and key == self.loop_key:
                self.mouse_widget.removeEventFilter(self)
                self.keyboard_widget.removeEventFilter(self)
                ui.qtest.keyRelease(self.keyboard_widget, self.loop_key, ui.qt.NoModifier)
                self.mouse_widget.installEventFilter(self)
                self.keyboard_widget.installEventFilter(self)
                self.loop = False
                return True

            self.finish_key_press()

            if self.mouse_release_callback is not None and self.press_mouse_button is None:
                self.release_pos = self.mouse_widget.mapFromGlobal(ui.qtg.QCursor.pos())
                result = self.mouse_release_callback(self)
                self.mouse_release_callback = None
                return result

        # DOUBLE CLICK
        elif e_type == ui.qtc.QEvent.MouseButtonDblClick:
            button = event.button()
            mods = event.modifiers()

            if ui.qt.AltModifier & mods or ( button not in (ui.qt.LeftButton, ui.qt.RightButton, ui.qt.MiddleButton) ):
                return True
            
            with hou.undos.group("Double Click Action"):
                self.press_pos = event.pos()

                state = self.state()
                pos = self.mouse_widget.mapFromGlobal(ui.qtg.QCursor.pos())
                x = pos.x()
                y = self.mouse_widget.height() - pos.y()
                
                cursor_node = self.scene_viewer.curViewport().queryNodeAtPixel(x, y)
                cur_node = self.scene_viewer.currentNode()

                is_node = self.scene_viewer.curViewport().queryPrimAtPixel(None, x, y) is not None
                in_space = not is_node and cursor_node is None


                if is_node and cursor_node is None:
                    cursor_node = cur_node

                # CURSOR IS ON SPACE
                if in_space:
                    if self.scene_viewer.selectionMode() == hou.selectionMode.Geometry:
                        self.scene_viewer.setSelectionMode(hou.selectionMode.Object)
                        self.scene_viewer.setCurrentState("select")
                    return True
                
                # CURSOR IS ON THE GEOMETRY
                elif state in ("topobuild", "modeler::topopatch"):
                    return False
          
                # SOP
                elif self.scene_viewer.selectionMode() == hou.selectionMode.Geometry:
                    # CURSOR NODE IS CURRENT
                    if self.scene_viewer.currentNode() == cursor_node:
                        if state not in ("select", "scriptselect"):
                            self.scene_viewer.setCurrentState("select")
                            hou.ui.waitUntil(lambda: True)
                            return True

                        elif button != ui.qt.LeftButton:
                            self.mouse_widget.removeEventFilter(self)
                            ui.qtest.mouseDClick(self.mouse_widget, ui.qt.LeftButton, mods, self.press_pos)
                            ui.qtest.mouseClick(self.mouse_widget, ui.qt.LeftButton, mods, self.press_pos)
                            self.mouse_widget.installEventFilter(self)
                            return True

                        return False

                    # CURSOR NODE IS NOT CURRENT. MAKE IT
                    if geo_utils.ancestor_object(cursor_node).isSelectableInViewport():
                        cursor_node.setCurrent(True, True)

                # OBJ
                elif cursor_node.isSelectableInViewport():
                    # GO INSIDE CURSOR NODE
                    self.scene_viewer.setPwd(cursor_node)

            return True

        # WHEEL
        elif e_type == ui.qtc.QEvent.Wheel:
            if event.buttons() != ui.qt.NoButton:
                return True

            wheel_mods = event.modifiers()
            
            if ui.qt.AltModifier & wheel_mods:
                return False

            elif event.delta() > 0:
                return self.mouse_hotkeys[ WHEEL_UP + int(wheel_mods) ](self)
            
            else:
                return self.mouse_hotkeys[ WHEEL_DOWN + int(wheel_mods) ](self)

            return True

        # LEAVE. DEACTIVATE VIEWER INTERACTION
        elif e_type == ui.qtc.QEvent.Leave:
            hou.ui.ALLOW_MODELER_TOOL = False
            self._pre_leave_scene_viewer_is_maximized = self.scene_viewer.pane().isMaximized()
            self.keyboard_widget.removeEventFilter(self)

        # ENTER. ACTIVATE VIEWER INTERACTION
        elif e_type == ui.qtc.QEvent.Enter:
            if hou.ui.paneTabUnderCursor() == self.scene_viewer:
                ui.qt_app.setActiveWindow(self.mouse_widget)

                hou.ui.ALLOW_MODELER_TOOL = True

                self.keyboard_widget.installEventFilter(self)

                if self._pre_volatile_snapping_mode is not None:
                    self.scene_viewer.setSnappingMode(self._pre_volatile_snapping_mode)

        # HIDE
        elif e_type == ui.qtc.QEvent.Hide and self.scene_viewer.pane().isMaximized() != self._pre_leave_scene_viewer_is_maximized:
            self.finish()

        return False


    def __init__(self):
        global hotkeys, mouse_hotkeys

        self.keyboard_file_path = hou.expandString("$HOUDINI_USER_PREF_DIR") + "/modeler_keyboard_hotkeys.pref"
        self.mouse_file_path = hou.expandString("$HOUDINI_USER_PREF_DIR") + "/modeler_mouse_hotkeys.pref"

        super(Mode, self).__init__()

        self.std_cursor = ui.qtg.QCursor( self._get_cursor_pixmap(ui.modeler_path + "/media/icons/std_cursor.svg"), 0, 0 )

        # BUILD TOOLS AND TOOLS LABELS LISTS BASED ON CATEGORIES DICT
        self.tools = []
        self.tools_labels = []
        for cat_tools in tools.CATEGORIES.values():
            self.tools += cat_tools
            self.tools_labels += [ cat_tool.__name__ for cat_tool in cat_tools ]

        # LOAD HOTKEYS FIRST TIME
        if ui.os.path.exists(self.keyboard_file_path):
            with open(self.keyboard_file_path, 'rb') as f:
                try:
                    hotkeys = ui.pickle.loads(f.read())
                except:
                    hotkeys = default_hotkeys.copy()
                    os.remove(self.keyboard_file_path)
        else:
            hotkeys = default_hotkeys.copy()

        # LOAD MOUSE HOTKEYS FIRST TIME
        if ui.os.path.exists(self.mouse_file_path):
            with open(self.mouse_file_path, 'rb') as f:
                try:
                    mouse_hotkeys = ui.pickle.loads(f.read())
                except:
                    mouse_hotkeys = default_mouse_hotkeys.copy()
                    os.remove(self.mouse_file_path)

        else:
            mouse_hotkeys = default_mouse_hotkeys.copy()

        bads = []
        # CHECK FOR KEYBOARD HOTKEYS WITH DEPRECATED TOOLS
        for key, value in list(hotkeys.items()):
            if key not in self.tools_labels:
                del hotkeys[key]
                bads.append(key)

        # CHECK FOR MOUSE HOTKEYS WITH DEPRECATED TOOLS
        for key, value in mouse_hotkeys.items():
            if value and value not in self.tools_labels:
                mouse_hotkeys[key] = ""
                bads.append(value)

        # CREATE AND INIT LAUNCHER
        self.launcher = Launcher(self)
        self.launcher.rebuild_hotkeys()

        # CREATE HOTKEY EDITOR
        self.hotkey_editor = HotkeyEditor(self)
        
        # CREATE TAB MENU EVENTFILTER
        self.tab_menu_ef = TabMenuEventFilter()

        # CREATE RADIAL MENU EVENTFILTER
        self.radial_menu_event_filter = RadialMenuEventFilter()
        
        self.started = False

    def start(self):
        # GET SCENE VIEWER
        self.scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        self.mouse_widget = ui.get_scene_viewer_mouse_widget()
        self.keyboard_widget = ui.get_scene_viewer_keyboard_widget()

        if self.scene_viewer is not None and self.mouse_widget is not None and self.keyboard_widget is not None:
            # STORE CPLANE IN MODELER INSTANCE
            self.cplane = self.scene_viewer.constructionPlane()
            
            # MODELER VARIABLES
            self.mouse_tool = None
            self.key_tool = None
            self.key_tool_time = 0.0
            self.loop = False
            self._pre_volatile_snapping_mode = None
            self._pre_alt_state = None
            self.mouse_release_callback = None
            self.press_mouse_button = None
            hou.ui.ALLOW_MODELER_TOOL = True

            # SETUP MOUSE AND KEYBOARD STARTUP HOTKEYS
            self.rebuild_hotkeys()

            # INSTALL MOUSE EVENT FILTER FOR VIEWER WIDGETS
            self.keyboard_widget.installEventFilter(self)
            self.mouse_widget.installEventFilter(self)
            self.eventFilter = self.eventFilter_standard

            # STASH HOUDINI STATE
            # self._pre_secure_selection = self.scene_viewer.isSecureSelection()
            self._pre_use_alt = hou.getPreference("viewport.altkeyviewcontrols.val")

            # CHANGE HOUDINI OPTIONS FOR MODELER
            # self.scene_viewer.setSecureSelection(True)
            hou.hscript('omunbind edit "Soft Edit Radius"')
            hou.setPreference("viewport.altkeyviewcontrols.val", "1")
            
            # VIEW STATE -> SELECT STATE
            if self.scene_viewer.currentState().endswith("view"):
                self.scene_viewer.setCurrentState("select")

            hou.ui.waitUntil(lambda: True)
            self.mouse_widget.setCursor(self.std_cursor)
            
            self.started = True

    def finish(self, message=None):
        # HIDE MODELER UI
        self.hotkey_editor.hide()

        # RESTORE ALIGNED VIEW
        tools.RestoreView()

        # FINISH PREVIEW SUBDIVIDE
        try:
            tools._preview_subdivided._subdivide_sop.destroy()
        except:
            pass

        # RESTORE HOUDINI OPTIONS
        hou.hscript('ombind -t sop "Soft Edit Radius" edit:rad hudslider:value')
        hou.setPreference("viewport.altkeyviewcontrols.val", self._pre_use_alt)


        # REMOVE MOUSE WIDGETS EVENT FILTER AND UNSET KEYBOARD BEHAVIOR
        self.mouse_widget.removeEventFilter(self)
        self.keyboard_widget.removeEventFilter(self)

        # UNSET CUSTOM VIEWER CURSOR
        self.mouse_widget.unsetCursor()

        # SCENE VIEWER STILL EXISTS
        try:
            self.scene_viewer.setGroupPicking(False)

        # SCENE VIEWER DESTROYED
        except:
            pass

        self.started = False

    def finish_key_press(self):
        self.key_tool = None
        self._pre_alt_state = None

    def start_volatile_hotkey_symbol(self, hotkey_symbol, handle_mode = False):
        self.finish_key_press()
        
        if ui.qt_app.focusWidget() is None:
            hou.ui.waitUntil(lambda: True)
            self.scene_viewer.setPromptMessage("The tool only works with a hotkey.")
        else:
            self._hotkey_symbols_to_restore = []
            dup = False

            for conflict in hou.hotkeys.findConflicts(None, "Print"):
                if conflict == hotkey_symbol:
                    dup = True
                else:
                    hou.hotkeys.removeAssignment(conflict, "Print")
                    self._hotkey_symbols_to_restore.append(conflict)

            if dup:
                self._hotkey_symbol_to_remove = None
            else:
                hou.hotkeys.addAssignment(hotkey_symbol, "Print")
                self._hotkey_symbol_to_remove = hotkey_symbol
            
            self.keyboard_widget.removeEventFilter(self)
            self.mouse_widget.removeEventFilter(self)
            
            ui.qtest.keyPress(self.mouse_widget, ui.qt.Key_Print, ui.qt.NoModifier)
            
            self.eventFilter = self.eventFilter_volatile_hotkey_symbol
            self.keyboard_widget.installEventFilter(self)
            self.mouse_widget.installEventFilter(self)

            self._vhs_handle_mode = handle_mode

            self._vhs_pre_snapping_mode = self.scene_viewer.snappingMode()
            self.scene_viewer.setSnappingMode(hou.snappingMode.Multi)

    def finish_volatile_hotkey_symbol(self):
        self.keyboard_widget.removeEventFilter(self)
        self.mouse_widget.removeEventFilter(self)

        ui.qtest.keyRelease(self.mouse_widget, ui.qt.Key_Print, ui.qt.NoModifier)
        
        for restore_symbol in self._hotkey_symbols_to_restore:
             hou.hotkeys.addAssignment(restore_symbol, "Print")

        hou.hotkeys.removeAssignment(self._hotkey_symbol_to_remove, "Print")

        self.mouse_widget.setFocus()
        self.eventFilter = self.eventFilter_standard
        self.keyboard_widget.installEventFilter(self)
        self.mouse_widget.installEventFilter(self)
        
        self.scene_viewer.setSnappingMode(self._vhs_pre_snapping_mode)

    def eventFilter_volatile_hotkey_symbol(self, obj, event):
        e_type = event.type()

        # IGNORE RMB PRESS OR ANY DOUBLE CLICK
        if ( e_type == ui.qtc.QEvent.MouseButtonPress and event.button() == ui.qt.RightButton ) and e_type == ui.qtc.QEvent.MouseButtonDblClick:
            return True

        # IGNORE MODIFIER KEYS
        elif (e_type == ui.qtc.QEvent.KeyPress or e_type == ui.qtc.QEvent.KeyRelease) and ui.key_is_modifier(event.key()):
            return False

        # IGNORE ANY NON-MODIFIER KEY PRESSES
        elif e_type == ui.qtc.QEvent.KeyPress:
            return True

        # ANY KEY RELEASE LEADS TO FINISHING THE ACTION
        elif e_type == ui.qtc.QEvent.KeyRelease:
            if not event.isAutoRepeat():
                self.finish_volatile_hotkey_symbol()

            return True

        return False

    def show_radial_menu(self, name):
        self.finish_key_press()

        self.keyboard_widget.removeEventFilter(self)
        self.mouse_widget.removeEventFilter(self)
        ui.qt_app.installEventFilter(self.radial_menu_event_filter)
 
        ui.radial_menu_viewport = self.scene_viewer.curViewport()
        self.scene_viewer.displayRadialMenu(name)

    def _get_cursor_pixmap(self, path):
        pixmap = ui.qtg.QPixmap(path)
        if hou.ui.globalScaleFactor() < 2.0:
            pixmap.setDevicePixelRatio(2)
        return pixmap

    def block_mouse_events(self, block):
        if block:
            self.mouse_widget.removeEventFilter(self)
        else:
            self.mouse_widget.installEventFilter(self)

    def block_keyboard_events(self, block):
        if block:
            self.keyboard_widget.removeEventFilter(self)
        else:
            self.keyboard_widget.installEventFilter(self)
   
    def bypass(self, mode):
        return False

    def qt_keys_to_modeler_hotkey_string(self, key, mods):
        if mods != ui.qt.NoModifier:
            hotkey_string = ""
            
            if ui.qt.AltModifier & mods:
                hotkey_string += "Alt+"
            
            if ui.qt.ControlModifier & mods:
                hotkey_string += "Ctrl+"

            if ui.qt.ShiftModifier & mods:
                hotkey_string += "Shift+"
            
            if key == ui.qt.Key_Plus:
                hotkey_string += "+"
            else:
                hotkey_string = hotkey_string + ui.qtg.QKeySequence(int(key)).toString()
        else:
            hotkey_string = ui.qtg.QKeySequence(int(key)).toString()
            
        return hotkey_string

    def rebuild_hotkeys(self):
        global hotkeys, mouse_hotkeys

        self.hotkeys = {}
        self.mouse_hotkeys = {}
        self.loop_conflicts = {}

        # KEYBOARD
        for key, value in hotkeys.items():
            # TOOL FUNCTION EXISTS IN MODELER
            try:
                self.hotkeys[value.strip()] = eval( "tools." + key )

            # TOOL FUNCTION NOT EXISTS IN MODELER
            except AttributeError:
                pass

        # MOUSE
        for key, value in mouse_hotkeys.items():
            # ASSIGNEMENT EXISTS
            if value:
                # TOOL FUNCTION EXISTS IN MODELER
                try:
                    self.mouse_hotkeys[key] = eval( "tools." + value )
                
                # TOOL FUNCTION NOT EXISTS IN MODELER
                except AttributeError:
                    pass
            
            # NO ASSIGNEMENT
            else:
                self.mouse_hotkeys[key] = self.bypass

    def state(self):
        if self.started:
            return self._pre_alt_state or self.scene_viewer.currentState()
        else:
            return hou.ui.paneTabOfType(hou.paneTabType.SceneViewer).currentState()


_mode = Mode()


def start():
    if not _mode.started:
        _mode.start()

def finish():
    if _mode.started:
        _mode.finish()

def toggle():
    if _mode.started:
        _mode.finish()
    else:
        _mode.start()

def is_started():
    return _mode.started