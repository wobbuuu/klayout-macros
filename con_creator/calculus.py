from struct import Struct
from time import time
from os import listdir, remove
from os.path import isfile, join, split
from collections import defaultdict
from cProfile import Profile
from pstats import Stats
from io import StringIO
import pya


class Timer:
    def __init__(self):
        self.start, self.current = time(), time()
        self.period = 0.1
        self.last_update = self.start - self.period

    def update(self):
        self.current = time()
        if self.current > self.last_update + self.period:
            pya.QCoreApplication.processEvents()
            self.last_update = self.current

    def refresh(self):
        self.start = time()

    def __str__(self):
        self.current = time()
        return '---------------------------- %.1f seconds ----------------------------\n' % (self.current - self.start)


class Calculus:
    def __init__(self, ebl, dirname, field, marks, visible, direction, pitch, dose, outlog, field_layer, merge, bench=False):
        self.ebl = ebl
        self.dirname = dirname
        self.field = field
        self.marks = marks
        self.visible = visible
        self.direction = direction
        self.pitch = pitch
        self.dose = dose
        self.outlog = outlog
        self.timer = Timer()
        self.timer.update()
        self.dist = 0.001  # accuracy
        self.squaredist = self.dist ** 2
        self.end_bytes = bytes([0xff, 0xff, 0x13, 0x00] + 34 * [0xcc])
        self.bench = bench
        self.ownfields = []
        self.field_layer = field_layer
        self.merge = merge
        # benchmarking
        if bench:
            self.pr = Profile()
            self.pr.enable()

    def print_stats(self):
        s = StringIO()
        sortby = 'cumulative'
        ps = Stats(self.pr, stream=s).sort_stats(sortby)
        ps.print_stats()
        self.outlog.write(s.getvalue())

    def start(self):
        view = pya.Application.instance().main_window().current_view()
        layit = view.begin_layers()
        cell = view.active_cellview().cell
        ly = view.active_cellview().layout()
        self.dbu = ly.dbu
        self.field.size = int(self.field.size / self.dbu)
        self.field.center[0] = int(self.field.center[0] / self.dbu)
        self.field.center[1] = int(self.field.center[1] / self.dbu)
        # Starting data collection from layers
        self.outlog.write('Collecting data from layers:\n')
        polygons = []
        while not layit.at_end():
            lp = layit.current()
            info = ly.get_info(lp.layer_index())
            name_type = str(info.layer) + '/' + str(info.datatype)
            if ((lp.visible and self.visible) or not self.visible) and lp.valid:
                self.outlog.write(info, '\n')
                shape_iter = ly.begin_shapes(cell, lp.layer_index())
                while not shape_iter.at_end():
                    shape = shape_iter.shape()
                    poly = shape.polygon.transformed(shape_iter.itrans())
                    if name_type != self.field_layer:
                        d = shape.property('dose')
                        # If shape's dose is None, look for closest instance dose in instance path
                        if d is None:
                            instpath = pya.ObjectInstPath(shape_iter, view.active_cellview_index())
                            # Using deepest dose in instance hierarchy
                            for i in instpath.each_inst():
                                if i.inst().property('dose') is not None:
                                    d = i.inst().property('dose')
                        polygons.append((float(d) if d is not None else None, poly))
                    elif name_type == self.field_layer:
                        if not poly.is_box():
                            self.outlog.write('There is a non-box shape on a field layer.\n')
                            shape_iter.next()
                            continue
                        self.ownfields.append(poly.bbox())
                    shape_iter.next()
            self.timer.update()
            layit.next()

        self.timer.update()
        shapes_with_f, amount = self.polygon_division(polygons)
        self.outlog.write(str(self.timer))
        self.outlog.write('There were ', len(polygons), ' polygons. Now there are ', amount,
                          ' polygons in ', len(shapes_with_f.keys()), ' fields.\n')
        self.timer.update()
        if self.ebl == 'cabl':
            self.write_files(shapes_with_f)
        elif self.ebl == 'xenos':
            self.write_pat_ctl(shapes_with_f)
        self.outlog.write(str(self.timer))
        self.outlog.write('End of writing files.\n')

        # end of benchmarking
        if self.bench:
            self.pr.disable()
            self.print_stats()
        return True

    def get_fields(self, shape):
        # return fields (list of pya.Box) where the shape is located
        minimx = int(self.field.center[0] + self.field.size *
                     ((shape.bbox().left - self.field.center[0] - 0.5 * self.field.size) // self.field.size + 0.5))
        maximx = int(self.field.center[0] + self.field.size *
                     ((shape.bbox().right - self.field.center[0] - 0.5 * self.field.size) // self.field.size + 0.5))
        minimy = int(self.field.center[1] + self.field.size *
                     ((shape.bbox().bottom - self.field.center[1] - 0.5 * self.field.size) // self.field.size + 0.5))
        maximy = int(self.field.center[1] + self.field.size *
                     ((shape.bbox().top - self.field.center[1] - 0.5 * self.field.size) // self.field.size + 0.5))
        fields = []
        for x in range(minimx, maximx + 1, self.field.size):
            for y in range(minimy, maximy + 1, self.field.size):
                fields.append(pya.Box(x, y, x + self.field.size, y + self.field.size))
        return fields

    def polygon_division(self, shapes):
        # Firstly all shapes are split into parts according to field boarders
        shapes_fielded = defaultdict(list)
        sections = []
        if self.field_layer == '':
            new_sections = []
            for dose, shape in shapes:
                sections.extend(self.get_fields(shape))
            for sec in sections:
                if sec not in new_sections:
                    new_sections.append(sec)
            sections = new_sections
        else:
            sections = self.ownfields

        for sec in sections:
            if self.merge:
                if shapes_fielded[sec] == []:
                    shapes_fielded[sec] = [[self.dose, []]]
                shapes_fielded[sec][0][1].extend(
                    pya.EdgeProcessor().boolean_p2p([s for _, s in shapes], [sec], pya.EdgeProcessor.ModeAnd, True, True))
            else:
                for i, (dose, shape) in enumerate(shapes):
                    shapes_fielded[sec].append([dose if dose is not None else self.dose, []])
                    shapes_fielded[sec][i][1].extend(
                        pya.EdgeProcessor().boolean_p2p([shape], [sec], pya.EdgeProcessor.ModeAnd, True, True))
            shapes_fielded[sec] = [[dose, polys] for dose, polys in shapes_fielded[sec] if polys != []]
            if not shapes_fielded[sec]:
                shapes_fielded.pop(sec, None)

        # Secondly new shapes are divided into trapezoids, parallelograms and triangles
        amount = 0
        for field in shapes_fielded.keys():
            for i, (dose, polys) in enumerate(shapes_fielded[field]):
                trs = []
                for poly in polys:
                    trs.extend(poly.decompose_trapezoids(pya.Polygon.TD_htrapezoids))
                shapes_fielded[field][i][1] = trs
                amount += len(trs)

        return shapes_fielded, amount

    @staticmethod
    def signed_area(points):
        p1 = points[-1]
        area = 0
        for p2 in points:
            area += (p2[0] - p1[0]) * (p2[1] + p1[1])
            p1 = p2
        return area

    def get_str_bin(self, shape, field, dose):
        coef = self.field.dots / self.field.size
        points = []
        for p in shape.each_point():
            xcord = int((p.x - field.left) * coef)
            ycord = int((field.top - p.y) * coef)
            points.append((xcord, ycord))
        points.append(points[0])
        area = self.signed_area(points)
        if len(points) < 4:
            self.outlog.write('Polygon collapsed due to amount of points. Points: [',
                ', '.join('(%.3f, %.3f)' % (v.x * self.dbu, v.y * self.dbu) for v in shape.each_point()) + ']\n')
            return None, None, None
        elif area == 0:
            self.outlog.write('Polygon collapsed due to zero area. Points: [',
                ', '.join('(%.3f, %.3f)' % (v.x * self.dbu, v.y * self.dbu) for v in shape.each_point()) + ']\n')
            return None, None, None
        min_index, min_value = min(enumerate(points), key=lambda p: (p[1][1], p[1][0]))
        points = points[min_index:] + points[1:min_index + 1]
        if area < 0:
            points = points[::-1]  # reverse

        # next level japanese logic here
        outbinary = [0] * 8
        outbinary[0] = points[0][0]
        outbinary[1] = points[0][1]
        outbinary[6] = points[1][1] - points[0][1]
        try:
            outbinary[3] = (points[1][0] - points[0][0]) / outbinary[6]
            outbinary[2] = points[-2][0] - points[0][0]  # + 1
            if points[-2][1] != points[0][1]:
                outbinary[2] = 1
            outbinary[5] = (points[2][0] - points[1][0] - outbinary[2]) / outbinary[6]
            if points[2][1] != points[1][1]:
                outbinary[5] = (1 - outbinary[2]) / outbinary[6]
        except ZeroDivisionError:
            self.outlog.write('Polygon collapsed by ZeroDivisionError. Points: ', points)
            return None, None, None
        outbinary[6] += 1
        outbinary[4] = self.pitch  # maybe pitch
        outbinary[7] = round(dose * 100)  # dose in us
        s = Struct('< 3i 3f 2i')
        packed_data = s.pack(*outbinary)
        poly_type = 'DWSL'
        if (outbinary[3] != 0 or outbinary[5] != 0) and len(points) == 5:
            poly_type = 'DWTZL'
        elif len(points) == 4:
            poly_type = 'DWTL'

        if poly_type == 'DWSL':
            outstr = str(points[0][0]) + ',' + str(points[0][1]) + ','\
                     + str(points[2][0]) + ',' + str(points[2][1]) + ','
        else:
            outstr = ''
            for p in points[:-1]:
                outstr += str(p[0]) + ',' + str(p[1]) + ','
        return outstr, poly_type, bytes([0x01, 0x08, 0x13, 0x00]) + bytes(self.direction, 'utf-8') + \
            bytes([0x00]) + bytes(packed_data)

    def write_files(self, shapes_with_f):
        for item in listdir(self.dirname):
            path = join(self.dirname, item)
            if isfile(path):
                end = split(item)[-1].lower()
                if len(end) > 3:
                    if end[-3:] == 'con' or end[-3:] == 'ccc' or end[-3:] == 'cbc':
                        remove(path)
        filename = split(self.dirname)[1] + '.con'
        fcon = open(join(self.dirname, filename), 'w')
        fcon.write('/*--- ' + filename + ' ---*/\n')
        cz = 'CZ' + str(round(self.field.size * self.dbu / 1000, 6)) + ',' + str(self.field.dots)
        fcon.write(cz + ';\n')
        if self.marks is not None:
            fcon.write('R2 ' + str(self.marks[0][0]) + ',' + str(self.marks[0][1]) + '; ' +
                       str(self.marks[1][0]) + ',' + str(self.marks[1][1]) + ';\n')
        fields = sorted(shapes_with_f.keys(), key=lambda f: (f.bottom, f.left))
        fname = 'field'
        for i, f in enumerate(fields):
            if i % 20 == 0:
                self.timer.update()
            a = str(round((f.left + f.right) / 2 * self.dbu / 1000, 6))
            b = str(round((f.top + f.bottom) / 2 * self.dbu / 1000, 6))
            fcon.write('PC' + fname + '_' + str(i + 1) + ';\n' + a + ',' + b + ';\n')
            fcon.write('PP' + fname + '_' + str(i + 1) + ';\n' + a + ',' + b + ';\n')

            fccc_name = fname + '_' + str(i + 1) + '.ccc'
            fccc = open(join(self.dirname, fccc_name), 'w')
            fccc.write('/*--- ' + fccc_name + ' ---*/\n')
            fccc.write('/* ' + cz + ' */\n')
            fccc.write('PATTERN\n')

            fcbc_name = fname + '_' + str(i + 1) + '.cbc'
            amount_cc = 24 - len(fcbc_name)  # amount of 0xcc needed after caption
            fcbc = open(join(self.dirname, fcbc_name), 'wb')
            fcbc.write(bytes(fcbc_name + ';1.1;', 'utf-8') + bytes([0x00]) + bytes(amount_cc * [0xcc]))
            for dose, shapes in shapes_with_f[f]:
                for shape in shapes:
                    string, poly_type, binary = self.get_str_bin(shape, f, dose)
                    if poly_type is not None:
                        fccc.write(poly_type + '(' + string + str(self.pitch) + ',' + str(dose) + ');3\n')
                        fcbc.write(binary)
            fccc.write('!END\n')
            fccc.close()
            fcbc.write(self.end_bytes)
            fcbc.close()
        fcon.write('!END\n')
        fcon.close()

    def get_str_pat(self, shape, field, dose):
        coef = self.field.dots / self.field.size
        points = []
        for p in shape.each_point():
            xcord = int((p.x - field.left) * coef)
            ycord = int((p.y - field.bottom) * coef)
            points.append((xcord, ycord))
        points.append(points[0])
        area = self.signed_area(points)
        if len(points) < 4:
            self.outlog.write('Polygon collapsed due to amount of points. Points: [',
                              ', '.join('(%.3f, %.3f)' % (v.x * self.dbu, v.y * self.dbu) for v in
                                        shape.each_point()) + ']\n')
            return None
        elif area == 0:
            self.outlog.write('Polygon collapsed due to zero area. Points: [',
                              ', '.join('(%.3f, %.3f)' % (v.x * self.dbu, v.y * self.dbu) for v in
                                        shape.each_point()) + ']\n')
            return None
        min_index, min_value = min(enumerate(points), key=lambda p: (p[1][1], p[1][0]))

        points = points[min_index:] + points[1:min_index + 1]

        if area < 0:
            points = points[::-1]  # reverse

        if (points[0][0] == points[1][0]) and (points[1][1] == points[2][1]) and \
                (points[2][0] == points[3][0]) and (points[3][1] == points[0][1]):
            outstr = 'RECT ' + \
                     str(points[0][0]) + ', ' + str(points[0][1]) + ', ' + \
                     str(points[2][0]) + ', ' + str(points[2][1])
        elif len(points) == 5:
            outstr = 'XPOLY ' + \
                     str(points[0][0]) + ', ' + str(points[0][1]) + ', ' + \
                     str(points[3][0]) + ', ' + str(points[2][0]) + ', ' + \
                     str(points[1][0]) + ', ' + str(points[1][1])
        else:
            outstr = 'XPOLY ' + \
                     str(points[0][0]) + ', ' + str(points[0][1]) + ', ' + \
                     str(points[2][0]) + ', ' + str(points[1][0]) + ', ' + \
                     str(points[1][0]) + ', ' + str(points[1][1])
        outstr = 'C ' + str(round(dose * 20) * 50) + '\nI ' + str(self.pitch) + '\n' + outstr
        return outstr

    def write_pat_ctl(self, shapes_with_f):
        for item in listdir(self.dirname):
            path = join(self.dirname, item)
            if isfile(path):
                end = split(item)[-1].lower()
                if len(end) > 3:
                    if end[-3:] == 'pat' or end[-3:] == 'ctl':
                        remove(path)
        filename = split(self.dirname)[1]
        fctl = open(join(self.dirname, filename + '.ctl'), 'w')
        fpat = open(join(self.dirname, filename + '.pat'), 'w')
        head = 'origin = 0, 0\ncurrent = 100\n' \
               'fsize = ' + str(round(self.field.size * self.dbu)) + '\n' \
                                                                     'sfile = ' + filename + '\n\n'
        fctl.write(head)
        # if self.marks is not None:
        #     fctl.write('R2 ' + str(self.marks[0][0]) + ',' + str(self.marks[0][1]) + '; ' +
        #                str(self.marks[1][0]) + ',' + str(self.marks[1][1]) + ';\n')
        fields = sorted(shapes_with_f.keys(), key=lambda f: (f.bottom, f.left))
        fname = 'field'
        for i, f in enumerate(fields):
            if i % 20 == 0:
                self.timer.update()
            a = str(round((f.left + f.right) / 2 * self.dbu, 3))
            b = str(round((f.top + f.bottom) / 2 * self.dbu, 3))
            move = 'x = ' + str(round((f.left + f.right) / 2 * self.dbu, 3)) + '\ny = ' + \
                   str(round((f.top + f.bottom) / 2 * self.dbu, 3)) + '\nstage\n'
            fctl.write(move + 'draw(' + fname + str(i) + ')\n\n')
            fpat.write('D ' + fname + str(i) + '\n')
            for dose, shapes in shapes_with_f[f]:
                for shape in shapes:
                    string = self.get_str_pat(shape, f, dose)
                    if string is not None:
                        fpat.write(string + '\n')
            fpat.write('END\n\n')
        fpat.close()
        fctl.write('end\n')
        fctl.close()
