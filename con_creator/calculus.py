from struct import Struct
from time import time
from os import listdir, remove
from os.path import isfile, join, split
from collections import defaultdict
from cProfile import Profile
from pstats import Stats
from io import StringIO
from pya import DSimplePolygon, Application, QCoreApplication
from shapely.geometry import Polygon, LineString, Point, mapping
from shapely import speedups


class Timer:
    def __init__(self):
        self.start = time()
        self.period = 0.1
        self.last_update = self.start - self.period
		
    def update(self):
        self.current = time()
        if self.current > self.last_update + self.period:
            QCoreApplication.processEvents()         
            self.last_update = self.current           
	
    def refresh(self):
        self.start = time()

    def __str__(self):
        self.current = time()
        return "--------------------------- %.2f seconds -------------------------\n" % (self.current - self.start)


class Calculus:
    def __init__(self, dirname, field, marks, visible, direction, pitch, dose, outlog, field_layer, bench=False):
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
        self.dist = 0.001  # accurancy
        self.squaredist = self.dist ** 2
        self.end_bytes = bytes([0xff, 0xff, 0x13, 0x00] + 34 * [0xcc])
        self.bench = bench
        self.ownfields = []
        self.field_layer = field_layer
        #benchmarking
        speedups.enable()
        if bench:
            self.pr = Profile()
            self.pr.enable()           

    def print_stats(self):
        s = StringIO()
        sortby = 'cumulative'
        ps = Stats(self.pr, stream=s).sort_stats(sortby)
        ps.print_stats()
        self.outlog.write(s.getvalue())   
    
    def get_poly(self, fig, current, dbu, dict_minmax):
        fig = fig.to_simple_polygon()
        fig = DSimplePolygon.from_ipoly(fig) * dbu  # coordinates of polygons in microns (double)
        set_x = set()
        set_y = set()
        points = []
        for p in fig.each_point():
            points.append((p.x, p.y))
            set_x.update([p.x])
            set_y.update([p.y])
        if len(set_x) < 2 and len(set_y) < 2:
            self.outlog.write("Not a polygon, skipping.\n")
            return None
        dict_minmax[current] = (min(set_x), min(set_y), max(set_x), max(set_y))
        poly = Polygon(points)
        if not poly.is_valid:
            poly = poly.buffer(0)
        return poly
           
    def start(self):    
        layit = Application.instance().main_window().current_view().begin_layers()
        cell = Application.instance().main_window().current_view().active_cellview().cell
        ly = Application.instance().main_window().current_view().active_cellview().layout()
        dbu = ly.dbu          
        
        #Starting collecting data from layers
        self.outlog.write("Collecting data from layers:\n")    
        dict_minmax = dict()    
        polygons = []        
        current = 0
        while not layit.at_end():
            lp = layit.current()
            print(lp.layer_index())
            info = ly.get_info(lp.layer_index())
            if ((lp.visible and self.visible) or not self.visible) and lp.valid:
                self.outlog.write(info, "\n")
                shape_iter = ly.begin_shapes(cell, lp.layer_index())
                while (not shape_iter.at_end()):
                    shape = shape_iter.shape()
                    poly = self.get_poly(shape.polygon.transformed(shape_iter.itrans()), current, dbu, dict_minmax)
                    if poly != None  and (str(info) != self.field_layer):
                        polygons.append(poly)
                        current += 1
                    elif poly != None  and (str(info) == self.field_layer):
                        self.ownfields.append(poly)
                        current += 1
                    shape_iter.next()
            layit.next()        
        self.timer.update()               
        shapes_with_f, amount = self.polygon_division(polygons, dict_minmax) 
        self.outlog.write(str(self.timer))    
        self.outlog.write("There were ", len(polygons), " polygons. Now there are ", amount, " polygons in ", len(shapes_with_f.keys()), " fields.\n")
        self.timer.update()        
        self.write_files(shapes_with_f)    
        self.outlog.write(str(self.timer)) 
        self.outlog.write("End of writing files.\n")
        
        #end of bechmarking
        if self.bench:
            self.pr.disable()    
            self.print_stats(pr)
        return True

    def get_field(self, point):
        if self.field_layer == "":
            return (self.field.center[0] + self.field.size * ((point[0]  - self.field.center[0] + self.field.size / 2) // self.field.size),\
            self.field.center[1] + self.field.size * ((point[1]  - self.field.center[1] + self.field.size / 2) // self.field.size))
        else:
            for f in self.ownfields:
                if f.intersects(Point(point[0], point[1])):
                    return (f.centroid.x, f.centroid.y)
            self.outlog.write("There is a part of object outside field.", '\n')
            return None

    def getpoint(self, shape):
        cords = list(shape.exterior.coords.xy)
        p0 = [cords[0][0], cords[1][0]]
        for p in cords[1:]:
            if p[0] != p0[0] and p[1] != p0[1]:
                return ((p0[0] + p[0]) / 2, (p0[1] + p[1]) / 2)                           
                    
    def cut_by_edge(self, shapes, sections): 
        out = [] 
        for shape_index, sectiones in sections.items():        
            shapes_iter = [shapes[shape_index]]
            if sectiones != []:
                for section in sectiones:
                    self.timer.update()
                    new_shapes = []            
                    for shape in shapes_iter:
                        section_pol = section.buffer(1e-8)
                        new_polygons = shape.difference(section_pol)
                        if new_polygons.geom_type != "Polygon":
                            new_shapes.extend(new_polygons)
                        else:
                            new_shapes.append(shape)
                    shapes_iter = new_shapes
                out.extend(new_shapes)
            else:
                out.append(shapes[shape_index])         
        return out

    def polygon_division(self, shapes, dict_minmax):    
        #firsly we have to divide all shapes into pieces if field net crosses shape
        sections = defaultdict(list)
        last_index = 0
        new_shapes = []
        for shape_index, shape in enumerate(shapes):
            if self.field_layer == "":
                sections[shape_index] = []
                minimx = dict_minmax[shape_index][0]
                maximx = dict_minmax[shape_index][2]
                minimy = dict_minmax[shape_index][1]
                maximy = dict_minmax[shape_index][3]
                fmin = self.get_field((minimx, minimy))
                fmax = self.get_field((maximx, maximy))
                for y in range(int((fmax[1] - fmin[1]) / self.field.size)):
                    sections[shape_index].append(LineString([(minimx - self.dist, (y + 0.5) * self.field.size + fmin[1]),\
                     (maximx + self.dist, (y + 0.5) * self.field.size + fmin[1])]))
                for x in range(int((fmax[0] - fmin[0]) / self.field.size)):
                    sections[shape_index].append(LineString([((x + 0.5) * self.field.size + fmin[0], minimy - self.dist),\
                     ((x + 0.5) * self.field.size + fmin[0], maximy + self.dist)]))        
            else:
                sec_set = []
                k = False
                for f in self.ownfields:
                    if f.intersects(shape):
                        bounds = f.bounds
                        sec_set.append(LineString([(bounds[0], bounds[1]), (bounds[0], bounds[3])]))
                        sec_set.append(LineString([(bounds[0], bounds[1]), (bounds[2], bounds[1])]))
                        sec_set.append(LineString([(bounds[2], bounds[3]), (bounds[0], bounds[3])]))
                        sec_set.append(LineString([(bounds[2], bounds[3]), (bounds[2], bounds[1])]))
                        k = True
                if k:
                    new_shapes.append(shape)
                    sections[last_index] = sec_set
                    last_index += 1

        if self.field_layer == "":
            new_shapes = shapes
        shapes = self.cut_by_edge(new_shapes, sections)
        
        #secondly new shapes have to be divided into trapezoids parallelograms and triangles
        dict_x = dict()
        dict_y = dict()
        dict_minmax = dict() 
        for i,shape in enumerate(shapes):
            set_x = set()
            set_y = set() 
            #dividing figure by horisontal or vertical lines made in vertexes' y positions
            for countour in mapping(shape)['coordinates']:
                for p in countour:
                    set_x.update([p[0]])
                    set_y.update([p[1]])
            dict_minmax[i] = (min(set_x), min(set_y), max(set_x), max(set_y))
            dict_x[i] = set_x - set([min(set_x), max(set_x)])
            dict_y[i] = set_y - set([min(set_y), max(set_y)])    
        
        sections = defaultdict(list)
        if self.direction == 'x':
            for shape_index, set_y in dict_y.items():
                minimx = dict_minmax[shape_index][0]
                maximx = dict_minmax[shape_index][2]
                for y in set_y:
                    linx = LineString([(minimx - self.dist, y), (maximx + self.dist, y)])
                    sections[shape_index].append(linx)
                if not set_y:
                    sections[shape_index] = []
        elif self.direction == 'y':
            for shape_index, set_x in dict_x.items():
                minimy = dict_minmax[shape_index][1]
                maximy = dict_minmax[shape_index][3]
                for x in set_x:
                    liny = LineString([(x, minimy - self.dist), (x, maximy + self.dist)])
                    sections[shape_index].append(liny)
                if not set_x:
                    sections[shape_index] = []
        shapes = self.cut_by_edge(shapes, sections)
        
        #finally we need to refer each shape to corresponding field
        shapes_with_f = defaultdict(list)
        amount = len(shapes)
        for shape in shapes:
            if len(shape.interiors) != 0:
                self.outlog.write("Polygon with hole eventiolly created, creation stopped. This is bug.")
                self.outlog.write("Coordinates of hull:", cords)
                raise Exception
            cords = list(shape.exterior.coords.xy)
            ps_for_f = []
            for i in range(3):
                ps_for_f.append([cords[0][i], cords[1][i]])  # need 3 point of polygon to get field
            inside_p = [0, 0]
            p_prev = ps_for_f[-1]
            perim = 0
            for p in ps_for_f:
                side = ((p[0] - p_prev[0]) ** 2 + (p[1] - p_prev[1]) ** 2) ** 0.5
                inside_p[0] += side * p_prev[0]
                inside_p[1] += side * p_prev[1]
                perim += side
                p_prev = p
            inside_p = [inside_p[0] / perim, inside_p[1] / perim] # incenter of triangle based on first 3 points of shape
            shapes_with_f[self.get_field(inside_p)].append(shape)
        if None in shapes_with_f.keys():
            nones = shapes_with_f.pop(None)
            amount -= len(nones)
        return shapes_with_f, amount
        
    def myround(self, num):
        if num < 0.5:
            return 0
        string = str(num)
        a = string.split('.')
        if a[1] != "":
            if a[1][0] > '4':
                return int(a[0]) + 1
        return int(a[0])

    def signed_area(self, points):
        p1 = points[-1]
        area = 0 
        for p2 in points:
            area += (p2[0] - p1[0]) * (p2[1] + p1[1])
            p1 = p2
        return area            
            
    def get_str_bin(self, shape, field):    
        coef = self.field.dots / self.field.size
        x,y = shape.exterior.coords.xy
        points = []
        for i,p in enumerate(zip(x,y)):
            xcord = self.myround((round(p[0], 3) - field[0] + self.field.size / 2) * coef)
            ycord = self.myround((field[1] + self.field.size / 2 - round(p[1],3)) * coef)
            point = (xcord, ycord)
            if i == 0:
                points.append(point)
            elif point != points[-1]:
                points.append(point)
        area = self.signed_area(points)
        if len(points) < 4:
            self.outlog.write("Polygon collapsed by amount of points. Points: ", '[' + ', '.join('(%.3f, %.3f)' % (v[0], v[1]) for v in zip(x,y)) + ']\n')
            return None, None, None
        elif area == 0:
            self.outlog.write("Polygon collapsed by zero area. Points: ", '[' + ', '.join('(%.3f, %.3f)' % (v[0], v[1]) for v in zip(x,y)) + ']\n')
            return None, None, None
        min_index, min_value = min(enumerate(points), key=lambda p: (p[1][1], p[1][0]))       
        points = points[min_index:] + points[1:min_index + 1]
        if area < 0:
            points = points[::-1]  #reverse

        #next level japanese logic here
        outbinary = [0] * 8
        outbinary[0] = points[0][0]
        outbinary[1] = points[0][1]
        outbinary[6] = points[1][1] - points[0][1]
        try:
            outbinary[3] = (points[1][0] - points[0][0]) / outbinary[6]
            outbinary[2] = points[-2][0] - points[0][0]# + 1
            if points[-2][1] != points[0][1]:
                outbinary[2] = 1
            outbinary[5] = (points[2][0] - points[1][0] - outbinary[2]) / outbinary[6]
            if points[2][1] != points[1][1]:
                outbinary[5] = (1 - outbinary[2]) / outbinary[6]
        except ZeroDivisionError:
            self.outlog.write("Polygon collapsed by ZeroDivisionError. Points: ", points)
            return None, None, None
        outbinary[6] += 1
        outbinary[4] = self.pitch  #maybe pitch
        outbinary[7] = self.myround(self.dose * 100)  #dose in us
        s = Struct('< 3i 3f 2i')
        packed_data = s.pack(*outbinary)        
        poly_type = "DWSL"
        if (outbinary[3] != 0 or outbinary[5] != 0) and len(points) == 5:
            poly_type = "DWTZL"
        elif len(points) == 4:
            poly_type = "DWTL"
            
        if poly_type == "DWSL":
            outstr = str(points[0][0]) + "," + str(points[0][1]) + "," + str(points[2][0]) + "," + str(points[2][1]) + ","
        else:
            outstr = ""
            for p in points[:-1]:
                outstr += str(p[0]) + "," + str(p[1]) + ","      
        return outstr, poly_type, bytes([0x01, 0x08, 0x13, 0x00]) + bytes(self.direction, 'utf-8') + bytes([0x00]) + bytes(packed_data)

    def write_files(self, shapes_with_f):        
        for item in listdir(self.dirname):
            path = join(self.dirname, item)
            if isfile(path):       
                end = split(item)[-1].lower()
                if len(end) > 3:
                    if end[-3:] == "con" or end[-3:] == "ccc" or end[-3:] == "cbc":
                        remove(path)                
        filename = split(self.dirname)[1] + ".con"
        fcon = open(join(self.dirname, filename), 'w')
        fcon.write("/*--- " +  filename + " ---*/\n")
        cz = "CZ" + str(self.field.size / 1000) + "," + str(self.field.dots)
        fcon.write(cz + ";\n")
        if self.marks != None:
            fcon.write("R2 " + str(self.marks[0][0]) + "," + str(self.marks[0][1]) + "; "+ str(self.marks[1][0]) + ","+ str(self.marks[1][1]) + ";\n")
        fields = sorted(shapes_with_f.keys(), key=lambda f: (f[1], f[0]))
        fname = "field"
        for i,f in enumerate(fields):
            fcon.write("PC" + fname + "_" + str(i + 1) + ";\n" + str(f[0] / 1000) + "," + str(f[1] / 1000) + ";\n") 
            fcon.write("PP" + fname + "_" + str(i + 1) + ";\n" + str(f[0] / 1000) + "," + str(f[1] / 1000) + ";\n")
            
            fccc_name = fname + "_" + str(i + 1) + ".ccc"
            fccc = open(join(self.dirname, fccc_name), 'w')
            fccc.write("/*--- " + fccc_name + " ---*/\n")
            fccc.write("/* " + cz + " */\n")
            fccc.write("PATTERN\n")        
            
            fcbc_name = fname + "_" + str(i + 1) + ".cbc"
            amount_cc = 24 - len(fcbc_name)  #amount of 0xcc needed after caption  
            fcbc = open(join(self.dirname, fcbc_name), 'wb')
            fcbc.write(bytes(fcbc_name + ";1.1;", 'utf-8') + bytes([0x00]) + bytes(amount_cc * [0xcc]))
            for shape in shapes_with_f[f]:
                string, poly_type, binary = self.get_str_bin(shape, f)
                if poly_type != None:
                    fccc.write(poly_type + "(" + string + str(self.pitch) + "," + str(self.dose) + ");3\n")
                    fcbc.write(binary)
            fccc.write("!END\n")
            fccc.close()
            fcbc.write(self.end_bytes)
            fcbc.close()
        fcon.write("!END\n")
        fcon.close()
