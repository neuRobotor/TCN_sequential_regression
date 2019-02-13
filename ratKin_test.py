import torch
from torch.autograd import Variable
import torch.optim as optim
import torch.nn.functional as F
import sys
from utils import *
from model import TCN
import numpy as np
import argparse
import os

import IPython as IP

parser = argparse.ArgumentParser(description='Sequence Regression - Rat Kinematic Data')
parser.add_argument('--batch_size', type=int, default=1, metavar='N',
                    help='batch size (default: 1)')
parser.add_argument('--cuda', action='store_false',
                    help='use CUDA (default: False)')
parser.add_argument('--dropout', type=float, default=0.05,
                    help='dropout applied to layers (default: 0.05)')
parser.add_argument('--clip', type=float, default=-1,
                    help='gradient clip, -1 means no clip (default: -1)')
parser.add_argument('--epochs', type=int, default=6,
                    help='upper epoch limit (default: 6)')
parser.add_argument('--ksize', type=int, default=7,
                    help='kernel size (default: 7)')
parser.add_argument('--levels', type=int, default=8,
                    help='# of levels (default: 8)')
parser.add_argument('--log-interval', type=int, default=100, metavar='N',
                    help='report interval (default: 100')
parser.add_argument('--lr', type=float, default=2e-3,
                    help='initial learning rate (default: 2e-3)')
parser.add_argument('--optim', type=str, default='Adam',
                    help='optimizer to use (default: Adam)')
parser.add_argument('--nhid', type=int, default=25,
                    help='number of hidden units per layer (default: 25)')
parser.add_argument('--seed', type=int, default=1111,
                    help='random seed (default: 1111)')
parser.add_argument('--permute', action='store_true',
                    help='use permuted MNIST (default: false)')
args = parser.parse_args()

torch.manual_seed(args.seed)
if not torch.cuda.is_available():
    if args.cuda:
        print("WARNING: You do not have a CUDA device, changing to run model without --cuda")
        args.cuda = False

print(args)

############################################################
# IMPORT DATA
data_dir = os.getcwd() + '/data/'
file_name = 'N5_171016_NoObstacles_s_matrices.mat'

## DATA variables:
neural_sig = 'APdat'            # Name of neural data
decoding_sig = 'KINdat'         # Usually: 'EMGdat' / 'KINdat' (!!string)
decoding_labels = 'KINlabels'   # Usually: 'EMGlabels' / 'KINlabels' (!!string) -> Leave as Empty string otherwise
signal = 3                      # EMG/Kinematic column to decode (FCR,FCU,ECR etc.)
train_prop = 0.90               # Percentage of training data
seq_length = 50                 # Num bins to look at before

data = import_data(data_dir, file_name)
neural_dat, dec_dat, dec_label = define_decoding_data(data, neural_sig, decoding_sig, signal, decoding_labels)


############################################################
'''Prepare data for TCN.
Then we split it into train and test data'''

# Prepare data to feed into TCN:

tcn_x, tcn_y = prepare_TCN_data(neural_dat, dec_dat, seq_length)
# Reshape as (N, channels, sample_length)
tcn_x = tcn_x.transpose(0,2,1)
# Create torch Float Tensors
tcn_x, tcn_y = torch.from_numpy(tcn_x).float(), torch.from_numpy(tcn_y)


# Now split it into train and test data:

train_idx = int(train_prop * tcn_x.shape[0])

x_train = tcn_x[0:train_idx]
y_train = tcn_y[0:train_idx]

x_test = tcn_x[train_idx+1 :]
y_test = tcn_y[train_idx+1 :]

if args.cuda:
    print('Using CUDA')
    model.cuda()
    x_train, x_test, y_train, y_test = x_train.cuda(), x_test.cuda(), y_train.cuda(), y_test.cuda()

##############################################################

##############################################################
batch_size = args.batch_size
n_classes = 1    # Output size is 1 for normal regression
input_channels = neural_dat.shape[1]
epochs = args.epochs
steps = 0

channel_sizes = [args.nhid] * args.levels
kernel_size = args.ksize


model = TCN(input_channels, n_classes, channel_sizes, kernel_size=kernel_size, dropout=args.dropout)


lr = args.lr
optimizer = getattr(optim, args.optim)(model.parameters(), lr=lr)
# ############################################################


def train(ep):
    global steps
    train_loss = []
    train_err = []
    test_err = []
    running_test_err = []
    # criterion = nn.MSELoss()
    model.train()
    for i in xrange(x_train.shape[0]):
        data, target = x_train[i], torch.FloatTensor([y_train[i]])
        if args.cuda: data, target = data.cuda(), target.cuda()
        # print('Training')
        # IP.embed()

        data, target = Variable(data), Variable(target)
        if (batch_size == 1): data = data.unsqueeze(0) # TCN works with a 3D tensor

        optimizer.zero_grad()
        output = model(data)  # Run Network

        # print('Loss')
        # IP.embed()
        loss = F.mse_loss(output, target)  # MSE loss. Take sqrt if you want RMS.
        loss.backward()
        if args.clip > 0:
            torch.nn.utils.clip_grad_norm(model.parameters(), args.clip)
        optimizer.step()
        if (i%100 == 0):
            _, sq_err = test()
            running_test_err.append(sq_err)
            print('VAF:{}'.format(sq_err))

    train_loss.append(loss)
    train_err.append(predict(x_train, y_train)[1])
    test_err.append(predict(x_test, y_test)[1])
    print('Train Epoch: {} \tLoss: {}, train VAF: {}, test VAF {}'.format(ep, train_loss[-1], train_err[-1], test_err[-1]))


# Evaluate your model performance on ANY data
def predict(X, Y):
    model.eval()
    pred = []
    for i in xrange(X.shape[0]):
        data, target = X[i], torch.FloatTensor([Y[i]])
        if args.cuda: data, target = data.cuda(), target.cuda()

        data, target = Variable(data, volatile=True), Variable(target)
        if (batch_size == 1): data = data.unsqueeze(0) # TCN works with a 3D tensor

        output = model(data)
        pred.append(output.data.numpy()[0,0])
    sq_err = get_corr(Y, pred)
    return pred, sq_err

# Evaluate your model performance on TESTING data
def test():
    model.eval()
    pred = []
    for i in xrange(x_test.shape[0]):
        data, target = x_test[i], torch.FloatTensor([y_test[i]])
        if args.cuda: data, target = data.cuda(), target.cuda()

        data, target = Variable(data, volatile=True), Variable(target)
        if (batch_size == 1): data = data.unsqueeze(0) # TCN works with a 3D tensor

        output = model(data)
        pred.append(output.data.numpy()[0,0])

    sq_err = get_corr(y_test, pred)
    return pred, sq_err

# Variance Accounted For Correlation
def get_corr(y_test, y_test_pred):
    y_test = y_test.cpu().numpy()
    y_mean = np.mean(y_test)
    r2 = 1-np.sum((y_test_pred-y_test)**2)/np.sum((y_test-y_mean)**2)
    return r2


if __name__ == "__main__":
    for epoch in range(1, epochs+1):
        train(epoch)
        test()
        if epoch % 10 == 0:
            lr /= 10
            for param_group in optimizer.param_groups:
                param_group['lr'] = lr
