from collections import defaultdict
import pya


class DoseVisualizer(pya.QDialog):
    """
    This class implements a dialog for visualizing
    doses of all shapes in currently visible layers.
    """

    def __init__(self, parent=None):
        """ Dialog constructor """
        super(DoseVisualizer, self).__init__()

        self.dose_layer = 10000  # aux layer
        self.layers = []  # layout layers to hide
        self.view = pya.Application.instance().main_window().current_view()
        self.cell = self.view.active_cellview().cell
        self.ly = self.view.active_cellview().layout()

        self.setWindowTitle("Visualize doses")
        self.resize(200, 30)

        showbutton = pya.QPushButton('Show', self)
        showbutton.clicked(self.showbutton_clicked)
        cleanbutton = pya.QPushButton('Clean up', self)
        cleanbutton.clicked(self.clearbutton_clicked)

        butbox = pya.QHBoxLayout()
        butbox.addWidget(cleanbutton)
        butbox.addStretch(1)
        butbox.addWidget(showbutton)

        self.setLayout(butbox)

    def showbutton_clicked(self, checked):
        """ Event handler: "Show" button clicked """
        # Clean up from previous show before proceed
        self.delete_aux()
        for lp in self.layers:
            lp.visible = True

        # Starting data collection from layers
        polygons, doses = defaultdict(list), set()
        layit = self.view.begin_layers()
        while not layit.at_end():
            lp = layit.current()
            if lp.visible and lp.valid:
                self.layers.append(lp)
                lp.visible = False
                shape_iter = self.ly.begin_shapes(self.cell, lp.layer_index())
                while not shape_iter.at_end():
                    shape = shape_iter.shape()
                    poly = shape.polygon.transformed(shape_iter.itrans())
                    d = shape.property('dose')
                    # If shape's dose is None, look for closest instance dose in instance path
                    if d is None:
                        instpath = pya.ObjectInstPath(shape_iter, self.view.active_cellview_index())
                        # Using deepest dose in instance hierarchy
                        for i in instpath.each_inst():
                            if i.inst().property('dose') is not None:
                                d = i.inst().property('dose')
                    polygons[str(f'{float(d):.2f}') if d is not None else None].append(poly)
                    if d is not None:
                        doses.add(str(f'{float(d):.2f}'))
                    shape_iter.next()
            layit.next()
        # Create layer and shapes with no dose specified
        if None in polygons.keys():
            linfo = pya.LayerInfo(self.dose_layer, 0, 'doses')
            layer_id = self.ly.insert_layer(linfo)

            ln = pya.LayerPropertiesNode()
            ln.dither_pattern = 2
            ln.width = 1
            ln.fill_color = self.rgb2int(150, 150, 150)
            ln.frame_color = self.rgb2int(0, 0, 0)
            ln.source_layer_index = layer_id
            ln.name = 'no dose'

            self.view.insert_layer(self.view.end_layers(), ln)
            for poly in polygons[None]:
                self.cell.shapes(layer_id).insert(poly)

        # Create layers for each dose and place there corresponding shapes
        for i, dose in enumerate(sorted(doses)):
            linfo = pya.LayerInfo(self.dose_layer, i + 1, 'doses')
            layer_id = self.ly.insert_layer(linfo)

            color = self.rgb2int(255, int(255 * (len(doses) - i) / len(doses)), 0)
            ln = pya.LayerPropertiesNode()
            ln.dither_pattern = 2
            ln.width = 1
            ln.fill_color = color
            ln.frame_color = self.rgb2int(0, 0, 0)
            ln.source_layer_index = layer_id
            ln.name = dose + ' us'

            self.view.insert_layer(self.view.end_layers(), ln)
            for poly in polygons[dose]:
                self.cell.shapes(layer_id).insert(poly).set_property('dose', dose)

    def delete_aux(self):
        """ Event handler: "Clear dose" button clicked """
        # Iteration over layers in LayoutView and delete of layer from Layout
        layit = self.view.begin_layers()
        while not layit.at_end():
            lp = layit.current()
            info = self.ly.get_info(lp.layer_index())
            if info.layer == self.dose_layer:
                self.ly.delete_layer(lp.layer_index())
            layit.next()

        # Delete layers from LayoutView
        self.view.remove_unused_layers()

    def clearbutton_clicked(self, checked):
        """ Event handler: "Clear dose" button clicked """
        self.delete_aux()
        for lp in self.layers:
            lp.visible = True

    @staticmethod
    def rgb2int(r: int, g: int, b: int) -> int:
        return (r << 16) + (g << 8) + b

# Instantiate the dialog and make it visible initially.
# Passing the main_window will make it stay on top of the main window.
dialog = DoseVisualizer(pya.Application.instance().main_window())
dialog.show()
