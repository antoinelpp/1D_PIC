import sys
sys.path.append("../..")

import numpy as np
import astropy

import matplotlib.pyplot as plt


import pic
from pic.plasma import plasma
from pic.particles import particles
from pic.functions import (generate_maxw, velocity_maxw_flux, max_vect, fux_vect,
                           numba_return_density, smooth)
from pic.constantes import (me, q, kb, eps_0, mi)

from pic.gui import LivePlot

import pickle

# parameters
Lx = 1e-2  # System length
dX = 5e-6  # dX in m
Nx = int(Lx/dX)  # cell number
Lx = Nx*dX
print("Nx = {Nx}, and Lx = {Lx} cm".format(Nx=Nx, Lx=Lx*100))

Npart = 100*Nx  # particles number, calculated via particle par cell
n = 3e17    # [m^-3]
dT = 1e-12  # time step
Nt = int(6e-6/dT)  # number of iteration
Te_0 = 50   # [eV] Electron distribution temperature
Ti_0 = 1    # [eV]

pla = plasma(dT, Nx, Lx, Npart, n, Te_0, Ti_0, n_average=2000, n_0=0)

petitevalue = 1e-5
phi_max = -3*Te_0
shapefactor = 0.1
# pla.phi = 1/(shapefactor*pla.x_j+petitevalue) - 1/(
#     - petitevalue + shapefactor*(pla.x_j - pla.x_j[-1]))
pla.phi = (pla.x_j-pla.x_j[int(len(pla.x_j)/2)])**2

pla.phi /= abs(pla.phi).max()
pla.phi *= phi_max
pla.E[:, 0] = - np.gradient(pla.phi, pla.dx)
if False:
    plt.plot(pla.x_j, pla.phi)
    plt.show()


pla.Do_diags = True
pla.n_0 = 0  # int(Nt/2)

doPlots = True
restartFileName = "cases/inft_sh/restart_pla.dat"
#  _______   ______       __        ______     ______   .______     _______.
# |       \ /  __  \     |  |      /  __  \   /  __  \  |   _  \   /       |
# |  .--.  |  |  |  |    |  |     |  |  |  | |  |  |  | |  |_)  | |   (----`
# |  |  |  |  |  |  |    |  |     |  |  |  | |  |  |  | |   ___/   \   \
# |  '--'  |  `--'  |    |  `----.|  `--'  | |  `--'  | |  |   .----)   |
# |_______/ \______/     |_______| \______/   \______/  | _|   |_______/
#

tabstr = ["phi", "Te",  "ne", "ve", "Qe", "hist"]
if doPlots:
    vtab = np.linspace(pla.ele.V[:, 0].min(),
                       pla.ele.V[:, 0].max(), 500)
    PlotObject = LivePlot(pla.x_j, vtab, tabstr)

    limites = {'phi': [phi_max, 200],
               # "ni": [0, 4.5e17],
               "ne": [0, 5*n],
               "Te": [0, 50],
               "ve": [-0.5e7, 0.5e7],
               "hist": [0, 1],
               "Qe": [-2e7, 2e7],
               }
    for ax, st in zip(PlotObject.axarr[:-1], tabstr[:-1]):
        ax.set_ylim(*limites[st])
    plt.show()

dataFileName = pla.create_filename("cases/inft_sh/center_parabol", "h5")

pla.ele.x[:] = float(pla.x_j[int(Nx/2)]) + (
    np.random.rand(pla.ele.x.size,)-0.5)*Lx/4
print(pla.ele.x.mean())
pla.ion.x[:] = float(pla.x_j[int(Nx/2)])

PlotObject.axarr[-1].set_xlim([pla.ele.V[:, 0].min(), pla.ele.V[:, 0].max()])

pla.ele.remove_parts(-5)  # remove all elecs
pla.ele.add_uniform_vect(0)  # add just 1k elecs

for nt in np.arange(Nt):
    Nelec = pla.ele.Npart - pla.ele.compt_out
    if Nelec < Npart:
        pla.ele.add_uniform_vect(10)

    pla.pusher()
    pla.boundary(absorbtion=True, injection=True)
    pla.compute_rho()
    # pla.solve_poisson()
    pla.diags(nt)

    if np.mod(nt - pla.n_0 + 1, pla.n_average) == 0:
        if nt < 20*pla.n_average and nt > 19*pla.n_average:
            pass  # PlotObject.axarr[-1].plot(vtab, pla.data[pla.lastkey]["hist"], "k")

        toopen = True if nt < pla.n_average else False
        pla.save_data_HDF5(dataFileName, True)

        # try:
        if doPlots:
            PlotObject.updatevalue(pla.data[pla.lastkey], nt, Nt, dT)
        # except:
            # print(len(pla.x_j),len(pla.data[pla.lastkey]["phi"]),len(pla.data[pla.lastkey]["ni"]),len(pla.data[pla.lastkey]["ne"]))

        print("\r t = {:2.5f} over {:2.5f} mu s, with {:2.2e} elecs".format(
            nt*pla.dT*1e6, Nt*pla.dT*1e6, pla.ele.Npart - pla.ele.compt_out), end="")

        if np.mod(nt - pla.n_0 + 1, 100*pla.n_average) == 0:
            pickle.dump(pla, open(restartFileName, 'wb'))

        pla.f.close()
