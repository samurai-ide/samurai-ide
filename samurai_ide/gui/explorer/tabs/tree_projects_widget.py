# -*- coding: utf-8 -*-
#
# This file is part of Samurai-IDE (https://samurai-ide.org).
#
# Samurai-IDE is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# any later version.
#
# Samurai-IDE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Samurai-IDE; If not, see <http://www.gnu.org/licenses/>.

import os

from PyQt5.QtWidgets import QTreeView
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QAbstractItemView
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QStackedLayout
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtWidgets import QStyle
from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QSizePolicy

from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QPalette
from PyQt5.QtGui import QCursor

from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QDateTime
from PyQt5.QtCore import QModelIndex

from samurai_ide import translations
from samurai_ide.core import settings
from samurai_ide.core.file_handling import file_manager
from samurai_ide.tools import ui_tools
from samurai_ide.tools import utils
from samurai_ide.tools import json_manager
from samurai_ide.gui.ide import IDE
from samurai_ide.gui.dialogs import add_to_project
from samurai_ide.gui.dialogs import project_properties_widget
from samurai_ide.gui.dialogs import new_project_manager
from samurai_ide.gui.explorer.explorer_container import ExplorerContainer
from samurai_ide.gui.explorer import actions
from samurai_ide.gui.explorer.nproject import NProject
from samurai_ide.tools.logger import NinjaLogger

logger = NinjaLogger('samurai_ide.gui.explorer.tree_projects_widget')

MAX_RECENT_PROJECTS = 10


