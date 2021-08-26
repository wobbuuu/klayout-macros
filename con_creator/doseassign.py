import pya


class DoseAssigner(pya.QDialog):
    """
    This class implements a dialog for assigning
    dose for currently selected shapes.
    """

    def __init__(self, parent=None):
        """ Dialog constructor """

        super(DoseAssigner, self).__init__()

        self.setWindowTitle("Assign dose")
        self.resize(200, 60)

        self.dosebox = pya.QDoubleSpinBox()
        self.dosebox.setRange(0, 300)
        self.dosebox.setSingleStep(0.01)

        hbox = pya.QHBoxLayout()
        hbox.addWidget(self.dosebox)
        hbox.addWidget(pya.QLabel('us', self))

        okbutton = pya.QPushButton('Set dose', self)
        okbutton.clicked(self.okbutton_clicked)
        clearbutton = pya.QPushButton('Clear dose', self)
        clearbutton.clicked(self.clearbutton_clicked)

        butbox = pya.QHBoxLayout()
        butbox.addWidget(clearbutton)
        butbox.addStretch(1)
        butbox.addWidget(okbutton)

        vbox = pya.QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addLayout(butbox)

        self.setLayout(vbox)

    def okbutton_clicked(self, checked):
        """ Event handler: "Set dose" button clicked """

        dose = self.dosebox.value
        lv = pya.LayoutView.current()
        lv.transaction("Set dose")

        for sel in lv.each_object_selected():
            obj = sel.shape if not sel.is_cell_inst() else sel.inst()
            obj.set_property('dose', f'{dose:.2f}')

        lv.commit()

    def clearbutton_clicked(self, checked):
        """ Event handler: "Clear dose" button clicked """

        lv = pya.LayoutView.current()
        lv.transaction("Assign doses")

        for sel in lv.each_object_selected():
            obj = sel.shape if not sel.is_cell_inst() else sel.inst()
            if obj.property('dose') is not None:
                obj.delete_property('dose')
        lv.commit()


# Instantiate the dialog and make it visible initially.
# Passing the main_window will make it stay on top of the main window.
dialog = DoseAssigner(pya.Application.instance().main_window())
dialog.show()
