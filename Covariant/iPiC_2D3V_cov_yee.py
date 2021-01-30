"""
Fully Implicit, Covariant Particle-in-Cell - 2D3V Electromagnetic - 2 species
Authors: G. Lapenta, F. Bacchini, L. Pezzini
Date: 30 Gen 2021
Copyright 2020 KULeuven
MIT License.
"""

import numpy as np
from scipy.optimize import newton_krylov
from numpy import cosh, zeros_like, mgrid, zeros
import matplotlib.pyplot as plt
import sys

# parameters
nx, ny = 16, 16
nxc, nyc = nx, ny
nxn, nyn = nxc+1, nyc+1
Lx, Ly = 4.,4.
dx, dy = Lx/nxc, Ly/nyc
dt = 0.05
nt = 30

# grid of centres C
xc, yc = mgrid[dx/2.:Lx-dx/2.:(nxc*1j), dy/2.:Ly-dy/2.:(nyc*1j)]
# grid of left-right faces LR
xLR, yLR = mgrid[0.:Lx:(nxn*1j), dy/2.:Ly-dy/2.:(nyc*1j)]
# grid of up-down faces UD
xUD, yUD = mgrid[dx/2.:Lx-dx/2.:(nxc*1j), 0.:Ly:(nyn*1j)]
# grid of corners N
xn, yn = mgrid[0.:Lx:(nxn*1j), 0.:Ly:(nyn*1j)]

# defined on grid LR:        Ex, Jx, By
# defined on grid UD:        Ey, Jy, Bx
# defined on grid centres c: Ez, Jz, rho
# defined on grid corners n: Bz
Ex = zeros(np.shape(xLR),np.float64)
Ey = zeros(np.shape(xUD),np.float64)
Ez = zeros(np.shape(xc),np.float64)
Bx = zeros(np.shape(xUD),np.float64)
By = zeros(np.shape(xLR),np.float64)
Bz = zeros(np.shape(xn),np.float64)

# defined on grid LR:        (g11, g21, g31)[nx, ny, 0] 
#                            (g12, g22, g32)[nx, ny, 1]
# defined on grid UD:        (g12, g22, g32)[nx, ny, 0] 
#                            (g11, g21, g31)[nx, ny, 1]
# defined on grid centres c: (g12, g23, g33)[nx, ny, 0]
# defined on grid corners n: (g12, g23, g33)[nx, ny, 1]
J_UD = np.ones(np.shape(xUD), np.float64)
J_LR = np.ones(np.shape(xLR), np.float64)
J_c  = np.ones(np.shape(xc), np.float64)
J_n  = np.ones(np.shape(xn), np.float64)

g11e = np.ones(np.shape(xLR), np.float64)
g12e = np.zeros(np.shape(xUD), np.float64)
g13e = np.zeros(np.shape(xc), np.float64)
g21e = np.zeros(np.shape(xLR), np.float64)
g22e = np.ones(np.shape(xUD), np.float64)
g23e = np.zeros(np.shape(xc), np.float64)
g31e = np.zeros(np.shape(xLR), np.float64)
g32e = np.zeros(np.shape(xUD), np.float64)
g33e = np.ones(np.shape(xc), np.float64)

g11b = np.ones(np.shape(xUD), np.float64)
g12b = np.zeros(np.shape(xLR), np.float64)
g13b = np.zeros(np.shape(xn), np.float64)
g21b = np.zeros(np.shape(xUD), np.float64)
g22b = np.ones(np.shape(xLR), np.float64)
g23b = np.zeros(np.shape(xn), np.float64)
g31b = np.zeros(np.shape(xUD), np.float64)
g32b = np.zeros(np.shape(xLR), np.float64)
g33b = np.ones(np.shape(xn), np.float64)

relativistic = False

# Species 1
npart1 = 1024
WP1 = 1. # Plasma frequency
QM1 = -1. # Charge/mass ratio
V0x1 = 1. # Stream velocity
V0y1 = 1. # Stream velocity
V0z1 = 1. # Stream velocity
VT1 = 0.01 # thermal velocity
# Species 2
npart2 = npart1
WP2 = 1. # Plasma frequency
QM2 = -1. # Charge/mass ratio
V0x2 = 1. # Stream velocity
V0y2 = 1. # Stream velocity
V0z2 = 1. # Stream velocity
VT2 = 0.01 # thermal velocity

