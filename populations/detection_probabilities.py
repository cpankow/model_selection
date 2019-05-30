#!/usr/bin/env python

"""
Function for incorporating selection effects on a population of binaries.
"""

import os
import numpy as np
import pandas as pd
import h5py
import argparse

from scipy.interpolate import interp1d
from scipy.interpolate import interpn
from scipy.interpolate import griddata

import itertools
import multiprocessing
from functools import partial

import lalsimulation
import lal

import astropy.units as u
from astropy import cosmology
from astropy.cosmology import z_at_value

# import important lal stuff
import lal, lalsimulation
from pycbc.detector import Detector

from utils import selection_effects

cosmo = cosmology.Planck15

_dirpath = '/projects/b1095/michaelzevin/model_selection/second_generation/data/unprocessed/spin_models/'
_outdir = '/projects/b1095/michaelzevin/model_selection/second_generation/data/processed/'

_psd_path = "/projects/b1095/michaelzevin/ligo/PSDs/"
ifos_O3_single = {"H1":"midhighlatelow"}
ifos_O3_network = {"H1":"midhighlatelow",
            "L1":"midhighlatelow",
            "V1":"midhighlatelow"}
ifos_design_single = {"H1":"design"}
ifos_design_network = {"H1":"design",
            "L1":"design",
            "V1":"design"}

_configs = [ifos_O3_single,ifos_O3_network,ifos_design_single,ifos_design_network]
_names = ['pdet_O3','pdet_O3network','pdet_design','pdet_designnetwork']


argp = argparse.ArgumentParser()
argp.add_argument("-m", "--model", type=str, required=True, help="Name of the model you wish to calculate SNR weights for.")
argp.add_argument("-c", "--channel", type=str, required=True, help="Name of the channel you wish to calculate SNR weights for. Must be a key in the model hdf file.")
argp.add_argument("-n", "--Ntrials", type=int, default=1000, help="Define the number of monte carlo trails used for calculating the average SNR. Default=1000")
argp.add_argument("-s", "--snr-min", type=float, default=8, help="Define the SNR threshold for detectability. Default=8")
argp.add_argument("-mp", "--multiproc", type=int, default=1, help="Number of cores you want to use. Default=1")
argp.add_argument("-zm", "--z-max", type=str, default=2.0, help="Maximum redshift value for sampling. Default=2.0")
args = argp.parse_args()


### MAIN FUNCTION ###

print("Calculating weights for model: {0:s}, channel: {1:s}".format(args.model, args.channel))
pop = pd.read_hdf(_dirpath+args.model+'.hdf', key=args.channel)

# if redshifts are not provided, temporarily put Nones there
if 'z' not in pop.keys():
    pop['z'] = None

# --- loop over ifo configurations and sensitivities for calculating different pdet
for ifos, name in zip(_configs,_names):
    print("  configuration {0:s}...".format(name))

    # set up partial functions and organize data for multiprocessing
    systems_info = []

    # set up partial function for multiprocessing
    func = partial(selection_effects.detection_probability, ifos=ifos, rho_det=args.snr_min, z_max=args.z_max, Ntrials=args.Ntrials, psd_path=_psd_path)

    # set up systems for multiprocessing
    for idx, system in pop.iterrows():
        systems_info.append([system['m1'], system['m2'], system['z'], (system['s1x'],system['s1y'],system['s1z']), (system['s2x'],system['s2y'],system['s2z'])])

    if args.multiproc > 1:
        mp = int(args.multiproc)
        pool = multiprocessing.Pool(mp)
        results = pool.map(func, systems_info)
        pool.close()
        pool.join()
    else:
        results = []
        for system in systems_info:
            results.append(func(system))

    results = np.transpose(results)
    weight = results[0]
    z = results[1]

    pop[name] = weight
    pop['z'] = z

# save pop model
pop.to_hdf(_outdir+args.model+'.hdf', key=args.channel)

