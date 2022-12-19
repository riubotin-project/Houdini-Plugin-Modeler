import os, shutil
from modeler.ui import hou, qtc, qtg, qtw, qtest, qt, partial, home_selected, inc_string, modeler_path, executeDeferred, settings, qt_app, run_internal_command
from modeler import geo_utils


class PythonPanel(qtw.QSplitter):
    def __init__(self):
        super(PythonPanel, self).__init__(None)

        self._last_xform_node = None
        self._do_auto_subdivide = False
        self._material_path = ""
        self._last = ""
        self.mask = "*.jpg"
        self.qdir = qtc.QDir("", "*", qtc.QDir.Name, qtc.QDir.Files | qtc.QDir.NoDotAndDotDot | qtc.QDir.CaseSensitive)

        right_space = hou.ui.scaledSize(-18)
        top_space = hou.ui.scaledSize(2)
        menu_padding = hou.ui.scaledSize(6)
        padding = hou.ui.scaledSize(3)
        font_size = hou.ui.scaledSize(12)
        self.setStyleSheet("QWidget { font-size: %dpx; background: #383838; border: none; } QMenu::item:selected { background: #383838; border: none; } \
                                      QSplitter:handle { background: #383838; } \
                                      QMenuBar { border: none; padding-left: %dpx; } QMenuBar::item:selected { background: #303030; } \
                                      QMenu { background: #292929; border: none; padding: %dpx;} QMenu::item { margin-right: %dpx; margin-top: %dpx; margin-bottom: %dpx; }" % (font_size, padding, menu_padding, right_space, top_space, top_space) )

        self.setHandleWidth(hou.ui.scaledSize(5))
        self.setStretchFactor(1, 10)

        margin = hou.ui.scaledSize(4)
        layout = qtw.QVBoxLayout(self)
        layout.setContentsMargins(margin, margin, margin, margin)
        self.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(hou.ui.scaledSize(4))

        self.treemodel = qtw.QFileSystemModel()
        self.treemodel.setFilter(qtc.QDir.Dirs | qtc.QDir.NoDotAndDotDot | qtc.QDir.CaseSensitive)
        self.treemodel.setReadOnly(False)
        self.treeview = qtw.QTreeView()
        self.treeview.setModel(self.treemodel)
        self.treeview.setColumnHidden(1, True)
        self.treeview.setColumnHidden(2, True)
        self.treeview.setColumnHidden(3, True)
        self.treeview.setExpandsOnDoubleClick(True)
        self.treeview.setHeaderHidden(True)
        self.treeview.setIndentation(hou.ui.scaledSize(8))
        self.treeview.setEditTriggers(qtw.QAbstractItemView.NoEditTriggers)
        self.treeview.setStyleSheet( "QTreeView { padding-left: %dpx; padding-top: %dpx; outline: none; background: #303030;} \
                                      QTreeView::branch {  border-image: url(none.png); } QTreeView::item:selected { background: #383838; border: none; } \
                                      QTreeView::item:!selected { background: #303030; border: none; }" % (hou.ui.scaledSize(8), hou.ui.scaledSize(8)) )
        self.treeview.setRootIsDecorated(False)
        self.treeview.setContextMenuPolicy(qt.CustomContextMenu)
        self.treeview.customContextMenuRequested.connect(self.show_lib_menu)
        self.tree_sel_model = self.treeview.selectionModel()

        self.listwidget = qtw.QListWidget()
        self.listwidget.setViewMode(qtw.QListWidget.IconMode)
        self.listwidget.setMovement(qtw.QListWidget.Static)
        self.listwidget.setResizeMode(qtw.QListWidget.Adjust)
        self.listwidget.setStyleSheet("QListView::item { border: none; color: #999999; } QListView::item:selected { background: none; color: #ffffff;}")
        self.listwidget.setUniformItemSizes(True)
        self.listwidget.setContextMenuPolicy(qt.CustomContextMenu)
        self.listwidget.customContextMenuRequested.connect(self.show_item_menu)
        self.listwidget_model = self.listwidget.model()

        # ITEM MENU
        self.item_menu = qtw.QMenu(self)
        self.item_menu.addAction("Add To Scene\tDbl Click").triggered.connect(self.add_to_scene_from_menu)
        self.item_menu.addAction("Insert Mesh\tAlt + Dbl Click").triggered.connect(self.insert_mesh_from_menu)
        self.item_menu.addSeparator()
        self.item_menu.addAction("Rename Item").triggered.connect(self.rename_item)
        self.item_menu.addAction("Delete Item").triggered.connect(self.delete_item)
        self.item_menu.addSeparator()
        self.item_menu.addAction("Update Icon: Current View").triggered.connect(self.update_icon)
        self.item_menu.addAction("Update Icon: Auto View").triggered.connect(partial(self.update_icon, True))

        # LIB MENU
        self.lib_menu = qtw.QMenu(self)

        self.lib_menu.addAction("Add Geometry").triggered.connect(self.new_item)
        self.lib_menu.addSeparator()
        self.lib_menu.addAction("New Library").triggered.connect(self.new_lib)
        self.lib_menu.addAction("Rename Library").triggered.connect(self.rename_lib)
        self.lib_menu.addAction("Duplicate Library").triggered.connect(self.duplicate_lib)
        self.lib_menu.addAction("Delete Library").triggered.connect(self.delete_lib)
        self.lib_menu.addSeparator()
        self.lib_menu.addAction("Update All Icons").triggered.connect(self.update_all_icons)
        self.lib_menu.addAction("Update New Icons").triggered.connect(self.update_new_icons)
        self.lib_menu.addAction("Update All Icons (Subdivide)").triggered.connect(self.update_all_icons_subdiv)
        self.lib_menu.addAction("Update New Icons (Subdivide)").triggered.connect(self.update_new_icons_subdiv)
        self.lib_menu.addSeparator()
        self.lib_menu.addAction("Import Geometry Files").triggered.connect(self.import_models)
        
        # ROOT LIB MENU
        self.root_lib_menu = qtw.QMenu(self)
        self.root_lib_menu.addAction("New Root Library").triggered.connect(self.new_lib)

        # MENUBAR
        self.setup_button = qtw.QPushButton("Setup")
        self.setup_button.setFlat(True)
        self.setup_menu = qtw.QMenu(self.setup_button)
        self.setup_button.clicked.connect(self.setup_menu_button_slot)

        self.woi_action = self.setup_menu.addAction("Icons With Wireframe")
        self.woi_action.setCheckable(True)
        self.setup_menu.addSeparator()
        action = self.setup_menu.addAction('Select "Update All Icons" Material')
        action.triggered.connect(self.select_custom_material)
        action = self.setup_menu.addAction('Disable "Update All Icons" Material')
        action.triggered.connect(self.disable_custom_material)
        self.setup_menu.addSeparator()
        action = self.setup_menu.addAction("Select Root Path")
        action.triggered.connect(self.select_root_path)
        action = self.setup_menu.addAction("Reset Root Path")
        action.triggered.connect(self.reset_root_path)
        
        self.filter_lineedit = qtw.QLineEdit()
        self.filter_lineedit.setToolTip("Filter Names. Press the button to clear.")
        self.filter_lineedit.setFixedWidth(hou.ui.scaledSize(80))
        self.filter_lineedit.setStyleSheet("QWidget { margin: 0px; background: #303030; selection-background-color: #383838; selection-color: #ffffff; }")
        self.filter_lineedit.setFocusPolicy(qt.ClickFocus)
        self.filter_lineedit.editingFinished.connect(self.filter_lineedit_slot)
        
        clear_filter_button = qtw.QPushButton(hou.qt.createIcon("BUTTONS_delete"), "")
        clear_filter_button.setFixedWidth(hou.ui.scaledSize(20))
        clear_filter_button.clicked.connect(self.clear_filter_slot)

        # LAYOUT
        ctl_layout = qtw.QHBoxLayout()
        ctl_layout.setSpacing(0)
        ctl_layout.setContentsMargins(0, 0, 0, 0)
        ctl_layout.addWidget(self.setup_button)
        ctl_layout.addWidget(self.filter_lineedit)
        ctl_layout.addWidget(clear_filter_button)

        left_layout = qtw.QVBoxLayout()
        left_layout.setSpacing(margin)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addLayout(ctl_layout)
        left_layout.addWidget(self.treeview)
        left_widget = qtw.QWidget()
        left_widget.setLayout(left_layout)

        self.addWidget(left_widget)
        self.addWidget(self.listwidget)

        # EVENTS
        self.treeview.keyPressEvent = self.treeview_listwidget_keyPressEvent
        self.treeview.mousePressEvent = self.treeview_mousePressEvent
        self.treeview.mouseMoveEvent = self.treeview_listwidget_mouseMoveEvent
        self.listwidget.keyPressEvent = self.treeview_listwidget_keyPressEvent
        self.listwidget.wheelEvent = self.listwidget_wheelEvent
        self.listwidget.mouseMoveEvent = self.treeview_listwidget_mouseMoveEvent
        
        # SIGNALS
        self.treeview.pressed.connect(self.treeview_pressed)
        self.treeview.pressed.connect(self.treeview_pressed)
        self.listwidget.itemPressed.connect(self.listwidget_item_clicked)
        self.listwidget.itemDoubleClicked.connect(self.add_to_scene)

        self.woi_action.setChecked(bool(settings.value("wireframe_on_icons", 0)))
        a = int( settings.value("tree_sizes_a", hou.ui.scaledSize(100)) )
        b = int( settings.value("tree_sizes_b", hou.ui.scaledSize(300)) )
        self.setSizes( (a, b) )
        size = int( settings.value("listwidget_icon_size", 128) )
        if size == 64:
            self.listwidget.setIconSize(qtc.QSize(64, 64))
            self.listwidget.setSpacing(1)

        elif size == 128:
            self.listwidget.setIconSize(qtc.QSize(128, 128))
            self.listwidget.setSpacing(4)
        else:
            self.listwidget.setIconSize(qtc.QSize(256, 256))
            self.listwidget.setSpacing(16)

        self.listwidget.setSpacing( int(settings.value("listwidget_spacing", hou.ui.scaledSize(4))) )
        
        # ROOT PATH
        self.default_root_path = modeler_path + "/kitbash"
        root_path = settings.value("root_path", self.default_root_path)
        self.set_root_path(root_path)

    def leaveEvent(self, event):
        super(PythonPanel, self).leaveEvent(event)
        self.save_settings()

    def setup_menu_button_slot(self):
        pos = self.setup_button.mapToGlobal(qtc.QPoint(0, 0)) + qtc.QPoint(0, self.setup_button.height())
        self.setup_menu.exec_(pos)

    def set_root_path(self, root_path):
        self.root_path = root_path
        id_ = self.treemodel.setRootPath(self.root_path)
        self.treeview.setRootIndex(id_)

    def reset_root_path(self):
        self.clear()
        self.clear_filter_slot()
        self.set_root_path(self.default_root_path)

    def select_root_path(self):
        self.setEnabled(False)
        result = hou.ui.selectFile(file_type=hou.fileType.Directory)
        self.setEnabled(True)
        self.activateWindow()
        if result:
            self.clear()
            self.clear_filter_slot()
            result = hou.expandString(result)
            self.set_root_path(result)

    def clear_filter_slot(self):
        self.filter_lineedit.setText("")
        self.filter_lineedit_slot()

    def filter_lineedit_slot(self):
        text = self.filter_lineedit.text()
        if text:
            self.mask = "*" + text + "*.jpg"
        else:
            self.mask = "*.jpg"
        self.treeview_pressed(self.treeview.currentIndex())

    def show_item_menu(self, pos):
        item = self.listwidget.itemAt(pos)
        if item is not None:
            pos = self.listwidget.mapToGlobal(pos) + qtc.QPoint(hou.ui.scaledSize(20), 0)
            self.item_menu.exec_(pos)
    
    def show_lib_menu(self, pos):
        cur_path = self.cur_path()
        gpos = self.treeview.mapToGlobal(pos) + qtc.QPoint(hou.ui.scaledSize(20), 0)
        if cur_path == self.treemodel.rootPath():
            self.root_lib_menu.exec_(gpos)
        else:
            self.lib_menu.exec_(gpos)

    def save_settings(self):
        settings.setValue("root_path", self.root_path)
        settings.setValue("wireframe_on_icons", self.woi_action.isChecked())
        a, b = self.sizes()
        settings.setValue("tree_sizes_a", a)
        settings.setValue("tree_sizes_b", b)
        settings.setValue("listwidget_icon_size", self.listwidget.iconSize().width())
        settings.setValue("listwidget_spacing", self.listwidget.spacing())
        settings.sync()

    # FIRST LIST WIDGET ITEM CLICK -> SET SELECTED ICON FROM NORMAL ICON (REMOVE BLUE OVERLAY FROM ICON)
    def listwidget_item_clicked(self, item):
        icon = item.icon()
        icon.addPixmap(icon.pixmap(256, 256, icon.Normal), icon.Selected)
        item.setIcon(icon)

    # IGNORE MOUSE MOVE EVENT TO PREVENT FROM CHANGING SELECTED ITEM
    @staticmethod
    def treeview_listwidget_mouseMoveEvent(event):
        event.ignore()

    def treeview_mousePressEvent(self, event):
        if event.buttons() == qt.LeftButton:
            super(qtw.QTreeView, self.treeview).mousePressEvent(event)
            pos = event.pos()
            index = self.treeview.indexAt(pos)
            path = self.treemodel.filePath(index)
            if not path:
                self.clear()

    def treeview_listwidget_keyPressEvent(self, event):
        event.ignore()

    def listwidget_wheelEvent(self, event):
        event.ignore()
        mods = event.modifiers()
        if mods == qt.ControlModifier:
            w = self.listwidget.iconSize().width()
            if event.delta() > 0:
                if w == 64:
                    self.listwidget.setIconSize(qtc.QSize(128, 128))
                    self.listwidget.setSpacing(4)
                elif w == 128:
                    self.listwidget.setIconSize(qtc.QSize(256, 256))
                    self.listwidget.setSpacing(16)
            else:
                if w == 256:
                    self.listwidget.setIconSize(qtc.QSize(128, 128))
                    self.listwidget.setSpacing(4)
                elif w == 128:
                    self.listwidget.setIconSize(qtc.QSize(64, 64))
                    self.listwidget.setSpacing(1)

            event.ignore()
        else:
            super(qtw.QListWidget, self.listwidget).wheelEvent(event)

    def confirmation(self, text="Are you sure?"):
        self.setEnabled(False)
        result = not hou.ui.displayMessage(text, buttons=("OK", "Cancel"), default_choice=1, close_choice=1)
        self.setEnabled(True)
        self.activateWindow()
        return result

    def message(self, text):
        self.setEnabled(False)
        hou.ui.displayMessage(text)
        self.setEnabled(True)
        self.activateWindow()

    def input(self, text, contents=""):
        self.setEnabled(False)
        result = hou.ui.readInput(text, initial_contents=contents, buttons=("OK",))[1]
        self.setEnabled(True)
        self.activateWindow()
        return result

    def add_tolbar_action(self, toolbar, label, tooltip, triggered_slot=None):
        action = toolbar.addAction(label)
        action.setToolTip(tooltip)
        if triggered_slot is not None:
            action.triggered.connect(triggered_slot)
        return action

    def clear(self):
        self.tree_sel_model.clear()
        self.listwidget.clear()

    def cur_path(self):
        if self.tree_sel_model.hasSelection():
            return self.treemodel.filePath(self.treeview.currentIndex())
        else:
            return self.treemodel.rootPath()

    def cur_item(self):
        sel_items = self.listwidget.selectedItems()
        if sel_items:
            return sel_items[0]

    def treeview_pressed(self, model_id):
        cur_path = self.treemodel.filePath(self.treeview.currentIndex())
        self.listwidget.clear()
        
        self.qdir.setPath(cur_path)
        for jpg_file_name in self.qdir.entryList((self.mask,)):
            self.listwidget.addItem( qtw.QListWidgetItem(qtg.QIcon(cur_path + "/" + jpg_file_name), jpg_file_name[:-4]) )

    def select_custom_material(self):
        self.setEnabled(False)
        result = hou.ui.selectNode(relative_to_node=None, initial_node=None, node_type_filter=hou.nodeTypeFilter.ShopMaterial)
        if result is not None:
            self._material_path = result
        self.setEnabled(True)
        self.activateWindow()

    def disable_custom_material(self):
        self._material_path = ""
    
    def new_lib(self):
        name = self.input("Enter a library name")
        if name:
            if self.tree_sel_model.hasSelection():
                model_id = self.treemodel.mkdir(self.treeview.currentIndex(), name)
            else:
                model_id = self.treemodel.mkdir(self.treeview.rootIndex(), name)
            
            self.treeview.setCurrentIndex(model_id)
            self.listwidget.clear()
                
            self.qdir.setPath(self.treemodel.filePath(model_id))
    
    def duplicate_lib(self):
        cur_path = self.cur_path()
        if cur_path != self.treemodel.rootPath() and self.confirmation('Duplicate "{}" library?'.format(os.path.split(cur_path)[-1])):
            d = qtc.QDir(cur_path)
            d.cdUp()
            up_path = d.path()
            name = inc_string(os.path.basename(cur_path))
            new_path = up_path + "/" + name
            while os.path.exists(new_path):
                name = inc_string(name)
                new_path = up_path + "/" + name
            try:
                shutil.copytree(cur_path, new_path)
            except IOError:
                self.message("Duplication input\\output error!")

    def delete_lib(self):
        cur_path = self.cur_path()
        if cur_path != self.treemodel.rootPath() and self.confirmation('Remove "{}" library?'.format(os.path.split(cur_path)[-1])):
            self.clear()
            shutil.rmtree(cur_path)

    def rename_lib(self):
        cur_path = self.cur_path()
        if cur_path != self.treemodel.rootPath():
            model_id = self.treeview.currentIndex()
            old_name = self.treemodel.fileName(model_id)
            name = self.input("Enter a new library name", old_name)
            if name and name != old_name:
                new_path = os.path.dirname(cur_path) + "/" + name
                os.rename(cur_path, new_path)
                self.clear()

    def import_models(self):
        cur_path = self.cur_path()
        if cur_path != self.treemodel.rootPath():
            self.setEnabled(False)
            files = hou.ui.selectFile(start_directory = hou.houdiniPath()[0], title = "Import Models To Library", pattern = "*.obj *.bgeo *.lwo *.stl", multiple_select = True)
            self.setEnabled(True)
            self.activateWindow()
            if files:
                self.clear_filter_slot()

                files = files.split(" ; ")
                empty_pixmap = qtg.QPixmap(256, 256)
                for file_path in files:
                    dirname, basename = os.path.split(file_path)
                    basename_no_ext, ext = os.path.splitext(basename)
                    
                    new_file_path = cur_path + "/" + basename
                    
                    name = basename_no_ext
                    while os.path.exists(new_file_path) or not name:
                        name += "1"
                        new_file_path = cur_path + "/" + name + ext

                    file_path = hou.expandString(file_path)

                    shutil.copyfile(file_path, new_file_path)
                    
                    jpg_path = dirname + "/" + basename_no_ext + ".jpg"
                    new_jpg_path = os.path.splitext(new_file_path)[0] + ".jpg"
                    
                    if os.path.exists(jpg_path):
                        shutil.copyfile(jpg_path, new_jpg_path)

                        item = qtw.QListWidgetItem(qtg.QIcon(jpg_path), name)

                    else:
                        empty_pixmap.save(new_jpg_path)
                        item = qtw.QListWidgetItem(qtg.QIcon(empty_pixmap), name)

                    self.listwidget.addItem(item)

                self.message(str(len(files)) + " models copied.")

    def delete_item(self):
        item = self.cur_item()
        if item is not None and self.confirmation('Remove "{}" item?'.format(item.text())):
            geo_path, jpg_path = self.geo_jpg_paths_from_item(item)
            if geo_path is not None:
                os.remove(geo_path)
                os.remove(jpg_path)
                
                self.listwidget.takeItem(self.listwidget.row(item))
                self.listwidget.clearSelection()

    def rename_item(self):
        item = self.cur_item()
        if item is not None:
            geo_path, jpg_path= self.geo_jpg_paths_from_item(item)
            if geo_path is not None:
                old_name = item.text()
                name = self.input("Rename library item", old_name)
                if name and name != old_name:
                    # CHECK IF FILE WITH THIS NAME EXISTS
                    if self.qdir.entryList((name + ".*",)):
                        self.message("File with this name already exists")
                        return

                    cur_path = self.cur_path()
                    
                    new_jpg_path = cur_path + "/" + name + ".jpg"
                    new_geo_path = cur_path + "/" + name + os.path.splitext(geo_path)[1]

                    os.rename(geo_path, new_geo_path)
                    os.rename(jpg_path, new_jpg_path)

                    # RENAME ITEM
                    item.setText(name)

    def update_icon(self, auto_view=False):
        item = self.cur_item()
        if item is not None:
            geo_path, jpg_path = self.geo_jpg_paths_from_item(item)
            if geo_path is not None:
                scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
                pwd = scene_viewer.pwd()
                child_cat = pwd.childTypeCategory()
                if child_cat == geo_utils._obj_category:
                    nodes = [node for node in hou.selectedNodes()]
                    if len(nodes) == 1:
                        with hou.undos.disabler():
                            self.build_object_icon(nodes[0], item.text(), auto_view=auto_view)
                            icon = qtg.QIcon(jpg_path)
                            icon.addPixmap(icon.pixmap(256, 256, icon.Normal), icon.Selected)
                            item.setIcon(icon)
                    else:
                        self.message("Select an object to update the icon and try again!")

                elif child_cat == geo_utils._sop_category:
                    sop = pwd.displayNode()
                    if sop is not None:
                        with hou.undos.disabler():
                            self.build_object_icon(geo_utils.ancestor_object(pwd), item.text(), auto_view=auto_view)
                            icon = qtg.QIcon(jpg_path)
                            icon.addPixmap(icon.pixmap(256, 256, icon.Normal), icon.Selected)
                            item.setIcon(icon)
                    else:
                        self.message("Select an object to update the icon and try again!")

    def update_all_icons(self, only_geos_wo_icons=False, subdiv=False):
        cur_path = self.cur_path()
        
        if cur_path != self.treemodel.rootPath() and self.confirmation():

            # REMOVE WIDGET ICONS
            self.listwidget.clear()

            scene_viewer = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)

            with hou.undos.disabler():
                # REMEMBER PWD
                pre_pwd = scene_viewer.pwd()

                # SET /OBJ AS VIEWER PWD
                obj_manager = hou.node("/obj")
                scene_viewer.setPwd(obj_manager)

                # CREATE TEMP GEO OBJECT WITH FILE SOP AND SET IT AS CURRENT
                tmp_obj = obj_manager.createNode("geo")
                
                tmp_obj.parm("shop_materialpath").set(self._material_path)
                

                # AUTO SUBDIVIDE
                if subdiv:
                    tmp_obj.parm("viewportlod").set(5)
                
                hou.ui.waitUntil(lambda: True)
                tmp_file_sop = tmp_obj.createNode("file")

                # CHECK ALL FILES
                for geo_filename in self.qdir.entryList():
                    name_no_ext, ext = os.path.splitext(geo_filename)
                    
                    # IGNORE JPG FILE
                    if ext == ".jpg":
                        continue
                    else:
                        jpg_path = cur_path + "/" + name_no_ext + ".jpg"
                        if os.path.exists(jpg_path) and only_geos_wo_icons:
                            continue

                    geo_filepath = cur_path + "/" + geo_filename
                    
                    tmp_file_sop.parm("file").set(geo_filepath)
                    hou.ui.waitUntil(lambda: True)
                    
                    # BAD GEOMETRY FILE
                    if tmp_file_sop.errors():
                        os.remove(geo_filepath)
                        try:
                            jpg_path = cur_path + "/" + name_no_ext + ".jpg"
                            os.remove(jpg_path)
                        except:
                            pass

                    else:
                        self.build_object_icon(tmp_obj, name_no_ext)

                # DESTROY TEMP GEO OBJECT WITH FILE SOP
                tmp_obj.destroy()

                # RESTORE PWD
                scene_viewer.setPwd(pre_pwd)


            # RESELECT LIBRARY
            self.treeview_pressed(self.treeview.currentIndex())

    def update_all_icons_subdiv(self):
        self.update_all_icons(False, True)

    def update_new_icons_subdiv(self):
        self.update_all_icons(True, True)

    def update_new_icons(self):
        self.update_all_icons(True)

    def auto_subdivide_slot(self):
        self._do_auto_subdivide = self.sender().isChecked()

    def replace_item(self):
        item = self.cur_item()
        if item is None:
            self.message("Something wrong! Select the library item, geometry from the scene, and try again")
        else:
            geo_path, jpg_path = self.geo_jpg_paths_from_item(item)
            if geo_path is not None:
                self.new_item(item, geo_path)
                scene_viewer = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
                scene_viewer.setPromptMessage("The current geometry saved to " + item.text() + " item.")

    def update_item_icon(self, auto_view=False):
        item = self.listwidget.currentItem()
        if item is None:
            self.message("Something wrong! Select the library item and try again")
        else:
            geo_path, jpg_path = self.geo_jpg_paths_from_item(item)
            if geo_path is not None:
                self.update_icon(auto_view=auto_view)

    def update_item_auto_icon(self):
        self.update_item_icon(auto_view=True)

    def new_item(self, item=None, geo_path=None):
        cur_path = self.cur_path()
        if cur_path != self.treemodel.rootPath():
            scene_viewer = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
            pwd = scene_viewer.pwd()
            child_cat = pwd.childTypeCategory()
            obj = sop = None
            
            if child_cat == geo_utils._obj_category:
                for sel in hou.selectedNodes():
                    if sel.type().name() == "geo":
                        sop = sel.displayNode()
                        if sop is not None:
                            obj = sel
                            break
                
            elif child_cat == geo_utils._sop_category:
                sop = pwd.displayNode()
                if sop is not None:
                    obj = pwd
                    while obj.type().name() != "geo":
                        obj = obj.parent()

            if obj is None or sop is None:
                self.message("Select geometry and try again")
                return
            
            if item is None:
                name = obj.name().capitalize()

                files = self.qdir.entryList((name + ".*",))
                while files:
                    name = inc_string(name)
                    files = self.qdir.entryList((name + ".*",))

                jpg_path = self.build_object_icon(obj, name)
                item = qtw.QListWidgetItem(qtg.QIcon(jpg_path), name)
                icon = qtg.QIcon(jpg_path)
                icon.addPixmap(icon.pixmap(256, 256, icon.Normal), icon.Selected)
                item.setIcon(icon)                
                self.listwidget.clearSelection()
                self.listwidget.addItem(item)
                geo_path = cur_path + "/" + name + ".bgeo"

            self.listwidget.setCurrentItem(item)
            
            # MODIFY AND SAVE GEOMETRY
            with hou.undos.disabler():

                geo = hou.Geometry(sop.geometry())
                
                geo.transform(obj.localTransform())
                
                # DESTROY ALL POINT ATTRIBUTES, EXCEPT "UV", "N", "sym_"
                for attrib in geo.pointAttribs():
                    if attrib.name() not in ("P", "uv", "N") :
                        attrib.destroy()
                
                # DESTROY ALL VERTEX ATTRIBUTES, EXCEPT "UV" and "N"
                for attrib in geo.vertexAttribs():
                    if attrib.name() not in ("uv", "N"):
                        attrib.destroy()
                
                # DESTROY ALL GROUPS, EXCEPT PRIM GROUPS
                for group in geo.pointGroups() + geo.edgeGroups():
                    group.destroy()
                    

                # DESTROY ALL DETAIL ATTRIBUTES
                # for attrib in geo.globalAttribs():
                    # attrib.destroy()
                
                # CREATE GLOBAL MATERIAL ATTRIBUTE
                global_mat = obj.evalParm("shop_materialpath")
                if global_mat:
                    attr = geo.addAttrib(hou.attribType.Global, "shop_materialpath", "", create_local_variable=False)
                    geo.setGlobalAttribValue("shop_materialpath", global_mat)

                # SAVE GEO
                geo.saveToFile(geo_path)

                # RETURN TO SOP
                if child_cat == geo_utils._sop_category:
                    sop.setCurrent(True, True)

    def build_object_icon(self, obj, name, auto_view=True):
        # REMEMBER VIEWER STATE AND SET ASPECT=1
        desktop = hou.ui.curDesktop()
        scene_viewer = desktop.paneTabOfType(hou.paneTabType.SceneViewer)
        vp = scene_viewer.curViewport()
        vp_name = vp.name()
        camera_path = desktop.name() + "." + scene_viewer.name() + "." + "world" "." + vp_name
        pre_state = hou.hscript("viewtransform -p " + camera_path)[0] + "viewdispopts -s on {0}; viewdisplay -H on {0}; {1}".format(camera_path, hou.hscript("viewrefplane *")[0])
        scene_viewer.setViewportLayout(hou.geometryViewportLayout.Single)
        
        pre_sel_mode = scene_viewer.selectionMode()

        ds = vp.settings().displaySet(hou.displaySetType.SceneObject)
        shade_mode = ds.shadedMode()

        if self.woi_action.isChecked():
            ds.setShadedMode(hou.glShadingType.SmoothWire)
        else:
            ds.setShadedMode(hou.glShadingType.Smooth)

        if auto_view:
            hou.hscript("viewtransform {0} flag (+a) aspect (1); viewdispopts -s off {0}; viewdisplay -H off {0}; viewprojection -o ortho {0}".format(camera_path))
        else:
            hou.hscript("viewtransform {0} flag (+a) aspect (1); viewdispopts -s off {0}; viewdisplay -H off {0}".format(camera_path))
        
        jpg_path = self.cur_path() + "/" + name + ".jpg"
        
        # SET VIEWPORT POSITION
        scene_viewer.setPwd(obj.parent())
        hou.ui.waitUntil(lambda: True)
        if auto_view:
            obj.setSelected(True, True)
            vp.homeSelected()
            vp.frameSelected()

        # WRITE VIEW TO FILE
        hou.hscript('viewdispopts -s off {0}; viewdisplay -H off {0}; viewrefplane -d off *; viewwrite -q 2 -c -r 256 256 -v {1} {0} "{2}"'.format(camera_path, obj.path(), jpg_path))            

        scene_viewer.setSelectionMode(pre_sel_mode)
        ds.setShadedMode(shade_mode)

        # RESTORE VIEWER STATE
        hou.hscript(pre_state)

        return jpg_path

    def geo_jpg_paths_from_item(self, item):
        name = item.text()
        cur_path = self.cur_path()
        jpg_name = name + ".jpg"

        geo_path = None
        jpg_path = None
        
        # FIND JPG AND GEO PATHS
        for filename in self.qdir.entryList((name + ".*",)):
            if filename == jpg_name:
                jpg_path = cur_path + "/" + filename
            else:
                geo_path = cur_path + "/" + filename

        if geo_path is None or jpg_path is None:
            self.message("Bad item! It was removed.")

            try:
                os.remove(jpg_path)
            except:
                pass

            try:
                os.remove(geo_path)
            except:
                pass

            self.listwidget.takeItem(self.listwidget.row(item))
            self.listwidget.clearSelection()

            return None, None

        return geo_path, jpg_path

    def add_to_scene_from_menu(self):
        item = self.listwidget.currentItem()
        self.add_to_scene(item)

    def insert_mesh_from_menu(self):
        item = self.listwidget.currentItem()
        self.add_to_scene(item, force_insert_mesh=True)

    def add_to_scene(self, item):
        # CLEAR ICONS
        geo_path, jpg_path = self.geo_jpg_paths_from_item(item)

        if geo_path is not None:
            # with hou.RedrawBlock() as rb:
                mods = qt_app.queryKeyboardModifiers()

                # ADD TO HOUDINI
                if mods == qt.NoModifier:
                    with hou.undos.group("KitBash: Add Item To Scene"):                
                        scene_viewer = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)

                        pwd = hou.node("/obj")

                        obj = pwd.createNode("geo", "kitbash_object1")
                        obj.setDisplayFlag(False)
                        f = obj.createNode("file")
                        f.parm("file").set(geo_path)
                        hou.ui.waitUntil(lambda: True)
                        
                        # BAD ITEM
                        if f.errors():
                            os.remove(geo_path)
                            os.remove(jpg_path)
                            self.listwidget.takeItem(self.listwidget.row(item))
                            self.listwidget.clearSelection()
                            obj.destroy()
                            self.message("Bad item! It was removed.")
                            return

                        file_geo = f.geometry()

                        # PROCESS MATERIAL GROUPS
                        mat = file_geo.findGlobalAttrib("shop_materialpath")
                        if mat is not None:
                            mat = file_geo.stringAttribValue("shop_materialpath")
                            f = f.createOutputNode("attribute", "delete_global_mat_attrib")
                            f.setParms({ "dtldel": "shop_materialpath", "detailrenames": 0, "ptrenames": 0, "vtxrenames": 0, "primrenames": 0, "rmanconversions": 0  })
                            obj.parm("shop_materialpath").set(mat)

                        xform_sop = f.createOutputNode("xform")
                        xform_sop.setUserData("__kitbash_xform__", "")

                        # AT SOP LEVEL -> TRANSLATE AND ROTATE
                        t, r = geo_utils.get_selection_center_and_rotation(scene_viewer)
                        if t is not None:
                            xform_sop.parmTuple("prexform_t").set(t)
                            xform_sop.parmTuple("prexform_r").set(r)

                        # SCALE NODE
                        ii = list(xform_sop.type().instances())
                        if len(ii) > 1:
                            ii.pop()
                            ii.reverse()

                            for i in ii:
                                if i.userData("__kitbash_xform__") is not None:
                                    xform_sop.parm("scale").set( i.evalParm("scale") )
                                    break

                        # DISPLAY NODE
                        with hou.RedrawBlock() as rb:
                            obj.setDisplayFlag(True)
                            xform_sop.setDisplayFlag(True)
                            xform_sop.setRenderFlag(True)
                            xform_sop.setCurrent(True, True)
                        
                        scene_viewer.enterCurrentNodeState()
                        obj.moveToGoodPosition()

                # REPLACE IN NODE
                elif mods == qt.SHIFT:
                    scene_viewer = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
                    
                    node = scene_viewer.currentNode()
                    inputs = node.inputs()
                    if len(inputs) > 1:
                        for f in (inputs[1],) + inputs[1].inputAncestors():
                            if f.type().name() == "file":
                                f.parm("file").set(geo_path)
                                scene_viewer.setPromptMessage("File node for the " + f.name() + " node was modified.")
                                break

                # INSERT MESH
                elif mods == qt.ALT:
                    with hou.undos.group("KitBash: Insert Mesh"):
                        scene_viewer = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
                        sop, sel, pwd = geo_utils.sop_selection(scene_viewer)
                        if sop is not None:
                            typ = sel.selectionType()
                            items = sel.selectionString(sop.geometry())

                            if typ == hou.geometryType.Primitives:
                                im = sop.createOutputNode("modeler::insert_mesh")
                                im.parm("group").set(items)
                                f = im.createInputNode(1, "file")
                                f.parm("file").set(geo_path)
                                hou.ui.waitUntil(lambda: True)
                                if f.errors():
                                    self.message("Bad item! It was removed.")
                                    os.remove(geo_path)
                                    os.remove(jpg_path)
                                    self.listwidget.takeItem(self.listwidget.row(item))
                                    self.listwidget.clearSelection()
                                    im.destroy()
                                    f.destroy()
                                    return

                                im.setInput(1, f)
                                im.setDisplayFlag(True)
                                im.setRenderFlag(True)
                                im.setCurrent(True, True)
                                scene_viewer.enterCurrentNodeState()


widget = None

def onCreateInterface():
    global widget

    i = []
    for pt in hou.ui.paneTabs():
        if pt.type() == hou.paneTabType.PythonPanel and pt.activeInterface().name() == "kitbash":
            i.append(pt)
    if len(i) > 1:
        for pt in i[:-1]:
            executeDeferred(pt.close)
    
    widget = PythonPanel()
    
    return widget