npart = npart1+npart2
QM = zeros(npart,np.float64)
QM[0:npart1] = QM1
QM[npart1:npart] = QM2

def avgC2N(fieldC):
    ''' To average a 2D field defined on centres to the nodes
    '''
    global nx,ny

    fieldN = zeros((nx,ny),np.float64)

    fieldN[1:nx-1,1:ny-1] = (fieldC[0:nx-2,0:ny-2]+fieldC[1:nx-1,0:ny-2]
                             +fieldC[0:nx-2,1:ny-1]+fieldC[1:nx-1,1:ny-1])/4.
    fieldN[0,1:ny-1] = (fieldC[0,0:ny-2]+fieldC[0,1:ny-1]+fieldC[nx-2,0:ny-2]+fieldC[nx-2,1:ny-1])/4.
    fieldN[nx-1,1:ny-1] = fieldN[0,1:ny-1]
    fieldN[1:nx-1,0] = (fieldC[0:nx-2,0]+fieldC[1:nx-1,0]+fieldC[0:nx-2,ny-2]+fieldC[1:nx-1,ny-2])/4.
    fieldN[1:nx-1,ny-1] = fieldN[1:nx-1,0]
    fieldN[0,0] = (fieldC[0,0]+fieldC[0,ny-2]+fieldC[nx-2,0]+fieldC[nx-2,ny-2])/4.
    fieldN[0,ny-1] = fieldN[0,0]
    fieldN[nx-1,0] = fieldN[0,0]
    fieldN[nx-1,ny-1] = fieldN[0,0]
    return fieldN

def avg(field, avgtype):
    ''' To take the average of a quantity
        avgtype defines input/output grid type and direction
    '''
    global nxn, nyn, nxc, nyc, dx, dy

    if avgtype == 'C2UD':  # centres to UD faces, y-average
      avgfield = zeros((nxc, nyn), np.float64)

      avgfield[0:nxc, 1:nyn-1] = (field[0:nxc, 1:nyc]+field[0:nxc, 0:nyc-1])/2.
      avgfield[0:nxc, 0] = (field[0:nxc, 0]+field[0:nxc, nyc-1])/2.
      avgfield[0:nxc, nyn-1] = avgfield[0:nxc, 0]

    elif avgtype == 'C2LR':  # centres to LR faces, x-average
      avgfield = zeros((nxn, nyc), np.float64)

      avgfield[1:nxn-1, 0:nyc] = (field[1:nxc, 0:nyc]+field[0:nxc-1, 0:nyc])/2.
      avgfield[0, 0:nyc] = (field[0, 0:nyc]+field[nxc-1, 0:nyc])/2.
      avgfield[nxn-1, 0:nyc] = avgfield[0, 0:nyc]

    elif avgtype == 'UD2N':  # UD faces to nodes, x-average
      avgfield = zeros((nxn, nyn), np.float64)

      avgfield[1:nxn-1, 0:nyn] = (field[1:nxc, 0:nyn]+field[0:nxc-1, 0:nyn])/2.
      avgfield[0, 0:nyn] = (field[0, 0:nyn]+field[nxc-1, 0:nyn])/2.
      avgfield[nxn-1, 0:nyn] = avgfield[0, 0:nyn]

    elif avgtype == 'LR2N':  # LR faces to nodes, y-average
      avgfield = zeros((nxn, nyn), np.float64)

      avgfield[0:nxn, 1:nyn-1] = (field[0:nxn, 1:nyc]+field[0:nxn, 0:nyc-1])/2.
      avgfield[0:nxn, 0] = (field[0:nxn, 0]+field[0:nxn, nyc-1])/2.
      avgfield[0:nxn, nyn-1] = avgfield[0:nxn, 0]

    elif avgtype == 'N2LR':  # nodes to LR faces, y-average
      avgfield = zeros((nxn, nyc), np.float64)

      avgfield[0:nxn, 0:nyc] = (field[0:nxn, 1:nyn]+field[0:nxn, 0:nyn-1])/2.

    elif avgtype == 'N2UD':  # nodes to UD faces, x-average
      avgfield = zeros((nxc, nyn), np.float64)

      avgfield[0:nxc, 0:nyn] = (field[1:nxn, 0:nyn]+field[0:nxn-1, 0:nyn])/2.

    elif avgtype == 'LR2C':  # LR faces to centres, x-average
      avgfield = zeros((nxc, nyc), np.float64)

      avgfield[0:nxc, 0:nyc] = (field[1:nxn, 0:nyc]+field[0:nxn-1, 0:nyc])/2.

    elif avgtype == 'UD2C':  # UD faces to centres, y-average
      avgfield = zeros((nxc, nyc), np.float64)

      avgfield[0:nxc, 0:nyc] = (field[0:nxc, 1:nyn]+field[0:nxc, 0:nyn-1])/2.

    return avgfield

