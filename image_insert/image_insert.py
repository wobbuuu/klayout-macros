import pya
import os
import numpy as np 
import pandas as pd

dirname = "/home"

df = pd.read_csv(os.path.join(dirname, "info.csv"), header=None)
for i, row in df.iterrows():
    pic = pya.Image(row.iloc[0])
    old_pts = [pya.DPoint(*row.iloc[1:3]), pya.DPoint(*row.iloc[3:5]), pya.DPoint(*row.iloc[5:7]), pya.DPoint(*row.iloc[7:9])]
    new_pts = [pya.DPoint(*row.iloc[9:11]), pya.DPoint(*row.iloc[11:13]), pya.DPoint(*row.iloc[13:15]), pya.DPoint(*row.iloc[15:17])]
    matrix = pya.Matrix3d()
    matrix.adjust(old_pts, new_pts, pya.Matrix3d.AdjustAll, -1)
    pic = pic.transformed(matrix)
    pya.Application.instance().main_window().current_view().insert_image(pic) 