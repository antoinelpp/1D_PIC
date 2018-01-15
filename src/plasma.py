

import numpy as np
import scipy as sp
import astropy

from imp import reload
from functions import generate_maxw, velocity_maxw_flux
from numba import jit

me = 9.109e-31; #[kg] electron mass
q = 1.6021765650e-19; #[C] electron charge
kb = 1.3806488e-23;  #Blozman constant
eps_0 = 8.8548782e-12; #Vaccum permitivitty
mi = 131*1.6726219e-27 #[kg]


class plasma:
    """a class with fields, parts, and method to pass from one to the other"""



    def __init__(self,dT,Nx,Lx,Npart,n,Te,Ti):

        from .particles import particles as particles

        self.Lx = Lx
        self.Nx = Nx
        self.dT = dT
        self.qf = n*self.Lx/(Npart)
        self.ele = particles(Npart,Te,me,self)
        self.ion = particles(Npart,Ti,mi,self)

        self.E = np.zeros((Nx+1,3))
        self.phi = np.zeros(Nx+1)
        self.ne = np.zeros((Nx+1))
        self.ni = np.zeros((Nx+1))
        self.rho = np.zeros((Nx+1))

        self.history = {'Ie_w' : [],
                        'Ii_w' : [],
                        'Ie_c' : [],
                        'Ii_c' : []
                        }

        self.x_j = np.arange(0,Nx+1, dtype='float64')*self.Lx/(Nx)
        self.dx = self.x_j[1]

    def pusher(self):
        """push the particles"""
        from scipy import interpolate

        Einterpol = [interpolate.interp1d(self.x_j,self.E[:,i]) for i in [0,1,2]]

        for sign,part in zip([-1,1],[self.ele,self.ion]):

            for i in [0,1,2]:
                #fast calculation
                try:
                    vectE = Einterpol[i](part.x)
                    part.V[:,i] -= sign*q/part.m*self.dT*vectE
                except:
                    print(part.x,max(part.x),min(part.x),part.V[:,0],self.Lx)
                    raise ValueError

            part.x += part.V[:,0] *self.dT


    def boundary(self):
        """look at the postition of the particle, and remove them if they are outside"""

        #mirror reflexion
        for key, part in zip(['Ie_w','Ii_w'],[self.ele,self.ion]):
            mask = part.x > self.Lx
            part.x[mask] = self.Lx - (part.x[mask] - self.Lx)
            part.V[mask,0] *= -1

            self.history[key].append(np.count_nonzero(mask==1))

        for key, part in zip(['Ie_c','Ii_c'],[self.ele,self.ion]):
            mask = part.x >0
            part.x = part.x[mask]
            part.V = part.V[mask,:]

            self.history[key].append(np.count_nonzero(mask==0))

        #self.inject_particles(self.history['Ie_w'][-1],self.history['Ii_w'][-1])

        self.inject_particles(self.history['Ie_c'][-1],self.history['Ii_c'][-1])


    def inject_particles(self,Ne,Ni):
        """inject particle with maxwellian distribution uniformely in the system"""

        #Would be better to add an array of particle, not a single one
        self.ele.add_uniform_vect(Ne)

        self.ion.add_uniform_vect(Ni)

    def inject_flux(self,Ne,Ni):
        """inject particle with maxwellian distribution uniformely in the system"""

        #Would be better to add an array of particle, not a single one
        self.ele.add_flux_vect(Ne)
        self.ion.add_flux_vect(Ni)


    def compute_rho(self):
        """Compute the plasma density via the invers aera method"""

        self.ne = self.ele.return_density(self.x_j)
        self.ni = self.ion.return_density(self.x_j)

        self.ni /= self.dx**2*self.qf
        self.ne /= self.dx**2*self.qf
        self.rho = self.ni - self.ne
        self.rho *= q


    def solve_poisson(self):
        """solve poisson via the Thomas method :

        TO VALIDATE !!!!


        A Phi = -rho/eps0

        """
        try:
            self.bi
        except:
            self.bi = - np.ones(self.Nx+1, dtype = 'float')
            self.bi[1:-1] *= 2

            [self.ai, self.ci ]= np.ones((2,self.Nx+1), dtype = 'float')
            self.ci[[0,-1]] = 0.
            self.ai[0] = 0.


            ciprim = np.copy(self.ci) #copy the value, not the reference
            ciprim[0] /= self.bi[0]
            for i in np.arange(1,len(ciprim)):
                ciprim[i] /= self.bi[i] - self.ai[i]*ciprim[i-1]

            self.ciprim = ciprim

        self.rho[[0,-1]] = 0
        di = - self.rho.copy()/eps_0

        diprim = di.copy()   #copy the values, not the reference
        diprim[0] /= self.bi[0]

        for i in np.arange(1,len(diprim)):
            diprim[i] -= self.ai[i]*diprim[i-1]
            diprim[i] /= self.bi[i] - self.ai[i]*self.ciprim[i-1]

        self.phi[:] = 0
        self.phi[-1] = diprim[-1]
        #limit conditions

        for i in np.arange(self.Nx-1,1,-1):
            self.phi[i] = diprim[i] - self.ciprim[i]*self.phi[i+1]

        self.phi *= self.dx**2/q
#        #Poisson finished

        self.E[:,0] = - np.gradient(self.phi, self.dx)