def curl(fieldx,fieldy,fieldz,fieldtype):
    ''' To take the curl of either E or B
    fieltype=='E': input -> LR,UD,C, output -> UD,LR,N
    fieltype=='B': input -> UD,LR,N, output -> LR,UD,C
    '''
    if fieldtype=='E':
      curl_x =   (dirder(avg(g31e * fieldx, 'LR2C'), 'C2UD') + dirder(avg(g32e * fieldy, 'UD2C'), 'C2UD') + dirder(g33e * fieldz, 'C2UD'))/J_UD
      curl_y = - (dirder(avg(g31e * fieldx, 'LR2C'), 'C2LR') + dirder(avg(g32e * fieldy, 'UD2C'), 'C2LR') + dirder(g33e * fieldz, 'C2LR'))/J_LR
      curl_z = (dirder(avg(avg(g21e * fieldx, 'LR2C'),'C2UD'), 'UD2N') + dirder(g22e * fieldy, 'UD2N') + dirder(avg(g13e * fieldz, 'C2UD'), 'UD2N')
              - dirder(g11e * fieldx, 'LR2N') + dirder(avg(avg(g12e * fieldy, 'UD2C'), 'C2LR'), 'LR2N') + dirder(avg(g13e * fieldz, 'C2LR'), 'LR2N'))/J_n

    else:
      curl_x=   (dirder(avg(g31b * fieldx, 'UD2N'), 'N2LR') + dirder(avg(g32b * fieldy, 'LR2N'), 'N2LR') + dirder(g33b * fieldz, 'N2LR'))/J_LR
      curl_y= - (dirder(avg(g31b * fieldx, 'UD2N'), 'N2UD') + dirder(avg(g32b * fieldy, 'LR2N'), 'N2UD') + dirder(g33b * fieldz, 'N2UD'))/J_UD
      curl_z=   (dirder(avg(avg(g21b * fieldx, 'UD2N'), 'N2LR'), 'LR2C') + dirder(g22b * fieldy, 'LR2C') + dirder(avg(g13b * fieldz, 'N2LR'), 'LR2C')
              - dirder(g11b * fieldx, 'UD2C') + dirder(avg(avg(g12b * fieldy, 'LR2N'), 'N2UD'), 'UD2C') + dirder(avg(g13b * fieldz, 'N2UD'), 'UD2C'))/J_c

    return curl_x, curl_y, curl_z

