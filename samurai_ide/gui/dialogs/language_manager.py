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
try:
    from urllib.request import urlopen
    from urllib.error import URLError
except ImportError:
    from urllib2 import urlopen
    from urllib2 import URLError

from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QSpacerItem
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QTabWidget
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QDialog
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QObject

from samurai_ide import resources
from samurai_ide.core.file_handling import file_manager
from samurai_ide.tools import ui_tools
from samurai_ide.tools import json_manager


class LanguagesManagerWidget(QDialog):

    def __init__(self, parent):
        QDialog.__init__(self, parent, Qt.Dialog)
        self.setWindowTitle(self.tr("Language Manager"))
        self.resize(700, 500)

        vbox = QVBoxLayout(self)
        self._tabs = QTabWidget()
        vbox.addWidget(self._tabs)
        # Footer
        hbox = QHBoxLayout()
        btn_close = QPushButton(self.tr('Close'))
        btnReload = QPushButton(self.tr("Reload"))
        hbox.addWidget(btn_close)
        hbox.addSpacerItem(QSpacerItem(1, 0, QSizePolicy.Expanding))
        hbox.addWidget(btnReload)
        vbox.addLayout(hbox)
        self.overlay = ui_tools.Overlay(self)
        self.overlay.show()

        self._languages = []
        self._loading = True
        self.downloadItems = []

        # Load Themes with Thread
        btnReload.clicked.connect(self._reload_languages)
        self._thread = ui_tools.ThreadExecution(self.execute_thread)
        self._thread.finished.connect(self.load_languages_data)
        btn_close.clicked.connect(self.close)
        self._reload_languages()

    def _reload_languages(self):
        self.overlay.show()
        self._loading = True
        self._thread.execute = self.execute_thread
        self._thread.start()

    def load_languages_data(self):
        if self._loading:
            self._tabs.clear()
            self._languageWidget = LanguageWidget(self, self._languages)
            self._tabs.addTab(self._languageWidget,
                              self.tr("Languages"))
            self._loading = False
        self.overlay.hide()
        self._thread.wait()

    def download_language(self, language):
        self.overlay.show()
        self.downloadItems = language
        self._thread.execute = self._download_language_thread
        self._thread.start()

    def resizeEvent(self, event):
        self.overlay.resize(event.size())
        event.accept()

    def execute_thread(self):
        try:
            descriptor_languages = urlopen(resources.LANGUAGES_URL)
            languages = json_manager.parse(descriptor_languages)
            languages = [[name, languages[name]] for name in languages]
            local_languages = self.get_local_languages()
            languages = [languages[i] for i in range(len(languages)) if
                         os.path.basename(languages[i][1]) not in local_languages]
            self._languages = languages
        except URLError:
            self._languages = []

    def get_local_languages(self):
        if not file_manager.folder_exists(resources.LANGS_DOWNLOAD):
            file_manager.create_tree_folders(resources.LANGS_DOWNLOAD)
        languages = os.listdir(resources.LANGS_DOWNLOAD) + \
            os.listdir(resources.LANGS)
        languages = [s for s in languages if s.lower().endswith('.qm')]
        return languages

    def _download_language_thread(self):
        for d in self.downloadItems:
            self.download(d[1], resources.LANGS_DOWNLOAD)

    def download(self, url, folder):
        fileName = os.path.join(folder, os.path.basename(url))
        try:
            content = urlopen(url)
            with open(fileName, 'wb') as f:
                f.write(content.read())
        except URLError:
            return


class LanguageWidget(QWidget):

    def __init__(self, parent, languages):
        QWidget.__init__(self, parent)
        self._parent = parent
        self._languages = languages
        vbox = QVBoxLayout(self)
        self._table = ui_tools.CheckableHeaderTable(1, 2)
        self._table.removeRow(0)
        vbox.addWidget(self._table)
        ui_tools.load_table(self._table,
                            [self.tr('Language'), self.tr('URL')], self._languages)
        btnUninstall = QPushButton(self.tr('Download'))
        btnUninstall.setMaximumWidth(100)
        vbox.addWidget(btnUninstall)
        self._table.setColumnWidth(0, 200)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        btnUninstall.clicked.connect(self._download_language)

    def _download_language(self):
        languages = ui_tools.remove_get_selected_items(self._table,
                                                       self._languages)
        self._parent.download_language(languages)
