import importlib
import configparser
from pathlib import Path
import pya

from con_creator import calculus

importlib.reload(calculus)
from con_creator.calculus import Calculus

curdir = Path(__file__).resolve().parent
lastdir = curdir / '.lastdir'


class OutLog:
    def __init__(self, edit, color=None):
        self.edit = edit
        self.color = color

    def write(self, *args):
        if self.color:
            tc = self.edit.textColor()
            self.edit.setTextColor(self.color)
        for argv in args:
            self.edit.moveCursor(pya.QTextCursor.End)
            self.edit.insertPlainText(str(argv))
        if self.color:
            self.edit.setTextColor(tc)


class Field:
    def __init__(self, size, dots, center):
        self.size = size
        self.dots = dots
        self.center = center


class Gui:
    def __init__(self, ebl):
        # loading defaults
        config = configparser.ConfigParser()
        config.read(curdir / 'defaults.ini')
        self.ebl = ebl

        # creation of form
        if self.ebl == 'cabl':
            ui_file = pya.QFile(str(curdir / 'dialog.ui'))  # does not support Path objects
        elif self.ebl == 'xenos':
            ui_file = pya.QFile(str(curdir / 'dialog_pat.ui'))  # does not support Path objects
        ui_file.open(pya.QIODevice.ReadOnly)
        self.form = pya.QFormBuilder().load(ui_file, pya.Application.instance().main_window())
        ui_file.close()

        # setting defaults
        self.def_path = str(Path(config['General']['path']).expanduser())
        self.uselastdir = config.getboolean('General', 'uselastdir')
        if self.uselastdir and lastdir.exists():
            with open(lastdir) as f:
                self.def_path = f.readline()

        self.form.dose.value = float(config['General']['dose'])
        self.form.visible_flag.checked = config.getboolean('General', 'visible')

        self.form.field_size.currentIndex = int(config['Field']['field_size index'])
        self.form.field_dots.currentIndex = int(config['Field']['field_dots index'])
        self.form.field_center_x.value = float(config['Field']['field_center_x'])
        self.form.field_center_y.value = float(config['Field']['field_center_y'])

        self.form.reg_flag.checked = config.getboolean('Reg_marks', 'reg_marks')
        self.form.mark1_x.value = float(config['Reg_marks']['reg_mark1_x'])
        self.form.mark1_y.value = float(config['Reg_marks']['reg_mark1_y'])
        self.form.mark2_x.value = float(config['Reg_marks']['reg_mark2_x'])
        self.form.mark2_y.value = float(config['Reg_marks']['reg_mark2_y'])

        # setting event handlers
        self.form.browse_button.clicked(self._browse_button_clicked)
        self.form.clear_button.clicked(self._clear_button_clicked)
        self.form.convert_button.clicked(self._convert_button_clicked)

        self.outlog = OutLog(self.form.textEdit)
        self.form.convert_button.setEnabled(False)
        # self.form.along_y_button.setEnabled(False)
        if self.ebl == 'xenos':
            self.form.field_dots.currentIndex = 0
            self.form.field_dots.setEnabled(False)
            self.form.label_dots.setEnabled(False)
        self.form.field_layer_box.clicked(self._toggle_center)
        self.form.setStyleSheet("QWidget {font-size: 11pt; font-family: Arial,Helvetica,sans-serif}")
        self.form.exec_()

    def set_elements(self, enable):
        '''
        Enabling/disabling all elements of form excluding 'clear' button
        '''
        self.form.filename_str.setEnabled(enable)
        self.form.browse_button.setEnabled(enable)
        if self.ebl == 'cabl':
            self.form.field_groupbox.setEnabled(enable)
        elif self.ebl == 'xenos':
            self.form.field_size.setEnabled(enable)
            self.form.label_um.setEnabled(enable)
        self.form.center_groupbox.setEnabled(enable and not self.form.field_layer_box.checked)
        self.form.reg_flag.setEnabled(enable)
        self.form.visible_flag.setEnabled(enable)
        # self.form.along_x_button.setEnabled(flag)
        # self.form.along_y_button.setEnabled(flag)
        self.form.dose.setEnabled(enable)
        self.form.pitch.setEnabled(enable)
        self.form.convert_button.setEnabled(enable)
        self.form.field_layer_box.setEnabled(enable)
        self.form.merge_flag.setEnabled(enable)

    def _toggle_center(self, clicked):
        self.form.center_groupbox.setEnabled(not clicked)  # self.form.center_groupbox.checked)

    def _clear_button_clicked(self, clicked):
        self.form.textEdit.clear()

    def _browse_button_clicked(self, clicked):
        self.dirname = pya.QFileDialog.getExistingDirectory(self.form, 'Open Directory', self.def_path)
        if self.dirname is not None:
            self.form.filename_str.setText(self.dirname)
            self.form.convert_button.setEnabled(True)

    def _convert_button_clicked(self, clicked):
        if pya.Application.instance().main_window().current_view() is None:
            self.outlog.write('Please open .gds file.\n')
            return
        # collecting parametrs of execution
        # if self.form.along_x_button.checked:
        direction = 'x'
        # else:
        #    direction = 'y'
        f_size = int(self.form.field_size.currentText)
        f_dots = int(self.form.field_dots.currentText)
        f_center = [self.form.field_center_x.value, self.form.field_center_y.value]
        field = Field(f_size, f_dots, f_center)
        dose = self.form.dose.value
        pitch = self.form.pitch.value
        dirname = self.form.filename_str.displayText

        visible = self.form.visible_flag.checked
        reg_marks = self.form.reg_flag.checked
        if reg_marks:
            marks = [(self.form.mark1_x.value / 1000, self.form.mark1_y.value / 1000),
                     (self.form.mark2_x.value / 1000, self.form.mark2_y.value / 1000)]
            if marks[0][1] > marks[1][1] or (marks[0][0] > marks[1][0] and marks[0][1] == marks[1][1]):
                marks[0], marks[1] = marks[1], marks[0]
        else:
            marks = None

        self.set_elements(False)

        self.outlog.write('Starting with following parameters:\nField: size = ', f_size, ' um, dots = ', f_dots,
                          ' and center = ', f_center, ' um.\n')
        if reg_marks:
            self.outlog.write('Registration marks: ', marks, ' mm.\n')
        else:
            self.outlog.write('No registration marks.\n')
        if self.form.field_layer_box.checked:
            field_layer = self.form.field_layer.text
        else:
            field_layer = ''
        merge = self.form.merge_flag.checked
        self.worker = Calculus(self.ebl, dirname, field, marks, visible, direction, pitch, dose, self.outlog,
                               field_layer, merge)
        self.worker.start()
        self.set_elements(True)

        if self.uselastdir:
            with open(lastdir, 'w') as f:
                f.write(str(Path(dirname).resolve().parent))