def dirder(field,dertype):
    ''' To take the directional derivative of a quantity
        dertype defines input/output grid type and direction
    '''
    global nxn,nyn,nxc,nyc,dx,dy

    if dertype=='C2UD': # centres to UD faces, y-derivative
      derfield = zeros((nxc,nyn),np.float64)

      derfield[0:nxc,1:nyn-1] = (field[0:nxc,1:nyc]-field[0:nxc,0:nyc-1])/dy
      derfield[0:nxc,0] = (field[0:nxc,0]-field[0:nxc,nyc-1])/dy
      derfield[0:nxc,nyn-1] = derfield[0:nxc,0]

    elif dertype=='C2LR': # centres to LR faces, x-derivative
      derfield = zeros((nxn,nyc),np.float64)

      derfield[1:nxn-1,0:nyc] = (field[1:nxc,0:nyc]-field[0:nxc-1,0:nyc])/dx
      derfield[0,0:nyc] = (field[0,0:nyc]-field[nxc-1,0:nyc])/dx
      derfield[nxn-1,0:nyc] = derfield[0,0:nyc]

    elif dertype=='UD2N': # UD faces to nodes, x-derivative
      derfield = zeros((nxn,nyn),np.float64)

      derfield[1:nxn-1,0:nyn] = (field[1:nxc,0:nyn]-field[0:nxc-1,0:nyn])/dx
      derfield[0,0:nyn] = (field[0,0:nyn]-field[nxc-1,0:nyn])/dx
      derfield[nxn-1,0:nyn] = derfield[0,0:nyn]

    elif dertype=='LR2N': # LR faces to nodes, y-derivative
      derfield = zeros((nxn,nyn),np.float64)

      derfield[0:nxn,1:nyn-1] = (field[0:nxn,1:nyc]-field[0:nxn,0:nyc-1])/dy
      derfield[0:nxn,0] = (field[0:nxn,0]-field[0:nxn,nyc-1])/dy
      derfield[0:nxn,nyn-1] = derfield[0:nxn,0]

    elif dertype=='N2LR': # nodes to LR faces, y-derivative
      derfield = zeros((nxn,nyc),np.float64)

      derfield[0:nxn,0:nyc] = (field[0:nxn,1:nyn]-field[0:nxn,0:nyn-1])/dy

    elif dertype=='N2UD': # nodes to UD faces, x-derivative
      derfield = zeros((nxc,nyn),np.float64)

      derfield[0:nxc,0:nyn] = (field[1:nxn,0:nyn]-field[0:nxn-1,0:nyn])/dx

    elif dertype=='LR2C': # LR faces to centres, x-derivative
      derfield = zeros((nxc,nyc),np.float64)

      derfield[0:nxc,0:nyc] = (field[1:nxn,0:nyc]-field[0:nxn-1,0:nyc])/dx
      
    elif dertype=='UD2C': # UD faces to centres, y-derivative
      derfield = zeros((nxc,nyc),np.float64)

      derfield[0:nxc,0:nyc] = (field[0:nxc,1:nyn]-field[0:nxc,0:nyn-1])/dy

    return derfield

def phys_to_krylov(Exk,Eyk,Ezk,uk,vk,wk):
    ''' To populate the Krylov vector using physiscs vectors
    Ex,Ey,Ez are 2D arrays
    u,v,w of dimensions npart
    '''
    global nxc,nyc,nxn,nyn,npart

    ykrylov = zeros(nxn*nyc+nxc*nyn+nxc*nyc+3*npart,np.float64)
    ykrylov[0:nxn*nyc] = Exk.reshape(nxn*nyc)
    ykrylov[nxn*nyc:nxn*nyc+nxc*nyn] = Eyk.reshape(nxc*nyn)
    ykrylov[nxn*nyc+nxc*nyn:nxn*nyc+nxc*nyn+nxc*nyc] = Ezk.reshape(nxc*nyc)
    ykrylov[nxn*nyc+nxc*nyn+nxc*nyc:nxn*nyc+nxc*nyn+nxc*nyc+npart] = uk
    ykrylov[nxn*nyc+nxc*nyn+nxc*nyc+npart:nxn*nyc+nxc*nyn+nxc*nyc+2*npart] = vk
    ykrylov[nxn*nyc+nxc*nyn+nxc*nyc+2*npart:nxn*nyc+nxc*nyn+nxc*nyc+3*npart] = wk
    return ykrylov

def krylov_to_phys(xkrylov):
    ''' To populate the physiscs vectors using the Krylov space vector
    Ex,Ey,Ez are 2D arrays of dimension (nx,ny)
    unew,vnew,wnew of dimensions npart1+npart2
    '''
    global nx,ny,npart

    Exk = np.reshape(xkrylov[0:nxn*nyc],(nxn,nyc))
    Eyk = np.reshape(xkrylov[nxn*nyc:nxn*nyc+nxc*nyn],(nxc,nyn))
    Ezk = np.reshape(xkrylov[nxn*nyc+nxc*nyn:nxn*nyc+nxc*nyn+nxc*nyc],(nxc,nyc))
    uk = xkrylov[nxn*nyc+nxc*nyn+nxc*nyc:nxn*nyc+nxc*nyn+nxc*nyc+npart]
    vk = xkrylov[nxn*nyc+nxc*nyn+nxc*nyc+npart:nxn*nyc+nxc*nyn+nxc*nyc+2*npart]
    wk = xkrylov[nxn*nyc+nxc*nyn+nxc*nyc+2*npart:nxn*nyc+nxc*nyn+nxc*nyc+3*npart]
    return Exk, Eyk, Ezk, uk, vk, wk

