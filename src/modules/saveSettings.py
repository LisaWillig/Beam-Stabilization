#===================================================================
# save "ui" controls and values to registry "setting"
# currently only handles comboboxes editlines & checkboxes
# ui = qmainwindow object
# settings = qsettings object

# Original from:
# https://stackoverflow.com/questions/23279125/python-pyqt4-functions-to-save-and-restore-ui-widget-values
#===================================================================
import sys
sys.path.append("..")
import inspect
from distutils.util import strtobool
import PyQt5
import os

class GUISettings:

    def guisave(self, ui, settings):

        # Save geometry
        #settings.setValue('size', ui.size())
        #settings.setValue('pos', ui.pos())

        for name, obj in inspect.getmembers(ui):
          # if type(obj) is QComboBox:  # this works similar to isinstance, but missed some field... not sure why?
          if isinstance(obj, PyQt5.QtWidgets.QComboBox):
              name = obj.objectName()  # get combobox name
              index = obj.currentIndex()  # get current index from combobox
              text = obj.itemText(index)  # get the text for current index
              settings.setValue(name, text)  # save combobox selection to registry

          if isinstance(obj, PyQt5.QtWidgets.QLineEdit):
              name = obj.objectName()
              value = obj.text()
              settings.setValue(name, value)  # save ui values, so they can be restored next time

          if isinstance(obj, PyQt5.QtWidgets.QCheckBox):
              name = obj.objectName()
              state = obj.isChecked()
              settings.setValue(name, state)

          if isinstance(obj, PyQt5.QtWidgets.QRadioButton):
              name = obj.objectName()
              value = obj.isChecked()  # get stored value from registry
              settings.setValue(name, value)

          if isinstance(obj, PyQt5.QtWidgets.QSlider):
              name = obj.objectName()
              value = obj.value()  # get stored value from registry
              settings.setValue(name, value)

          if isinstance(obj, PyQt5.QtWidgets.QSpinBox):
              name = obj.objectName()
              value = obj.value()  # get stored value from registry
              settings.setValue(name, value)


    def guirestore(self, ui, settings):

        # Restore geometry
        #self.resize(self.settings.value('size', QtCore.QSize(500, 500)))
        #self.move(self.settings.value('pos', QtCore.QPoint(60, 60)))

        for name, obj in inspect.getmembers(ui):
            if isinstance(obj, PyQt5.QtWidgets.QComboBox):
                index = obj.currentIndex()  # get current region from combobox
                # text   = obj.itemText(index)   # get the text for new selected index
                name = obj.objectName()

                value = (settings.value(name))

                if value == "":
                    continue

                index = obj.findText(value)  # get the corresponding index for specified string in combobox

                if index == -1:  # add to list if not found
                    obj.insertItems(0, [value])
                    index = obj.findText(value)
                    obj.setCurrentIndex(index)
                else:
                    obj.setCurrentIndex(index)  # preselect a combobox value by index

            if isinstance(obj, PyQt5.QtWidgets.QLineEdit):
                name = obj.objectName()
                value = settings.value(name)  # get stored value from registry
                obj.setText(value)  # restore lineEditFile

            if isinstance(obj, PyQt5.QtWidgets.QCheckBox):
                name = obj.objectName()
                value = settings.value(name)  # get stored value from registry
                if value != None:
                    obj.setChecked(strtobool(value))  # restore checkbox

            if isinstance(obj, PyQt5.QtWidgets.QRadioButton):
                name = obj.objectName()
                value = settings.value(name)  # get stored value from registry
                if value != None:
                    obj.setChecked(strtobool(value))

            if isinstance(obj, PyQt5.QtWidgets.QSlider):
                name = obj.objectName()
                value = settings.value(name)    # get stored value from registry
                if value != None:
                    obj. setValue(int(value))   # restore value from registry

            if isinstance(obj, PyQt5.QtWidgets.QSpinBox):
                name = obj.objectName()
                value = settings.value(name)    # get stored value from registry
                if value != None:
                    obj. setValue(int(value))   # restore value from registry