import numpy as np
import torch
from scipy.io import loadmat
from ml import BrainDataset, PolicyEstimator, reinforce
from utils import device, train_cv_test_split, set_rand_seed
from argparse import ArgumentParser
from preferred_path import PreferredPath

if __name__ == "__main__":
    # Input Parameters
    parser = ArgumentParser()
    add = lambda arg, default, t, const=None: parser.add_argument(f'--{arg}', nargs='?', const=const, default=default, type=t)
    add_list = lambda arg: parser.add_argument(f'--{arg}', nargs='+')
    add('res', 219, int)
    add('subj', 1, int)
    add('epoch', 1, int)
    add('batch', 1, int)
    add('sample', 100, int)
    add('hu', 10, int)
    add('lr', 0.001, float)
    add('save', None, str)
    add('load', None, str)
    add('savefreq', 1, int)
    add('nolog', False, bool, const=True)
    add('pathmethod', PreferredPath._DEF_METHOD, str)
    add('seed', None, int)
    add('nnweight', None, float)
    add('constsig', None, float)
    add('posonly', False, bool, const=True)
    add_list('fns')
    args = vars(parser.parse_args())

    # Read input arguments
    res = args['res']
    subj = args['subj']
    subj = list(range(484)) if subj == 0 else [subj-1]
    epoch = args['epoch']
    batch = args['batch']
    sample = args['sample']
    hidden_units = args['hu']
    lr = args['lr']
    save_path = args['save']
    load_path = args['load']
    save_freq = args['savefreq']
    log = not args['nolog']
    path_method = args['pathmethod']
    seed = args['seed']
    nn_init_weight = args['nnweight']
    const_sig = args['constsig']
    pos_only = args['posonly']
    fns = args['fns'] 
    num_fns = len(fns)

    # Extract selected input params for outputs
    subj_name = f'x{len(subj)}' if len(subj) > 1 else f's{str(subj[0] + 1).zfill(3)}'
    params = {
        'device': device,
        'res': res,
        'subj': subj_name,
        'epochs': epoch,
        'batch_size': batch,
        'samples': sample,
        'hidden_units': hidden_units,
        'learning_rate': lr,
        'save_path': save_path,
        'load_path': load_path,
        'save_frequency (epochs)': save_freq,
        'log_output': log,
        'path_method': path_method,
        'rand_seed': seed,
        'nn_initial_weight': nn_init_weight,
        'const_sig': const_sig,
        'pos_only': pos_only,
        'functions': f'{num_fns} ({", ".join([f for f in fns])})'
    }

    # Apply random seed
    if seed is not None:
        set_rand_seed(seed=seed)

    # Network parameters
    if log: print("Creating network...")
    pe = PolicyEstimator(res=res, fn_len=num_fns, hidden_units=hidden_units, init_weight=nn_init_weight, const_sig=const_sig).to(device)
    opt = torch.optim.Adam(pe.network.parameters(), lr=lr)

    # Init new/load previous training data
    if load_path:
        # Load from checkpoint
        plt_data = torch.load(load_path)
        pe.network.load_state_dict(plt_data.pop('model_state_dict'))
        opt.load_state_dict(plt_data.pop('optimizer_state_dict'))
        if plt_data['fns'] != fns: raise ValueError('Different function criteria loaded')
        params['epochs'] += plt_data['epochs']
    else:
        # New
        plt_data = {
            'epochs': 0,
            'epoch_seconds': [],
            'rewards': [],
            'success': [],
            'mu': [[] for _ in range(num_fns)],
            'sig': [[] for _ in range(num_fns)],
            'fns': fns}
        plt_data['train_idx'], plt_data['cv_idx'], plt_data['test_idx'] = train_cv_test_split(M=subj, train_pct=0.6, cv_pct=0.2)

    # Write params to a txt file and print
    summary = '====================\n' + '\n'.join([f'{k} = {v}' for k, v in params.items()]) + '\n===================='
    print(summary, flush=True)
    if save_path is not None:
        # Add 'params' prefix and write
        ridx = save_path.rfind('/')
        log_path = save_path[:ridx+1] + 'params_' + save_path[ridx+1:]
        with open(log_path + '.txt', 'w') as file:
            file.write(summary)

    if log:
        print('Reading files...')

    # Read brain data
    
    pwd = './'
    
    sc = loadmat(pwd+'subjfiles_SC'+str(res)+'.mat')
    fc = loadmat(pwd+'subjfiles_FC'+str(res)+'.mat')
    sc = np.array([sc[f's{str(z+1).zfill(3)}'] for z in subj])
    fc = np.array([fc[f's{str(z+1).zfill(3)}'] for z in subj])
    euc_dist = loadmat(pwd+'euc_dist.mat')[f'eu{res}']
    hubs = np.loadtxt(pwd+'hubs_'+str(res)+'.txt', dtype=int, delimiter=',')
    regions = np.loadtxt(pwd+'regions_'+str(res)+'.txt', dtype=int, delimiter=',')
    func_regions = np.loadtxt(pwd+'func_reg'+str(res)+'.txt', dtype=int, delimiter=',')

    # Train / test split
    if log: print('Loading brains...')
    train_idx = plt_data['train_idx']
    if len(train_idx) == 1: train_idx = [0]
    train_data = BrainDataset(sc=sc[train_idx], fc=fc[train_idx], euc_dist=euc_dist, hubs=hubs, regions=regions, func_regions=func_regions, fns=fns)
    if log: print('====================')

    # Reinforce and save after each epoch
    reinforce(pe=pe, opt=opt, data=train_data, epochs=epoch, batch=batch, sample=sample, lr=lr, const_sig=const_sig, pos_only=pos_only, plt_data=plt_data, save_path=save_path, save_freq=save_freq, log=log, path_method=path_method)