def residual(xkrylov):
    ''' Calculation of the residual of the equations
    This is the most important part: the definition of the problem
    '''

    global Ex,Ey,Ez,Bx,By,Bz,u,v,w,QM,q,npart,dt

    Exnew, Eynew, Eznew, unew, vnew, wnew = krylov_to_phys(xkrylov)
    
    ubar = (u+unew)/2.
    vbar = (v+vnew)/2.
    wbar = (w+wnew)/2.

    if relativistic:
      gold = np.sqrt(1.+u**2+v**2+w**2)
      gnew = np.sqrt(1.+unew**2+vnew**2+wnew**2)
      gbar = (gold+gnew)/2.
    else:
     gbar = np.ones(npart)

    xbar = x + ubar/gbar*dt/2.
    ybar = y + vbar/gbar*dt/2.
    xbar = xbar%Lx
    ybar = ybar%Ly
    
    Jx, Jy, Jz = particle_to_grid_J(xbar,ybar,ubar/gbar,vbar/gbar,wbar/gbar,q)

    Exbar = (Exnew+Ex)/2.
    Eybar = (Eynew+Ey)/2.
    Ezbar = (Eznew+Ez)/2.
    curlE_x, curlE_y, curlE_z = curl(Exbar,Eybar,Ezbar,'E')
    Bxbar = Bx - dt/2.*curlE_x
    Bybar = By - dt/2.*curlE_y
    Bzbar = Bz - dt/2.*curlE_z

    curlB_x, curlB_y, curlB_z = curl(Bxbar,Bybar,Bzbar,'B')

    resEx = Exnew - Ex - dt*curlB_x + dt*Jx
    resEy = Eynew - Ey - dt*curlB_y + dt*Jy
    resEz = Eznew - Ez - dt*curlB_z + dt*Jz
    
    Exp = grid_to_particle(xbar,ybar,Exbar,'LR')
    Eyp = grid_to_particle(xbar,ybar,Eybar,'UD')
    Ezp = grid_to_particle(xbar,ybar,Ezbar,'C')
    Bxp = grid_to_particle(xbar,ybar,Bxbar,'UD')
    Byp = grid_to_particle(xbar,ybar,Bybar,'LR')
    Bzp = grid_to_particle(xbar,ybar,Bzbar,'N')

    resu = unew - u - QM * (Exp + vbar/gbar*Bzp - wbar/gbar*Byp)*dt
    resv = vnew - v - QM * (Eyp - ubar/gbar*Bzp + wbar/gbar*Bxp)*dt
    resw = wnew - w - QM * (Ezp + ubar/gbar*Byp - vbar/gbar*Bxp)*dt

    ykrylov = phys_to_krylov(resEx,resEy,resEz,resu,resv,resw)
    return  ykrylov

def grid_to_particle(xk,yk,f,gridtype):
    ''' Interpolation of grid quantity to particle
    '''
    global dx, dy, nx, ny, npart
    
    fp = zeros(npart,np.float64)

    fx, fy = 0., 0.
    if gridtype=='LR':
      fy = dy/2.
    elif gridtype=='UD':
      fx = dx/2.
    elif gridtype=='C':
      fx, fy = dx/2., dy/2.

    for i in range(npart):

      #  interpolate field f from grid to particle */
      xa = (xk[i]-fx)/dx
      ya = (yk[i]-fy)/dy
      i1 = int(np.floor(xa))
      i2 = i1 + 1
      j1 = int(np.floor(ya))
      j2 = j1 + 1 
      wx2 = xa - np.float64(i1)
      wx1 = 1.0 - wx2
      wy2 = ya - np.float64(j1)
      wy1 = 1.0 - wy2
      if gridtype=='LR':
        j1, j2 = j1%nyc, j2%nyc
      elif gridtype=='UD':
        i1, i2 = i1%nxc, i2%nxc
      elif gridtype=='C':
        i1, i2 = i1%nxc, i2%nxc
        j1, j2 = j1%nyc, j2%nyc

      fp[i] = wx1* wy1 * f[i1,j1] + wx2* wy1 * f[i2,j1] + wx1* wy2 * f[i1,j2] + wx2* wy2 * f[i2,j2]
    
    return fp

