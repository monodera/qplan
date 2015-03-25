import math
import datetime

import ephem

import matplotlib
from matplotlib import rc, figure
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from PyQt4 import QtGui

class AZELPlot(object):

    def __init__(self, width, height, dpi=96):
        # radar green, solid grid lines
        rc('grid', color='#316931', linewidth=1, linestyle='-')
        rc('xtick', labelsize=10)
        rc('ytick', labelsize=10)

        # altitude increments, by degree
        self.alt_inc_deg = 15
        
        # create matplotlib figure
        self.fig = figure.Figure(figsize=(width, height), dpi=dpi)

    def setup(self):
        ax = self.fig.add_axes([0.1, 0.1, 0.8, 0.8],
                               projection='polar', axisbg='#d5de9c')
        self.ax = ax
        #ax.set_title("Slew order", fontsize=14)

    def get_figure(self):
        return self.fig
    
    def get_ax(self):
        return self.ax

    def make_canvas(self):
        canvas = FigureCanvas(self.fig)
        return canvas
        
    def clear(self):
        self.ax.cla()

    def map_azalt(self, az, alt):
        return (math.radians(az), 90.0 - alt)
    
    def orient_plot(self):
        ax = self.ax
        # Orient plot for Subaru telescope
        ax.set_theta_zero_location("S")
        #ax.set_theta_direction(-1)
        ax.set_theta_direction(1)

        # standard polar projection has radial plot running 0 to 90,
        # inside to outside.
        # Adjust radius so it goes 90 at the center to 0 at the perimeter
        #ax.set_ylim(90, 0)   # (doesn't work)

        # Redefine yticks and labels
        #alts = [0, 15, 60, 70, 90]
        alts = range(0, 90, self.alt_inc_deg)
        ax.set_yticks(alts)
        #alts_r = list(alts)
        #alts_r.reverse()
        alts_r = range(90, 0, -self.alt_inc_deg)
        ax.set_yticklabels(map(str, alts_r))
        # maximum altitude of 90.0
        ax.set_rmax(90.0)
        ax.grid(True)

        # add compass annotations
        ## for az, d in ((0.0, 'S'), (90.0, 'W'), (180.0, 'N'), (270.0, 'E')):
        ##     ax.annotate(d, xy=self.map_azalt(az, 0.0), textcoords='data')
        ax.annotate('W', (1.08, 0.5), textcoords='axes fraction',
                    fontsize=16)
        ax.annotate('E', (-0.1, 0.5), textcoords='axes fraction',
                    fontsize=16)
        ax.annotate('N', (0.5, 1.08), textcoords='axes fraction',
                    fontsize=16)
        ax.annotate('S', (0.5, -0.08), textcoords='axes fraction',
                    fontsize=16)

    def plot_coords(self, coords):

        ax = self.ax
        az = map(lambda pt: math.radians(pt[0]), coords)
        # invert the radial axis
        alt = map(lambda pt: (90.0 - pt[1]), coords)
        tgts = map(lambda pt: pt[2], coords)

        ax.plot(az, alt, 'ro-') 

        self.orient_plot()

        for i, txt in enumerate(tgts):
            #ax.annotate(txt, (az[i], alt[i]))
            ax.annotate("%d"%(i+1), (az[i], alt[i]))

        self.fig.canvas.draw()
        
    def plot_azel(self, coords, outfile=None):

        ax = self.ax
        az = map(lambda pt: math.radians(pt[0]), coords)
        # invert the radial axis
        alt = map(lambda pt: (90.0 - pt[1]), coords)
        tgts = map(lambda pt: pt[2], coords)

        ax.plot(az, alt, 'ro-') 

        self.orient_plot()

        for i, txt in enumerate(tgts):
            #ax.annotate(txt, (az[i], alt[i]))
            ax.annotate("%d"%(i+1), (az[i], alt[i]))

        if outfile == None:
            self.canvas = self.make_canvas()
            self.canvas.show()
        else:
            self.canvas = self.make_canvas()
            self.fig.savefig(outfile)

    def plot_moon(self, obs, time_start):
        obs.date = datetime.datetime.utcnow()
        az, el = azel_calc(obs, ephem.Moon())
        self.ax.plot(az, 90.0-el, color='#bf7033')

if __name__ == '__main__':
    app = QtGui.QApplication([])
    plot = AZELPlot(10, 10)
    plot.setup()
    plot.plot_azel([(-210.0, 60.43, "telescope")])
    app.exec_()