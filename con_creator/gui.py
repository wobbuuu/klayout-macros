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

class ConverterDialog(pya.QDialog):
    """
    This class implements a dialog for design convert
    """

    def __init__(self, parent=None, ebl='xenos'):
        """ Dialog constructor """

        super(ConverterDialog, self).__init__()

        # loading defaults
        config = configparser.ConfigParser()
        config.read(curdir / ('defaults_' + ebl + '.ini'))
        self.ebl = ebl

        self.setWindowTitle("Create .ctl and .pat files")
        # self.resize(540, 650)

        vbox = pya.QVBoxLayout()

        hbox = pya.QHBoxLayout()
        hbox.addWidget(pya.QLabel('Directory', self))
        self.filename_str = pya.QLineEdit('', self)
        self.filename_str.setReadOnly(True)
        hbox.addWidget(self.filename_str)
        self.browse_button = pya.QPushButton('Browse', self)
        hbox.addWidget(self.browse_button)
        vbox.addLayout(hbox)

        if self.ebl == 'cabl':
            vbox.addWidget(pya.QLabel('Warning! All *.con, *.ccc, *.cbc files in this directory will be deleted!', self))
        elif self.ebl == 'xenos':
            vbox.addWidget(pya.QLabel('Warning! All *.ctl, *.pat files in this directory will be deleted!', self))

        self.field_groupbox = pya.QGroupBox('Field', self)
        grid = pya.QGridLayout()
        self.field_size = pya.QComboBox(self)
        if self.ebl == 'cabl':
            self.field_size.addItems(['60', '120', '300', '600', '1200'])
        elif self.ebl == 'xenos':
            self.field_size.addItems(['50', '100', '250', '500', '1000'])
        grid.addWidget(self.field_size, 0, 0)
        self.label_um = pya.QLabel('um', self)
        grid.addWidget(self.label_um, 0, 1)
        self.field_dots = pya.QComboBox(self)
        if self.ebl == 'cabl':
            self.field_dots.addItems(['10000', '20000', '60000', '240000'])
        elif self.ebl == 'xenos':
            self.field_dots.addItems(['50000'])
        grid.addWidget(self.field_dots, 1, 0)
        self.label_dots = pya.QLabel('dots', self)
        grid.addWidget(self.label_dots, 1, 1)
        self.field_groupbox.setLayout(grid)

        self.center_groupbox = pya.QGroupBox('Center', self)
        grid = pya.QGridLayout()
        grid.addWidget(pya.QLabel('X', self), 0, 0)
        self.field_center_x = pya.QDoubleSpinBox(self)
        self.field_center_x.setRange(-1200, 1200)
        self.field_center_x.setDecimals(3)
        self.field_center_x.setButtonSymbols(pya.QAbstractSpinBox.NoButtons)
        grid.addWidget(self.field_center_x, 0, 1)
        grid.addWidget(pya.QLabel('um', self), 0, 2)
        grid.addWidget(pya.QLabel('Y', self), 1, 0)
        self.field_center_y = pya.QDoubleSpinBox(self)
        self.field_center_y.setRange(-1200, 1200)
        self.field_center_y.setDecimals(3)
        self.field_center_y.setButtonSymbols(pya.QAbstractSpinBox.NoButtons)
        grid.addWidget(self.field_center_y, 1, 1)
        grid.addWidget(pya.QLabel('um', self), 1, 2)
        self.center_groupbox.setLayout(grid)

        self.field_layer_box = pya.QGroupBox('Field layer', self)
        self.field_layer_box.setCheckable(True)
        self.field_layer_box.setChecked(False)
        hbox = pya.QHBoxLayout()
        self.field_layer = pya.QLineEdit('1/0', self)
        self.field_layer.setFixedWidth(75)
        hbox.addWidget(self.field_layer)
        hbox.addStretch()
        self.field_layer_box.setLayout(hbox)

        vbox1 = pya.QVBoxLayout()
        vbox1.addWidget(self.field_groupbox)
        vbox1.addStretch()
        vbox1.addWidget(self.field_layer_box)
        vbox1.addStretch()
        vbox1.addWidget(self.center_groupbox)

        self.reg_flag = pya.QGroupBox('Reg. marks', self)
        self.reg_flag.setCheckable(True)
        grid = pya.QGridLayout()

        self.marks = []
        if self.ebl == 'cabl':
            self.nmarks = 2
        elif self.ebl == 'xenos':
            self.nmarks = 4
        for i in range(self.nmarks):
            grid.addWidget(pya.QLabel('X' + str(i+1), self), 2*i, 0)
            mark_x = pya.QDoubleSpinBox(self)
            mark_x.setButtonSymbols(pya.QAbstractSpinBox.NoButtons)
            mark_x.setDecimals(3)
            mark_x.setRange(-99999, 99999)
            mark_y = pya.QDoubleSpinBox(self)
            mark_y.setButtonSymbols(pya.QAbstractSpinBox.NoButtons)
            mark_y.setDecimals(3)
            mark_y.setRange(-99999, 99999)
            self.marks.append((mark_x, mark_y))
            grid.addWidget(mark_x, 2*i, 1)
            grid.addWidget(pya.QLabel('um', self), 2*i, 2)
            grid.addWidget(pya.QLabel('Y' + str(i+1), self), 2*i+1, 0)
            grid.addWidget(mark_y, 2*i+1, 1)
            grid.addWidget(pya.QLabel('um', self), 2*i+1, 2)
        self.reg_flag.setLayout(grid)

        vbox2 = pya.QVBoxLayout()
        vbox2.addWidget(self.reg_flag)
        vbox2.addStretch()

        self.visible_flag = pya.QCheckBox('Only visible layers', self)
        self.merge_flag = pya.QCheckBox('Merge objects', self)
        self.along_x_button = pya.QRadioButton('Along X axis', self)
        self.along_x_button.setChecked(True)
        self.along_x_button.setEnabled(False)


        grid = pya.QGridLayout()
        grid.addWidget(pya.QLabel('Dose', self), 0, 0)
        self.dose = pya.QDoubleSpinBox(self)
        self.dose.setButtonSymbols(pya.QAbstractSpinBox.NoButtons)
        self.dose.setDecimals(2)
        self.dose.setRange(0, 300)
        grid.addWidget(self.dose, 0, 1)
        grid.addWidget(pya.QLabel('us', self), 0, 2)
        grid.addWidget(pya.QLabel('Pitch', self), 1, 0)
        self.pitch = pya.QSpinBox(self)
        self.pitch.setButtonSymbols(pya.QAbstractSpinBox.NoButtons)
        self.pitch.setRange(1, 99)
        grid.addWidget(self.pitch, 1, 1)
        grid.addWidget(pya.QLabel('', self), 1, 2)

        vbox3 = pya.QVBoxLayout()
        vbox3.addWidget(self.visible_flag)
        vbox3.addWidget(self.merge_flag)
        vbox3.addWidget(self.along_x_button)
        vbox3.addLayout(grid)
        vbox3.addStretch()

        hbox = pya.QHBoxLayout()
        hbox.addLayout(vbox1)
        hbox.addStretch()
        hbox.addLayout(vbox2)
        hbox.addStretch()
        hbox.addLayout(vbox3)
        vbox.addLayout(hbox)

        self.textEdit = pya.QTextEdit('', self)
        self.textEdit.document.setPlainText('---------------------------- 999.9 seconds ----------------------------')

        font = self.textEdit.document.defaultFont
        fontMetrics = pya.QFontMetrics(font)
        textSize = fontMetrics.size(0, self.textEdit.toPlainText())
        w = textSize.width + 10
        h = 10 * textSize.height + 10
        self.textEdit.setMinimumSize(w, h)
        # self.textEdit.setMaximumSize(w, h)
        # self.textEdit.resize(w, h)
        self.textEdit.document.setPlainText('')

        self.textEdit.setReadOnly(True)
        vbox.addWidget(self.textEdit)

        self.clear_button = pya.QPushButton('Clear', self)
        self.convert_button = pya.QPushButton('Convert', self)
        hbox = pya.QHBoxLayout()
        hbox.addWidget(self.clear_button)
        hbox.addStretch()
        hbox.addWidget(self.convert_button)
        vbox.addLayout(hbox)

        self.setLayout(vbox)
        self.setFixedSize(vbox.sizeHint())

        # setting defaults
        self.def_path = str(Path(config['General']['path']).expanduser())
        self.uselastdir = config.getboolean('General', 'uselastdir')
        if self.uselastdir and lastdir.exists():
            with open(lastdir) as f:
                self.def_path = f.readline()

        self.dose.value = float(config['General']['dose'])
        self.pitch.value = int(config['General']['pitch'])
        self.visible_flag.checked = config.getboolean('General', 'visible')

        self.field_size.currentIndex = int(config['Field']['field_size index'])
        self.field_dots.currentIndex = int(config['Field']['field_dots index'])
        self.field_center_x.value = float(config['Field']['field_center_x'])
        self.field_center_y.value = float(config['Field']['field_center_y'])

        self.reg_flag.checked = config.getboolean('Reg_marks', 'reg_marks')
        for i in range(self.nmarks):
            self.marks[i][0].value = float(config['Reg_marks']['reg_mark' + str(i+1) + '_x'])
            self.marks[i][1].value = float(config['Reg_marks']['reg_mark' + str(i+1) + '_y'])

        # setting event handlers
        self.browse_button.clicked(self._browse_button_clicked)
        self.clear_button.clicked(self._clear_button_clicked)
        self.convert_button.clicked(self._convert_button_clicked)

        self.outlog = OutLog(self.textEdit)
        self.convert_button.setEnabled(False)
        if self.ebl == 'xenos':
            self.field_dots.currentIndex = 0
            self.field_dots.setEnabled(False)
            self.label_dots.setEnabled(False)
        self.field_layer_box.clicked(self._toggle_center)
        # self.setStyleSheet("QWidget {font-size: 11pt; font-family: Arial,Helvetica,sans-serif}")
        # self.exec_()


    def set_elements(self, enable):
        '''
        Enabling/disabling all elements of form excluding 'clear' button
        '''
        self.filename_str.setEnabled(enable)
        self.browse_button.setEnabled(enable)
        if self.ebl == 'cabl':
            self.field_groupbox.setEnabled(enable)
        elif self.ebl == 'xenos':
            self.field_size.setEnabled(enable)
            self.label_um.setEnabled(enable)
        self.center_groupbox.setEnabled(enable and not self.field_layer_box.checked)
        self.reg_flag.setEnabled(enable)
        self.visible_flag.setEnabled(enable)
        # self.along_x_button.setEnabled(flag)
        self.dose.setEnabled(enable)
        self.pitch.setEnabled(enable)
        self.convert_button.setEnabled(enable)
        self.field_layer_box.setEnabled(enable)
        self.merge_flag.setEnabled(enable)

    def _toggle_center(self, clicked):
        self.center_groupbox.setEnabled(not clicked)  # self.center_groupbox.checked)

    def _clear_button_clicked(self, clicked):
        self.textEdit.clear()

    def _browse_button_clicked(self, clicked):
        self.dirname = pya.QFileDialog.getExistingDirectory(self, 'Open Directory', self.def_path)
        if self.dirname is not None:
            self.filename_str.setText(self.dirname)
            self.convert_button.setEnabled(True)

    def _convert_button_clicked(self, clicked):
        if pya.Application.instance().main_window().current_view() is None:
            self.outlog.write('Please open .gds file.\n')
            return

        # collecting parametrs of execution
        direction = 'x'

        f_size = int(self.field_size.currentText)
        f_dots = int(self.field_dots.currentText)
        f_center = [self.field_center_x.value, self.field_center_y.value]
        field = Field(f_size, f_dots, f_center)
        dose = self.dose.value
        pitch = self.pitch.value
        dirname = self.filename_str.displayText

        if self.reg_flag.checked:
            marks = [(m[0].value / 1000, m[1].value / 1000) for m in self.marks]
            if self.ebl == 'cabl':
                if marks[0][1] > marks[1][1] or (marks[0][0] > marks[1][0] and marks[0][1] == marks[1][1]):
                    marks[0], marks[1] = marks[1], marks[0]
            elif self.ebl == 'xenos':
                pass
        else:
            marks = None

        self.set_elements(False)

        self.outlog.write('Starting with following parameters:\nField: size = ', f_size, ' um, dots = ', f_dots,
                          ' and center = ', f_center, ' um.\n')
        if self.reg_flag.checked:
            self.outlog.write('Registration marks: ', marks, ' mm.\n')
        else:
            self.outlog.write('No registration marks.\n')
        if self.field_layer_box.checked:
            field_layer = self.field_layer.text
        else:
            field_layer = ''

        self.worker = Calculus(self.ebl, dirname, field, marks, self.visible_flag.checked, direction, pitch, dose, self.outlog,
                               field_layer, self.merge_flag.checked)
        self.worker.start()
        self.set_elements(True)

        if self.uselastdir:
            with open(lastdir, 'w') as f:
                f.write(str(Path(dirname).resolve().parent))