def particle_to_grid_J(xk,yk,uk,vk,wk,qk): 
    ''' Interpolation particle to grid - current
    ''' 
    global dx, dy, nxc, nyc, nxn, nyn, npart
  
    Jx = zeros(np.shape(xLR),np.float64)
    Jy = zeros(np.shape(xUD),np.float64)
    Jz = zeros(np.shape(xc),np.float64)
    for i in range(npart):

      #  interpolate p -> LR
      xa = xk[i]/dx 
      ya = (yk[i]-dy/2.)/dy
      i1 = int(np.floor(xa))
      i2 = i1 + 1
      if i2==nxn-1:
        i2=0
      j1 = int(np.floor(ya))
      j2 = j1 + 1  
      wx2 = xa - np.float64(i1)
      wx1 = 1.0 - wx2
      wy2 = ya - np.float64(j1)
      wy1 = 1.0 - wy2
      j1, j2 = j1%nyc, j2%nyc

      Jx[i1,j1] += wx1* wy1 * qk[i] * uk[i]/dx/dy
      Jx[i2,j1] += wx2* wy1 * qk[i] * uk[i]/dx/dy
      Jx[i1,j2] += wx1* wy2 * qk[i] * uk[i]/dx/dy
      Jx[i2,j2] += wx2* wy2 * qk[i] * uk[i]/dx/dy

      # interpolate p -> UD
      xa = (xk[i]-dx/2.)/dx 
      ya = yk[i]/dy
      i1 = int(np.floor(xa))
      i2 = i1 + 1
      j1 = int(np.floor(ya))
      j2 = j1 + 1  
      if j2==nyn-1:
        j2=0
      wx2 = xa - np.float64(i1)
      wx1 = 1.0 - wx2
      wy2 = ya - np.float64(j1)
      wy1 = 1.0 - wy2
      i1, i2 = i1%nxc, i2%nxc

      Jy[i1,j1] += wx1* wy1 * qk[i] * vk[i]/dx/dy
      Jy[i2,j1] += wx2* wy1 * qk[i] * vk[i]/dx/dy
      Jy[i1,j2] += wx1* wy2 * qk[i] * vk[i]/dx/dy
      Jy[i2,j2] += wx2* wy2 * qk[i] * vk[i]/dx/dy

      # interpolate p -> c
      xa = (xk[i]-dx/2.)/dx 
      ya = (yk[i]-dy/2.)/dy
      i1 = int(np.floor(xa))
      i2 = i1 + 1
      j1 = int(np.floor(ya))
      j2 = j1 + 1  
      wx2 = xa - np.float64(i1)
      wx1 = 1.0 - wx2
      wy2 = ya - np.float64(j1)
      wy1 = 1.0 - wy2
      i1, i2 = i1%nxc, i2%nxc
      j1, j2 = j1%nyc, j2%nyc

      Jz[i1,j1] += wx1* wy1 * qk[i] * wk[i]/dx/dy
      Jz[i2,j1] += wx2* wy1 * qk[i] * wk[i]/dx/dy
      Jz[i1,j2] += wx1* wy2 * qk[i] * wk[i]/dx/dy
      Jz[i2,j2] += wx2* wy2 * qk[i] * wk[i]/dx/dy

    Jx[nxn-1,:] = Jx[0,:]
    Jy[:,nyn-1] = Jy[:,0]

    return Jx, Jy, Jz

# initialize particles
np.random.seed(1)

dxp = Lx/np.sqrt(npart1)
dyp = Ly/np.sqrt(npart1)
xp,yp = mgrid[dxp/2.:Lx-dxp/2.:(np.sqrt(npart1)*1j), dyp/2.:Ly-dyp/2.:(np.sqrt(npart1)*1j)]

