#!/usr/bin/env python
"""C 2021 Bence Becsy
MCMC for CW fast likelihood (w/ Neil Cornish and Matthew Digman)"""

import numpy as np
np.seterr(all='raise')
import matplotlib.pyplot as plt
#import corner

import pickle
import argparse

import enterprise
from enterprise.pulsar import Pulsar
import enterprise.signals.parameter as parameter
from enterprise.signals import utils
from enterprise.signals import signal_base
from enterprise.signals import selections
from enterprise.signals.selections import Selection
from enterprise.signals import white_signals
from enterprise.signals import gp_signals
from enterprise.signals import deterministic_signals
import enterprise.constants as const

from enterprise_extensions import deterministic

from holodeck.constants import YR

#import glob
#import json

import QuickCW.QuickCW as QuickCW
from QuickCW.QuickMCMCUtils import ChainParams
#import QuickCW.FastLikelihoodNumba as FastLikelihoodNumba

####################################################################################
#
# Set up argparser
#
####################################################################################
def _setup_argparse():
    parser = argparse.ArgumentParser()
    parser.add_argument('data_pkl', type=str,
                        help='pkl data file path, including filename ending in .pkl')
    parser.add_argument('save_file', type=str,
                        help='save data file path, including filename ending in .h5')
    
    
    parser.add_argument('--noise_file', action='store', dest='noise_file', type=str,
                        default='./data/fake_pta_noisefile.json',
                        help='Name of json file containing white noise dictionary')
    parser.add_argument('--rn_file', action='store', dest='rn_emp_dist_file', type=str,
                        default=None, help='Path to red noise file')
    parser.add_argument('-n', '--n_iter', action='store', dest='n_iterations', type=int,
                        default=5_000_000, help='Total number of MCMC iterations')
    parser.add_argument('--T_max', action='store', dest='T_max', type=float,
                        default=3.0, help='Max temperature in ladder')
    parser.add_argument('--n_chain', action='store', dest='n_chain', type=int,
                        default=4, help='Number of chains in MCMC')
    parser.add_argument('--n_save', action='store', dest='n_save', type=int,
                        default=1, help='Number of chains to save')
    
    parser.add_argument('--fix_rn', action='store_true', dest='fix_rn', 
                        default=False, help='Whether or not to fix red noise')
    parser.add_argument('--zero_rn', action='store_true', dest='zero_rn', 
                        default=False, help='Whether or not to zero red noise')
    parser.add_argument('--fix_gwb', action='store_true', dest='fix_gwb', 
                        default=False, help='Whether or not to fix gwb')
    parser.add_argument('--zero_gwb', action='store_true', dest='zero_gwb', 
                        default=False, help='Whether or not to zero gwb')
    
    parser.add_argument('--exclude_cw', action='store_true', dest='exclude_cw', 
                        default=False, help='Whether or not to exclude a CW in the model')
    parser.add_argument('--freq_max', action='store', dest='freq_max', type=float,
                            default=2.5e-8, help='Maximum CW frequency in Hz')
    parser.add_argument('--freq_min', action='store', dest='freq_min', type=float,
                            default=None, help='Minimum CW frequency in Hz')
    parser.add_argument('--m_max', action='store', dest='m_max', type=float,
                            default=10, help='Maximum log10 chirp mass/M_sun')
    parser.add_argument('--gwb_comps', action='store', dest='gwb_comps', type=int,
                            default=16, help='Number of frequency components to model in the GWB')

    
    args = parser.parse_args()
    return args

args = _setup_argparse()



# make sure this points to the pickled pulsars you want to analyze
data_pkl = args.data_pkl

# whether to include CW in the model
include_cw = False if args.exclude_cw else True

with open(data_pkl, 'rb') as psr_pkl:
    psrs = pickle.load(psr_pkl)

print(len(psrs))

#number of iterations (increase to 100 million - 1 billion for actual analysis)
N = args.n_iterations

