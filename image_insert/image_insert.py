import pya
import os
import numpy as np
import cProfile
import pstats
import io
import time
from PIL import Image
from collections import defaultdict

#file name should be delimitered with '_' 
#example Sample_Nice_f3_01_25
image_formats = set(["png", "jpg", "tif", "tiff"])
need_convert = image_formats - set(["png", "jpg"])


class Timer:
    def __init__(self):
        self.start = time.time()
        self.period = 0.1
        self.last_update = self.start - self.period
		
    def update(self):
        self.current = time.time()
        if self.current > self.last_update + self.period:
            pya.QCoreApplication.processEvents()         
            self.last_update = self.current           
	
    def refresh(self):
        self.start = time.time()

    def __str__(self):
        self.current = time.time()
        return "--------------------------- %.2f seconds -------------------------\n" % (self.current - self.start)


def delete_image(path, need_delete):
    if need_delete:
        os.remove(path)
        
            
def find_cross(pic, width, height, pix1, pix2):
    '''
    pix1, pix2 - tuples indicate region of pic in which
    cross should be found
    pix1 < pix2 (both coords)
    '''
    matrix = np.matrix([[pic.get_pixel(i,j) for i in range(pix1[0], pix2[0])] for j in range(pix1[1], pix2[1])])        
    start = []
    end = []
    for row in (matrix.T[1:] - matrix.T[:-1]).T:
        start.append(np.argmax(row))
        end.append(np.argmin(row))
    x = (max(start, key=start.count) + max(end, key=end.count) - width) / 2 + pix1[0] + 1
    start = []
    end = []
    for column in (matrix[1:] - matrix[:-1]).T:
        start.append(np.argmax(column))
        end.append(np.argmin(column))
    y = (max(start, key=start.count) + max(end, key=end.count) - height) / 2 + pix1[1] + 1
    return pya.DPoint(x,y) 

def addpic(path, p1, p2, part, with_annotation, annotation): 
    '''
    p1 - coords of left bottom cross on image (in um)
    p2 - coords of right top cross on image (in um)
    suppose that crosses are vertexes of rectangle
    part - part of image where cross will be looking for
    '''
    p1 = [float(c) for c in p1]
    p2 = [float(c) for c in p2]        
    pic = pya.Image(path)
    width = pic.width()
    height = pic.height()
    d = round(part * max(height, width))
    bot = 0 # bottom indent changes if annotation present
    if with_annotation:
        bot = int(annotation * height)
    # old points
    po1 = find_cross(pic, width, height, (0, height - d), (d, height))
    po2 = find_cross(pic, width, height, (0, bot), (d, bot + d))  
    po3 = find_cross(pic, width, height, (width - d, bot), (width, bot + d))
    po4 = find_cross(pic, width, height, (width - d, height - d), (width, height))
    # new points
    pn1 = pya.DPoint(p1[0], p2[1])
    pn2 = pya.DPoint(p1[0], p1[1])
    pn3 = pya.DPoint(p2[0], p1[1])
    pn4 = pya.DPoint(p2[0], p2[1])
    matrix = pya.Matrix3d()
    matrix.adjust([po1, po2, po3, po4], [pn1, pn2, pn3, pn4], pya.Matrix3d.AdjustAll, -1)
    pic = pic.transformed(matrix)
    pya.Application.instance().main_window().current_view().insert_image(pic)  


def add_images(dirname, offset, macrostep, step, infield_shifts, annotation, with_annotation, multifields, cross_search, outlog, bench=False):
    offset = np.array(offset)
    macrostep = np.array(macrostep)
    step = np.array(step)
    infield_shift_1 = np.array(infield_shifts[0])
    infield_shift_2 = np.array(infield_shifts[1])
    timer = Timer()
    if bench:
        pr = cProfile.Profile()
        pr.enable()
    for i in os.listdir(dirname):
        timer.update()
        path = os.path.join(dirname, i)
        if os.path.isfile(path):       
            parts = i.split('.')
            if parts[-1] not in image_formats:
                continue
            name = ".".join(parts[0:-1]).split('_')
            need_delete = False
            if parts[-1] in need_convert:
                im = Image.open(path)
                dire = os.path.join(path[: - (len(i) + 1)], "inserted")
                if not os.path.exists(dire):
                    os.makedirs(dire)
                path = os.path.join(dire, ".".join(parts[0:-1]) + ".png")
                im.save(path)
                need_delete = True
            try:
                if len(name) > 3 and not multifields:
                    if name[-3][:-1] != "f" and name[-3][:-1] != "F" and name[-3][:-1] != "field":
                        outlog.write("Supposedly auxillary image. Image ", i, " was not inserted.\n")
                        delete_image(path, need_delete)
                        continue 
                    field = int(name[-3][-1])            
                    shift = macrostep * np.array([(field - 1) % 2, (field - 1) // 2])
                    infield_shift = infield_shift_1
                elif len(name) > 4 and multifields:
                    if name[-4][:-1] != "f" and name[-4][:-1] != "F" and name[-4][:-1] != "field":
                        outlog.write("Supposedly auxillary image. Image ", i, " was not inserted.\n")
                        delete_image(path, need_delete)
                        continue  
                    field = int(name[-4][-1])
                    infield = name[-3]
                    shift = macrostep * np.array([(field - 1) % 2, (field - 1) // 2])
                    if infield == 'r':
                        infield_shift = infield_shift_2
                    elif infield == 'l':
                        infield_shift = infield_shift_1
                    else:
                        outlog.write("Wrong filename. Image ", i, " was not inserted.\n")
                        delete_image(path, need_delete)
                        continue            
                else:
                    outlog.write("Wrong filename. Image ", i, " was not inserted.\n")
                    delete_image(path, need_delete)
                    continue
                p1 = np.array(offset + shift + infield_shift + np.array([int(name[-2]) - 1, int(name[-1]) - 1]) * step)
                p2 = p1 + step
                addpic(path, p1, p2, cross_search, with_annotation, annotation)
            except:
                outlog.write("Exception caught. Image ", i, " was not inserted.\n") 
            #delete_image(path, need_delete)     
    
    if bench:
        pr.disable()
        s = io.StringIO()
        sortby = 'cumulative'
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.outlog.write_stats()
        outlog.write(s.getvalue())