x = zeros(npart,np.float64)
x[0:npart1] = xp.reshape(npart1)
#x[0:npart1] = Lx*np.random.rand(npart1)
x[npart1:npart] = x[0:npart1]
y = zeros(npart,np.float64)
y[0:npart1] = yp.reshape(npart1)
#y[0:npart1] = Ly*np.random.rand(npart1)
y[npart1:npart] = y[0:npart1]
u = zeros(npart,np.float64)
u[0:npart1] = V0x1+VT1*np.random.randn(npart1)
u[npart1:npart] = V0x2+VT2*np.random.randn(npart2)
v = zeros(npart,np.float64)
v[0:npart1] = V0y1+VT1*np.random.randn(npart1)
v[npart1:npart] = V0y2+VT2*np.random.randn(npart2)
w = zeros(npart,np.float64)
w[0:npart1] = V0z1+VT1*np.random.randn(npart1)
w[npart1:npart] = V0z2+VT2*np.random.randn(npart2)
q = zeros(npart,np.float64)
q[0:npart1] = np.ones(npart1) * WP1**2 / (QM1*npart1/Lx/Ly)
q[npart1:npart] = np.ones(npart2) * WP2**2 / (QM2*npart2/Lx/Ly)
if relativistic:
  g = 1./np.sqrt(1.-(u**2+v**2+w**2))
  u = u*g
  v = v*g
  w = w*g

# main cycle
if relativistic:
  histEnergyP1=[np.sum((g[0:npart1]-1.)*abs(q[0:npart1]/QM[0:npart1]))]
  histEnergyP2=[np.sum((g[npart1:npart]-1.)*abs(q[npart1:npart]/QM[npart1:npart]))]
else:
  histEnergyP1=[np.sum((u[0:npart1]**2+v[0:npart1]**2+w[0:npart1]**2)/2.*abs(q[0:npart1]/QM[0:npart1]))]
  histEnergyP2=[np.sum((u[npart1:npart]**2+v[npart1:npart]**2+w[npart1:npart]**2)/2.*abs(q[npart1:npart]/QM[npart1:npart]))]

histEnergyEx=[np.sum(Ex[0:nxn-1,:]**2)/2.*dx*dy]
histEnergyEy=[np.sum(Ey[:,0:nyn-1]**2)/2.*dx*dy]
histEnergyEz=[np.sum(Ez[:,:]**2)/2.*dx*dy]
histEnergyBx=[np.sum(Bx[:,0:nyn-1]**2)/2.*dx*dy]
histEnergyBy=[np.sum(By[0:nxn-1,:]**2)/2.*dx*dy]
histEnergyBz=[np.sum(Bz[0:nxn-1,0:nyn-1]**2)/2.*dx*dy]

histEnergyTot=[histEnergyP1[0]+histEnergyP2[0]+
               histEnergyEx[0]+histEnergyEy[0]+histEnergyEz[0]+
               histEnergyBx[0]+histEnergyBy[0]+histEnergyBz[0]]

print('cycle 0, energy =',histEnergyTot[0])
print('energyP1 =',histEnergyP1[0],'energyP2=',histEnergyP2[0])
print('energyEx=',histEnergyEx[0],'energyEy=',histEnergyEy[0],'energyEz=',histEnergyEz[0])
print('energyBx=',histEnergyBx[0],'energyBy=',histEnergyBy[0],'energyBz=',histEnergyBz[0])

for it in range(1,nt+1):
    plt.clf()
    guess = phys_to_krylov(Ex,Ey,Ez,u,v,w) 
#     guess = zeros(3*nx*ny+3*npart,np.float64)

    # Uncomment the following to use python's NK methods