n_int_block = 10_000 #number of iterations in a block (which has one shape update and the rest are projection updates)
save_every_n = 100_000 #number of iterations between saving intermediate results (needs to be integer multiple of n_int_block)
N_blocks = np.int64(N//n_int_block) #number of blocks to do
fisher_eig_downsample = 2000 #multiplier for how much less to do more expensive updates to fisher eigendirections for red noise and common parameters compared to diagonal elements

n_status_update = 100 #number of status update printouts (N/n_status_update needs to be an intiger multiple of n_int_block)
n_block_status_update = np.int64(N_blocks//n_status_update) #number of bllocks between status updates

assert N_blocks%n_status_update ==0 #or we won't print status updates
assert N%save_every_n == 0 #or we won't save a complete block
assert N%n_int_block == 0 #or we won't execute the right number of blocks

#Parallel tempering parameters
T_max = args.T_max
n_chain = args.n_chain

#make sure this points to your white noise dictionary
# noisefile = 'data/quickCW_noisedict_kernel_ecorr.json'
noisefile = args.noise_file

#make sure this points to the RN empirical distribution file you plan to use (or set to None to not use empirical distributions)
# rn_emp_dist_file = 'data/emp_dist.pkl'
# rn_emp_dist_file = None
rn_emp_dist_file = args.rn_emp_dist_file

#file containing information about pulsar distances - None means use pulsar distances present in psr objects
#if not None psr objects must have zero distance and unit variance
psr_dist_file = None

#this is where results will be saved
# savefile = 'results/quickCW_test16.h5'
savefile = args.save_file
#savefile = None

if args.freq_min is None:
    freq_min = np.nan
else:
    freq_min = args.freq_min

#Setup and start MCMC
#object containing common parameters for the mcmc chain
chain_params = ChainParams(T_max,n_chain, n_block_status_update,
                        #    freq_bounds=np.array([np.nan, 3e-7]), #prior bounds used on the GW frequency (a lower bound of np.nan is interpreted as 1/T_obs)
                           freq_bounds=np.array([freq_min, args.freq_max]), #prior bounds used on the GW frequency (a lower bound of np.nan is interpreted as 1/T_obs)
                           m_max=args.m_max, # prior upper bound on log10 chirp mass
                           n_int_block=n_int_block, #number of iterations in a block (which has one shape update and the rest are projection updates)
                           save_every_n=save_every_n, #number of iterations between saving intermediate results (needs to be intiger multiple of n_int_block)
                           fisher_eig_downsample=fisher_eig_downsample, #multiplier for how much less to do more expensive updates to fisher eigendirections for red noise and common parameters compared to diagonal elements
                           rn_emp_dist_file=rn_emp_dist_file, #RN empirical distribution file to use (no empirical distribution jumps attempted if set to None)
                           savefile = savefile,#hdf5 file to save to, will not save at all if None
                           thin=100,  #thinning, i.e. save every `thin`th sample to file (increase to higher than one to keep file sizes small)
                           prior_draw_prob=0.2, de_prob=0.6, fisher_prob=0.3, #probability of different jump types
                           dist_jump_weight=0.2, rn_jump_weight=0.3, gwb_jump_weight=0.1, common_jump_weight=0.2, all_jump_weight=0.2, #probability of updating different groups of parameters
                           fix_rn=args.fix_rn, zero_rn=args.zero_rn, fix_gwb=args.fix_gwb, zero_gwb=args.zero_gwb, #switches to turn off GWB or RN jumps and keep them fixed and to set them to practically zero (gamma=0.0, log10_A=-20)
                           includeCW=include_cw, # If False, we are not including the CW in the likelihood (good for testing) [True]
                           gwb_comps=args.gwb_comps, #  Number of frequency components to model in the GWB [14]
                           save_first_n_chains=args.n_save) 

pta,mcc = QuickCW.QuickCW(chain_params, psrs,
                                  amplitude_prior='detection', #specify amplitude prior to use - 'detection':uniform in log-amplitude, 'UL': uniform in amplitude
                                  psr_distance_file=psr_dist_file, #file to specify advanced (parallax+DM) pulsar distance priors, if None use regular Gaussian priors based on pulsar distances in pulsar objects
                                  noise_json=noisefile,
                                  include_ecorr=False, backend_selection=False)

#Some parameters in chain_params can be updated later if needed
# mcc.chain_params.thin = 10 # for 10_000_000 run
thin = int(N/1_000_000)
print(f"{thin=}")
mcc.chain_params.thin = thin

#Do the main MCMC iteration
mcc.advance_N_blocks(N_blocks)
