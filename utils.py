import torch
from torchvision import datasets, transforms
import matplotlib.pyplot as plt
import numpy as np
from scipy import io
from scipy import stats
import os
import IPython as IP



def import_data(root, file_name, batch_size=1):
    '''
    Will load NEURAL + DECODING sig (EMG/KIN) from .mat file with data stored in matrix form.
    '''
    data = io.loadmat(root + file_name)

    # Make directories to save files
    save_dir = root + 'PredResuls/'
    if not (os.path.isdir(save_dir)):
        os.mkdir(save_dir)

    animal_dir_save = (save_dir + file_name[:-4] + '/') # -4 to get rid of .mat extension
    if not (os.path.isdir(animal_dir_save)):
        os.mkdir(animal_dir_save)

    return data

'''
Define target decoding DATA & SIGNAL
'''
def define_decoding_data(data, neural_sig, decoding_sig, signal, decoding_labels):
    decoding_sig = decoding_sig    # Name of decoding Sig ('EMG/KIN')
    neural_dat = data[neural_sig]
    dec_sig_dat = data[decoding_sig][:,signal]
    if decoding_labels:
        sigs_labels = data[decoding_labels][0][signal]   # Labels

    return neural_dat, dec_sig_dat, sigs_labels

'''
Prepare data to feed into TCN.
Returns Neural data as [Samples * Channels * Seq_length], Dec_signal [Samples * Seq_length]
'''
def prepare_TCN_data(neural_sig, dec_sig, seq_length):
    # +1 Because the last neural data point counts for the same time prediction
    samples = neural_sig.shape[0] - seq_length +1
    channels = neural_sig.shape[1]

    reshaped_neural_sig = np.zeros([samples, seq_length, channels])
    for i in xrange(neural_sig.shape[0] - seq_length + 1):
        reshaped_neural_sig[i] = neural_sig[ i:i+seq_length, :]
    # Decoding signal responds to the 'seq_length' previous neural data bins
    reshaped_decoding_sig = dec_sig[seq_length-1 :]

    return reshaped_neural_sig, reshaped_decoding_sig