#    sol = newton_krylov(residual, guess, method='lgmres', verbose=1, f_tol=1e-14)#, f_rtol=1e-7)
#    print('Residual: %g' % abs(residual(sol)).max())
    
    # The following is a Picard iteration
    err = 1.
    tol = 1e-14
    kmax = 100
    k=0
    xkrylov = guess
    while err > tol and k<=kmax:
      k+=1
      xkold = xkrylov
      xkrylov = xkrylov - residual(xkrylov)
      err = np.linalg.norm(xkrylov-xkold)
      print(k, err)

    sol = xkrylov
    Exnew, Eynew, Eznew, unew, vnew, wnew = krylov_to_phys(sol)
    if relativistic:
      gnew = np.sqrt(1.+unew**2+vnew**2+wnew**2)
      gold = np.sqrt(1.+u**2+v**2+w**2)
      gbar = (gold+gnew)/2.
    else:
      gbar = np.ones(npart)

    ubar = (unew + u)/2.
    vbar = (vnew + v)/2.
    x += ubar/gbar*dt
    y += vbar/gbar*dt
    x = x%Lx
    y = y%Ly
    u = unew
    v = vnew
    w = wnew

    Exbar = (Exnew+Ex)/2.
    Eybar = (Eynew+Ey)/2.
    Ezbar = (Eznew+Ez)/2.
    curlE_x, curlE_y, curlE_z = curl(Exbar,Eybar,Ezbar,'E')
    Bx = Bx - dt*curlE_x
    By = By - dt*curlE_y
    Bz = Bz - dt*curlE_z
    Ex = Exnew
    Ey = Eynew
    Ez = Eznew

    if relativistic:
      energyP1 = np.sum((gnew[0:npart1]-1.)*abs(q[0:npart1]/QM[0:npart1]))
      energyP2 = np.sum((gnew[npart1:npart]-1.)*abs(q[npart1:npart]/QM[npart1:npart]))
    else:
      energyP1 = np.sum((u[0:npart1]**2+v[0:npart1]**2+w[0:npart1]**2)/2.*abs(q[0:npart1]/QM[0:npart1]))
      energyP2 = np.sum((u[npart1:npart]**2+v[npart1:npart]**2+w[npart1:npart]**2)/2.*abs(q[npart1:npart]/QM[npart1:npart]))

    energyEx=np.sum(Ex[0:nxn-1,:]**2)/2.*dx*dy
    energyEy=np.sum(Ey[:,0:nyn-1]**2)/2.*dx*dy
    energyEz=np.sum(Ez[:,:]**2)/2.*dx*dy
    energyBx=np.sum(Bx[:,0:nyn-1]**2)/2.*dx*dy
    energyBy=np.sum(By[0:nxn-1,:]**2)/2.*dx*dy
    energyBz=np.sum(Bz[0:nxn-1,0:nyn-1]**2)/2.*dx*dy
    energyTot = energyP1+energyP2+energyEx+energyEy+energyEz+energyBx+energyBy+energyBz
    histEnergyP1.append(energyP1)
    histEnergyP2.append(energyP2)
    histEnergyEx.append(energyEx)
    histEnergyEy.append(energyEy)
    histEnergyEz.append(energyEz)
    histEnergyBx.append(energyBx)
    histEnergyBy.append(energyBy)
    histEnergyBz.append(energyBz)
    histEnergyTot.append(energyTot)
    print('cycle',it,'energy =',histEnergyTot[it])
    print('energyP1 =',histEnergyP1[it],'energyP2=',histEnergyP2[it])
    print('energyEx=',histEnergyEx[it],'energyEy=',histEnergyEy[it],'energyEz=',histEnergyEz[it])
    print('energyBx=',histEnergyBx[it],'energyBy=',histEnergyBy[it],'energyBz=',histEnergyBz[it])
    plt.subplot(2, 3, 1)
    plt.pcolor(xLR, yLR, Ex)
    plt.colorbar()
    plt.subplot(2, 3, 2)
    plt.pcolor(xUD, yUD, Ey)
    plt.colorbar()
    plt.subplot(2, 3, 3)
    plt.pcolor(xc, yc, Ez)
    plt.colorbar()
    plt.subplot(2, 3, 4)
    plt.plot(x[0:npart1],y[0:npart1],'r.')
    plt.plot(x[npart1:npart],y[npart1:npart],'b.')
    plt.xlim((0,Lx))
    plt.ylim((0,Ly))
#    plt.subplot(2,2,3)
#    plt.plot(histEnergy)
    plt.subplot(2, 3, 5)
    plt.plot((histEnergyTot-histEnergyTot[0])/histEnergyTot[0])
    print('relative energy change=',(histEnergyTot[it]-histEnergyTot[0])/histEnergyTot[0])
#    plt.show()
    plt.pause(0.000000000000001)
    
# visualize