class ProjectTreeColumn(QDialog):

    # Signalsnproject =
    dockWidget = pyqtSignal('PyQt_PyObject')
    undockWidget = pyqtSignal()
    changeTitle = pyqtSignal('PyQt_PyObject', 'QString')
    updateLocator = pyqtSignal()
    activeProjectChanged = pyqtSignal()

    def __init__(self, parent=None):
        super(ProjectTreeColumn, self).__init__(parent)
        vbox = QVBoxLayout(self)
        vbox.setSizeConstraint(QVBoxLayout.SetDefaultConstraint)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        self._buttons = []
        frame = QFrame()
        frame.setObjectName("actionbar")
        box = QVBoxLayout(frame)
        box.setContentsMargins(1, 1, 1, 1)
        box.setSpacing(0)

        self._combo_project = QComboBox()
        self._combo_project.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._combo_project.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self._combo_project.setObjectName("combo_projects")
        box.addWidget(self._combo_project)
        vbox.addWidget(frame)
        self._combo_project.setContextMenuPolicy(Qt.CustomContextMenu)
        self._projects_area = QStackedLayout()
        logger.debug("This is the projects area")
        vbox.addLayout(self._projects_area)

        # Empty widget
        self._empty_proj = QLabel(translations.TR_NO_PROJECTS)
        self._empty_proj.setAlignment(Qt.AlignCenter)
        self._empty_proj.setAutoFillBackground(True)
        self._empty_proj.setBackgroundRole(QPalette.Base)
        self._projects_area.addWidget(self._empty_proj)
        self._projects_area.setCurrentWidget(self._empty_proj)

        self.projects = []

        self._combo_project.activated.connect(
            self._change_current_project)
        self._combo_project.customContextMenuRequested[
            'const QPoint&'].connect(self.context_menu_for_root)

        connections = (
            {
                "target": "main_container",
                "signal_name": "addToProject",
                "slot": self._add_file_to_project
            },
            {
                "target": "main_container",
                "signal_name": "showFileInExplorer",
                "slot": self._show_file_in_explorer
            },
        )
        IDE.register_service('projects_explorer', self)
        IDE.register_signals('projects_explorer', connections)
        ExplorerContainer.register_tab(translations.TR_TAB_PROJECTS, self)

        # FIXME: Should have a ninja settings object that stores tree state
        # FIXME: Or bettter, application data object
        # TODO: check this:
        # self.connect(ide, SIGNAL("goingDown()"),
        #    self.tree_projects.shutdown)

    def install_tab(self):
        ide = IDE.get_service('ide')
        ui_tools.install_shortcuts(self, actions.PROJECTS_TREE_ACTIONS, ide)
        ide.goingDown.connect(self._on_ide_going_down)

    def _on_ide_going_down(self):
        """Save some settings before close"""
        if self.current_tree is None:
            return
        ds = IDE.data_settings()
        show_filesize = not bool(self.current_tree.isColumnHidden(1))
        ds.setValue("projectsExplorer/showFileSize", show_filesize)

    def load_session_projects(self, projects):
        for project in projects:
            if os.path.exists(project):
                self._open_project_folder(project)

    def open_project_folder(self, folderName=None):
        if settings.WORKSPACE:
            directory = settings.WORKSPACE
        else:
            directory = os.path.expanduser("~")

        if folderName is None:
            folderName = QFileDialog.getExistingDirectory(
                self, translations.TR_OPEN_PROJECT_DIRECTORY, directory)
            logger.debug("Choosing Foldername")
        if folderName:
            if not file_manager.folder_exists(folderName):
                QMessageBox.information(
                    self,
                    translations.TR_PROJECT_NONEXIST_TITLE,
                    translations.TR_PROJECT_NONEXIST % folderName)
                return
            logger.debug("Opening %s" % folderName)
            for p in self.projects:
                if p.project.path == folderName:
                    QMessageBox.information(
                        self,
                        translations.TR_PROJECT_PATH_ALREADY_EXIST_TITLE,
                        translations.TR_PROJECT_PATH_ALREADY_EXIST
                        % folderName)
                    return
            self._open_project_folder(folderName)

    def _open_project_folder(self, folderName):
        ninjaide = IDE.get_service("ide")
        # TODO: handle exception when .nja file is empty
        project = NProject(folderName)
        qfsm = ninjaide.filesystem.open_project(project)
        if qfsm:
            self.add_project(project)
            self.save_recent_projects(folderName)
            # FIXME: show editor area?
            if len(self.projects) > 1:
                title = "%s (%s)" % (
                    translations.TR_TAB_PROJECTS, len(self.projects))
            else:
                title = translations.TR_TAB_PROJECTS
            self.changeTitle.emit(self, title)

    def _add_file_to_project(self, path):
        """Add the file for 'path' in the project the user choose here."""
        if self._projects_area.count() > 0:
            path_project = [self.current_project]
            _add_to_project = add_to_project.AddToProject(path_project, self)
            _add_to_project.exec_()
            if not _add_to_project.path_selected:
                return
            main_container = IDE.get_service('main_container')
            if not main_container:
                return
            editorWidget = main_container.get_current_editor()
            if not editorWidget.file_path:
                name = QInputDialog.getText(
                    None,
                    translations.TR_ADD_FILE_TO_PROJECT,
                    translations.TR_FILENAME + ": ")[0]
                if not name:
                    QMessageBox.information(
                        self,
                        translations.TR_INVALID_FILENAME,
                        translations.TR_INVALID_FILENAME_ENTER_A_FILENAME)
                    return
            else:
                name = file_manager.get_basename(editorWidget.file_path)
            new_path = file_manager.create_path(
                _add_to_project.path_selected, name)
            ide_srv = IDE.get_service("ide")
            old_file = ide_srv.get_or_create_nfile(path)
            new_file = old_file.save(editorWidget.text(), new_path)
            # FIXME: Make this file replace the original in the open tab
        else:
            pass
            # Message about no project

    def _show_file_in_explorer(self, path):
        '''Iterate through the list of available projects and show
        the current file in the explorer view for the first
        project that contains it (i.e. if the same file is
        included in multiple open projects, the path will be
        expanded for the first project only).
        Note: This slot is connected to the main container's
        "showFileInExplorer(QString)" signal.'''
        central = IDE.get_service('central_container')
        if central and not central.is_lateral_panel_visible():
            return
        for project in self.projects:
            index = project.model().index(path)
            if index.isValid():
                # This highlights the index in the tree for us
                project.scrollTo(index, QAbstractItemView.EnsureVisible)
                project.setCurrentIndex(index)
                break

    def add_project(self, project):
        if project not in self.projects:
            self._combo_project.addItem(project.name)
            tooltip = utils.path_with_tilde_homepath(project.path)
            self._combo_project.setToolTip(tooltip)
            index = self._combo_project.count() - 1
            self._combo_project.setItemData(index, project)
            ptree = TreeProjectsWidget(project)
            self._projects_area.addWidget(ptree)
            ptree.closeProject['PyQt_PyObject'].connect(self._close_project)
            pmodel = project.model
            ptree.setModel(pmodel)
            pindex = pmodel.index(pmodel.rootPath())
            ptree.setRootIndex(pindex)
            self.projects.append(ptree)
            self._projects_area.setCurrentWidget(ptree)  # Can be empty widget
            self._combo_project.setCurrentIndex(index)

        # FIXME: improve?
        #     self._combo_project.currentIndexChanged[int].connect(
        #         self._change_current_project)

    def _close_project(self, widget):
        """Close the project related to the tree widget."""
        index = self._combo_project.currentIndex()
        self.projects.remove(widget)
        # index + 1 is necessary because the widget
        # with index 0 is the empty widget
        self._projects_area.takeAt(index + 1)
        self._combo_project.removeItem(index)
        index = self._combo_project.currentIndex()
        self._projects_area.setCurrentIndex(index + 1)
        ninjaide = IDE.get_service('ide')
        ninjaide.filesystem.close_project(widget.project.path)
        widget.deleteLater()
        if len(self.projects) > 1:
            title = "%s (%s)" % (
                translations.TR_TAB_PROJECTS, len(self.projects))
        else:
            title = translations.TR_TAB_PROJECTS
        self.changeTitle.emit(self, title)
        self.updateLocator.emit()

    def _change_current_project(self, index):
        nproject = self._combo_project.itemData(index)

        ninjaide = IDE.get_service("ide")
        projects = ninjaide.get_projects()
        for project in projects.values():
            if project == nproject:
                nproject.is_current = True
            else:
                project.is_current = False
        self._projects_area.setCurrentIndex(index + 1)
        self.activeProjectChanged.emit()

    def close_opened_projects(self):
        for project in reversed(self.projects):
            self._close_project(project)

    def save_project(self):
        """Save all the opened files that belongs to the actual project."""
        if self.current_project is not None:
            path = self.current_project.path
            main_container = IDE.get_service('main_container')
            if path and main_container:
                main_container.save_project(path)

    def create_new_project(self):
        wizard = new_project_manager.NewProjectManager(self)
        wizard.show()

    @property
    def current_project(self):
        project = None
        if self._projects_area.count() > 0 and self.current_tree is not None:
            project = self.current_tree.project
        return project

    @property
    def current_tree(self):
        tree = None
        widget = self._projects_area.currentWidget()
        if isinstance(widget, TreeProjectsWidget):
            tree = widget
        return tree

    def set_current_item(self, path):
        if self.current_project is not None:
            self.current_tree.set_current_item(path)

    def save_recent_projects(self, folder):
        settings = IDE.data_settings()
        recent_project_list = settings.value('recentProjects', {})
        # if already exist on the list update the date time
        projectProperties = json_manager.read_ninja_project(folder)
        name = projectProperties.get('name', '')
        description = projectProperties.get('description', '')

        if not name:
            name = file_manager.get_basename(folder)

        if not description:
            description = translations.TR_NO_DESCRIPTION

        if folder in recent_project_list:
            properties = recent_project_list[folder]
            properties["lastopen"] = QDateTime.currentDateTime()
            properties["name"] = name
            properties["description"] = description
            recent_project_list[folder] = properties
        else:
            recent_project_list[folder] = {
                "name": name,
                "description": description,
                "isFavorite": False, "lastopen": QDateTime.currentDateTime()}
            # if the length of the project list it's high that 10 then delete
            # the most old
            # TODO: add the length of available projects to setting
            if len(recent_project_list) > MAX_RECENT_PROJECTS:
                del recent_project_list[self.find_most_old_open(
                    recent_project_list)]
        settings.setValue('recentProjects', recent_project_list)

    def find_most_old_open(self, recent_project_list):
        listFounder = []
        for recent_project_path, content in list(recent_project_list.items()):
            listFounder.append((recent_project_path, int(
                content["lastopen"].toString("yyyyMMddHHmmzzz"))))
        listFounder = sorted(listFounder, key=lambda date: listFounder[1],
                             reverse=True)   # sort by date last used
        return listFounder[0][0]

    def reject(self):
        if self.parent() is None:
            self.dockWidget.emit(self)

    def closeEvent(self, event):
        self.dockWidget.emit(self)
        event.ignore()

    def context_menu_for_root(self):
        menu = QMenu(self)
        if self.current_tree is None:
            # No projects
            return
        path = self.current_tree.project.path
        # Reset index
        self.current_tree.setCurrentIndex(QModelIndex())

        action_add_file = menu.addAction(QIcon(":img/new"),
                                         translations.TR_ADD_NEW_FILE)
        action_add_folder = menu.addAction(QIcon(
            ":img/openProj"), translations.TR_ADD_NEW_FOLDER)
        action_create_init = menu.addAction(translations.TR_CREATE_INIT)
        menu.addSeparator()
        action_run_project = menu.addAction(translations.TR_RUN_PROJECT)
        action_properties = menu.addAction(translations.TR_PROJECT_PROPERTIES)
        action_show_file_size = menu.addAction(translations.TR_SHOW_FILESIZE)
        menu.addSeparator()
        action_close = menu.addAction(translations.TR_CLOSE_PROJECT)

        # Connections
        action_add_file.triggered.connect(
            lambda: self.current_tree._add_new_file(path))
        action_add_folder.triggered.connect(
            lambda: self.current_tree._add_new_folder(path))
        action_create_init.triggered.connect(self.current_tree._create_init)
        action_run_project.triggered.connect(
            self.current_tree._execute_project)
        action_properties.triggered.connect(
            self.current_tree.open_project_properties)
        action_close.triggered.connect(self.current_tree._close_project)
        action_show_file_size.triggered.connect(
            self.current_tree.show_filesize_info)

        # menu for the project
        for m in self.current_tree.extra_menus_by_scope['project']:
            if isinstance(m, QMenu):
                menu.addSeparator()
                menu.addMenu(m)

        # show the menu!
        menu.exec_(QCursor.pos())

        #        translations.TR_REMOVE_PROJECT_FROM_PYTHON_CONSOLE)
        #    self.connect(actionRemoveFromConsole, SIGNAL("triggered()"),
        #                 self.current_tree._remove_project_from_console)
        #        translations.TR_ADD_PROJECT_TO_PYTHON_CONSOLE)
        #    self.connect(actionAdd2Console, SIGNAL("triggered()"),
        #                 self.current_tree._add_project_to_console)


class TreeProjectsWidget(QTreeView):

    # Signals
    closeProject = pyqtSignal('PyQt_PyObject')
    """
    runProject()
    setActiveProject(PyQt_PyObject)
    closeProject(QString)
    closeFilesFromProjectClosed(QString)
    addProjectToConsole(QString)
    removeProjectFromConsole(QString)
    projectPropertiesUpdated(QTreeWidgetItem)
    """

    # Extra context menu 'all' indicate a menu for ALL LANGUAGES!
    extra_menus = {'all': []}
    # Extra context menu by scope all is for ALL the TREE ITEMS!
    extra_menus_by_scope = {'project': [], 'folder': [], 'file': []}
    # TODO: We need to implement a new mechanism for scope aware menus

    def __format_tree(self):
        """If not called after setting model, all the column format
        options are reset to default when the model is set"""
        self.setSelectionMode(QTreeView.SingleSelection)
        self.setAnimated(True)
        self.setHeaderHidden(True)
        self.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        pal = self.palette()
        pal.setColor(pal.Base, pal.base().color())
        self.setPalette(pal)

        self.hideColumn(1)  # Size
        self.hideColumn(2)  # Type
        self.hideColumn(3)  # Modification date
        self.setUniformRowHeights(True)

        ds = IDE.data_settings()
        if ds.value("projectsExplorer/showFileSize", type=bool):
            self.show_filesize_info()

    def set_current_item(self, path: str):
        index = self.model().index(path)
        if index.isValid():
            self.setCurrentIndex(index)

    def setModel(self, model):
        super(TreeProjectsWidget, self).setModel(model)
        self.__format_tree()
        # Activated is said to do the right thing on every system
        self.doubleClicked['const QModelIndex &'].connect(self._open_node)

    def __init__(self, project, state_index=list()):
        super(TreeProjectsWidget, self).__init__()
        self.setFrameShape(0)
        self.project = project
        self._added_to_console = False
        self.__format_tree()

        self.setStyleSheet("QTreeView{ show-decoration-selected: 1;}")

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu_context_tree)

        self.expanded.connect(self._item_expanded)
        self.collapsed.connect(self._item_collapsed)
        # FIXME: Should I store this somehow for each project path?
        # Perhaps store after each change
        self.state_index = list()
        self._folding_menu = FoldingContextMenu(self)

    def refresh_file_filters(self):
        ninjaide = IDE.get_service("ide")
        ninjaide.filesystem.refresh_name_filters(self.project)

    # FIXME: Check using the amount of items under this tree
    # add it to the items of pindex item children
    def _item_collapsed(self, tree_item):
        """Store status of item when collapsed"""
        path = self.model().filePath(tree_item)
        if path in self.state_index:
            path_index = self.state_index.index(path)
            self.state_index.pop(path_index)

    def _item_expanded(self, tree_item):
        """Store status of item when expanded"""
        path = self.model().filePath(tree_item)
        if path not in self.state_index:
            self.state_index.append(path)

    def _menu_context_tree(self, point):
        index = self.indexAt(point)
        if not index.isValid():
            return

        handler = None
        menu = QMenu(self)
        if self.model().isDir(index):
            self._add_context_menu_for_folders(menu)
        else:
            filename = self.model().fileName(index)
            lang = file_manager.get_file_extension(filename)
            self._add_context_menu_for_files(menu, lang)

        menu.addMenu(self._folding_menu)

        # menu for the Project Type(if present)
        if handler:
            for m in handler.get_context_menus():
                if isinstance(m, QMenu):
                    menu.addSeparator()
                    menu.addMenu(m)
        # show the menu!
        menu.exec_(QCursor.pos())

    def _add_context_menu_for_folders(self, menu):
        # Create Actions
        action_add_file = menu.addAction(QIcon(":img/new"),
                                         translations.TR_ADD_NEW_FILE)
        action_add_folder = menu.addAction(QIcon(
            ":img/openProj"), translations.TR_ADD_NEW_FOLDER)
        action_create_init = menu.addAction(translations.TR_CREATE_INIT)
        action_remove_folder = menu.addAction(translations.TR_REMOVE_FOLDER)

        action_add_file.triggered.connect(self._add_new_file)
        action_add_folder.triggered.connect(self._add_new_folder)
        action_remove_folder.triggered.connect(self._delete_folder)
        action_create_init.triggered.connect(self._create_init)
        # self.connect(action_add_file, SIGNAL("triggered()"),
        #             self._add_new_file)
        # self.connect(action_add_folder, SIGNAL("triggered()"),
        #             self._add_new_folder)
        # self.connect(action_create_init, SIGNAL("triggered()"),
        #             self._create_init)
        # self.connect(action_remove_folder, SIGNAL("triggered()"),
        #             self._delete_folder)

    def _add_context_menu_for_files(self, menu, lang):
        # Create actions
        action_rename_file = menu.addAction(translations.TR_RENAME_FILE)
        action_move_file = menu.addAction(translations.TR_MOVE_FILE)
        action_copy_file = menu.addAction(translations.TR_COPY_FILE)
        action_remove_file = menu.addAction(
            self.style().standardIcon(QStyle.SP_DialogCloseButton),
            translations.TR_DELETE_FILE)

        # Connect actions
        # self.connect(action_remove_file, SIGNAL("triggered()"),
        #             self._delete_file)
        action_remove_file.triggered.connect(self._delete_file)
        action_rename_file.triggered.connect(self._rename_file)
        action_copy_file.triggered.connect(self._copy_file)
        action_move_file.triggered.connect(self._move_file)
        # self.connect(action_rename_file, SIGNAL("triggered()"),
        #             self._rename_file)
        # self.connect(action_copy_file, SIGNAL("triggered()"),
        #             self._copy_file)
        # self.connect(action_move_file, SIGNAL("triggered()"),
        #             self._move_file)

        # Allow to edit Qt UI files with the appropiate program
        if lang == 'ui':
            action_edit_ui_file = menu.addAction(translations.TR_EDIT_UI_FILE)
            self.connect(action_edit_ui_file, SIGNAL("triggered()"),
                         self._edit_ui_file)

        # Menu for files
        for m in self.extra_menus_by_scope['file']:
            if isinstance(m, QMenu):
                menu.addSeparator()
                menu.addMenu(m)

    def _add_project_to_console(self):
        tools_dock = IDE.get_service('tools_dock')
        if tools_dock:
            tools_dock.add_project_to_console(self.project.path)
            self._added_to_console = True

    def _remove_project_from_console(self):
        tools_dock = IDE.get_service('tools_dock')
        if tools_dock:
            tools_dock.remove_project_from_console(self.project.path)
            self._added_to_console = False

    def _open_node(self, model_index):
        if self.model().isDir(model_index):
            if self.isExpanded(model_index):
                self.collapse(model_index)
            else:
                self.expand(model_index)
            return
        path = self.model().filePath(model_index)
        main_container = IDE.get_service('main_container')
        logger.debug("tried to get main container")
        if main_container:
            logger.debug("will call open file")
            main_container.open_file(path)

    def open_project_properties(self):
        proj = project_properties_widget.ProjectProperties(self.project, self)
        proj.show()

    def _close_project(self):
        self.closeProject.emit(self)

    def _create_init(self):
        path = self.model().filePath(self.currentIndex())
        if not path:
            path = self.project.path
        try:
            file_manager.create_init_file(path)
        except file_manager.NinjaFileExistsException as reason:
            QMessageBox.information(self, translations.TR_CREATE_INIT_FAIL,
                                    str(reason))

    def _add_new_file(self, path=''):
        if not path:
            path = self.model().filePath(self.currentIndex())
        main_container = IDE.get_service('main_container')
        project_path = self.project.path
        main_container.create_file(path, project_path)

    def _add_new_folder(self, path=''):
        # FIXME: We need nfilesystem support for this
        if not path:
            path = self.model().filePath(self.currentIndex())
        main_container = IDE.get_service('main_container')
        project_path = self.project.path
        main_container.create_folder(path, project_path)

    def _delete_file(self, path=''):
        if not path:
            path = self.model().filePath(self.currentIndex())
        name = file_manager.get_basename(path)
        val = QMessageBox.question(
            self, translations.TR_DELETE_FILE,
            translations.TR_DELETE_FOLLOWING_FILE.format(name),
            QMessageBox.Yes, QMessageBox.No)
        if val == QMessageBox.Yes:
            ninjaide = IDE.get_service("ide")
            current_nfile = ninjaide.get_or_create_nfile(path)
            current_nfile.delete()
            # FIXME: Manage the deletion signal instead of main container
            # fiddling here

    def _delete_folder(self):
        # FIXME: We need nfilesystem support for this
        path = self.model().filePath(self.currentIndex())
        name = file_manager.get_basename(path)
        val = QMessageBox.question(
            self, translations.TR_REMOVE_FOLDER,
            translations.TR_DELETE_FOLLOWING_FOLDER.format(name),
            QMessageBox.Yes, QMessageBox.No)
        if val == QMessageBox.Yes:
            file_manager.delete_folder(path)

    def _rename_file(self):
        path = self.model().filePath(self.currentIndex())
        name = file_manager.get_basename(path)
        new_name, ok = QInputDialog.getText(
            self, translations.TR_RENAME_FILE,
            translations.TR_ENTER_NEW_FILENAME,
            text=name)
        if ok and new_name.strip():
            filename = file_manager.create_path(
                file_manager.get_folder(path), new_name)
            if path == filename:
                return
            ninjaide = IDE.get_service("ide")
            print(ninjaide.filesystem.get_files())
            current_nfile = ninjaide.get_or_create_nfile(path)
            editable = ninjaide.get_editable(nfile=current_nfile)
            current_nfile.move(filename)
            if editable is not None:
                main_container = IDE.get_service("main_container")
                main_container.combo_area.bar.update_item_text(
                    editable, new_name)
                tree = ninjaide.filesystem.get_files()
                # FIXME: this is bad
                tree[filename] = tree.pop(path)
            print(ninjaide.filesystem.get_files())

    def _copy_file(self):
        path = self.model().filePath(self.currentIndex())
        name = file_manager.get_basename(path)
        global projectsColumn
        pathProjects = [p.project for p in projectsColumn.projects]
        add_to_project_dialog = add_to_project.AddToProject(pathProjects, self)
        add_to_project_dialog.setWindowTitle(translations.TR_COPY_FILE_TO)
        add_to_project_dialog.exec_()
        if not add_to_project_dialog.path_selected:
            return
        name = QInputDialog.getText(self, translations.TR_COPY_FILE,
                                    translations.TR_FILENAME, text=name)[0]
        if not name:
            QMessageBox.information(
                self, translations.TR_INVALID_FILENAME,
                translations.TR_INVALID_FILENAME_ENTER_A_FILENAME)
            return
        new_path = file_manager.create_path(
            add_to_project_dialog.pathSelected, name)
        ninjaide = IDE.get_service("ide")
        current_nfile = ninjaide.get_or_create_nfile(path)
        # FIXME: Catch willOverWrite and willCopyTo signals
        current_nfile.copy(new_path)

    def _move_file(self):
        path = self.model().filePath(self.currentIndex())
        global projectsColumn
        path_projects = [p.project for p in projectsColumn.projects]
        add_to_project_dialog = add_to_project.AddToProject(path_projects)
        add_to_project_dialog.setWindowTitle(translations.TR_MOVE_FILE)
        add_to_project_dialog.exec_()
        if not add_to_project_dialog.path_selected:
            return
        name = file_manager.get_basename(path)
        new_path = file_manager.create_path(
            add_to_project_dialog.path_selected, name)
        ninjaide = IDE.get_service("ide")
        current_nfile = ninjaide.get_or_create_nfile(path)
        current_nfile.close()
        # FIXME: Catch willOverWrite and willMove signals
        current_nfile.move(new_path)

    def show_filesize_info(self):
        """Show or Hide the filesize information on TreeProjectWidget"""
        self.showColumn(1) if self.isColumnHidden(1) else self.hideColumn(1)

        # #open the correct program to edit Qt UI files!

    def _execute_project(self):
        tools_dock = IDE.get_service('tools_dock')
        if tools_dock:
            tools_dock.execute_project()

    def keyPressEvent(self, event):
        super(TreeProjectsWidget, self).keyPressEvent(event)
        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            self._open_node(self.currentIndex())


class FoldingContextMenu(QMenu):
    """
    This class represents a menu for Folding/Unfolding task
    """

    def __init__(self, tree):
        super(FoldingContextMenu, self).__init__()
        self._tree = tree
        self._collapsed = True

        self.setTitle(translations.TR_FOLD + " / " + translations.TR_UNFOLD)

        fold_project = self.addAction(translations.TR_FOLD_PROJECT)
        unfold_project = self.addAction(translations.TR_UNFOLD_PROJECT)

        fold_project.triggered.connect(
            lambda: self._fold_unfold_project(False))
        unfold_project.triggered.connect(
            lambda: self._fold_unfold_project(True))

    def _fold_unfold_project(self, expand):
        """
        Fold the current project
        """
        if self._collapsed:
            self._tree.expandAll()
        else:
            self._tree.collapseAll()

    def _fold_all_projects(self):
        """
        Fold all projects
        """
        self._tree.collapseAll()

    def _unfold_all_projects(self):
        """
        Unfold all project
        """
        self._tree.expandAll()


if settings.SHOW_PROJECT_EXPLORER:
    projectsColumn = ProjectTreeColumn()
else:
    projectsColumn = None
