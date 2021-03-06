# -*- coding: utf-8 -*-
"""
Created on Tue Sep  6 17:17:43 2016

@author: ajaver
"""
import os
import glob
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from tierpsy.analysis.feat_create.obtainFeaturesHelper import WormStats

from correct_file_name import read_rig_csv_db, gecko_fnames_to_table

def convertUnits(df, microns_per_pixel):
    
    def _removeExtra(x):
        for bad_str in ['_pos', '_neg', '_abs', '_paused', '_foward', '_backward']:
            x = x.replace(bad_str, '')
        return x
    
    dict_units = WormStats().features_info['units'].to_dict()
    
    def _getFactor(x):
        try:
            units = dict_units[_removeExtra(x)]
        except KeyError:
            units = '1'
        if units in ['microns', 'microns/seconds']:
            return microns_per_pixel
        elif units == 'microns^2':
            return microns_per_pixel**2
        elif units == 'radians/microns':
            return 1/microns_per_pixel
        else:
            return 1
    
    for feat in df:
        df[feat] *= _getFactor(feat)
    
    return df
    
class ReadFeaturesHDF5(object):
    def __init__(self):
        self.ws = WormStats()
    
    def get(self, features_file, feat2read = []):
        if not feat2read:
            feat2read = self.ws.feat_timeseries
        feat2read = ['worm_index', 'timestamp'] + feat2read
        with pd.HDFStore(features_file, 'r') as fid:
            features_timeseries = fid['/features_timeseries']
            features_timeseries = features_timeseries[feat2read]

        return features_timeseries
    
    def get_means(self, features_file, group_str = 'feat_means'):
        with pd.HDFStore(features_file, 'r') as fid:
            features_means = fid['/features_summary/' + group_str]
        return features_means

def save_into_db(database_name, experiments):
    
    assert all(x in experiments for x in ['microns_per_pixel'])
    
    
    disk_engine = create_engine('sqlite:///' + database_name)
    experiments.to_sql('experiments', 
                       disk_engine, 
                       if_exists='replace', 
                       index_label = 'video_id',
                       chunksize=1)
    
    
    feat_reader = ReadFeaturesHDF5()
    for video_id, plate_row in experiments.iterrows():
        feat_file = os.path.join(plate_row['directory'], plate_row['base_name'] + '_features.hdf5')
        if not os.path.exists(feat_file):
                continue
        
        #empty file continue 
        with pd.HDFStore(feat_file, 'r') as fid:
            if not 'features_means' in fid:
                continue
        
        
        feat_types = ['P10th', 'P90th', 'medians', 'means']
        feat_types = feat_types + [x + '_split' for x in feat_types]
        for feat_str in feat_types:
            plate_mean_features = feat_reader.get_means(feat_file, feat_str)
            
            plate_mean_features = convertUnits(plate_mean_features, plate_row['microns_per_pixel'])
            
            
            plate_mean_features['video_id'] = video_id
    
            exists_type = 'replace' if video_id == 0 else 'append'
            plate_mean_features.to_sql(feat_str, 
                                  disk_engine,
                                  if_exists=exists_type,
                                  index = False)
            
        print('{} of {} {}'.format(video_id+1, len(experiments),plate_row['base_name']))


def _delta_timestamp(video_timestamp):
    delT = video_timestamp - video_timestamp.min()
    delT /= np.timedelta64(1, 'm')
    return delT

def _get_set_delta_t(experiments):
    set_dT = pd.Series()
    exp_dT = pd.Series()
    groupby_exp = experiments.groupby('exp_name')
    for exp_name, exp_rows in groupby_exp:
        delT = _delta_timestamp(exp_rows['video_timestamp'])
        exp_dT = exp_dT.append(delT)
        for set_n, set_rows in exp_rows.groupby('set_n'):
            delT = _delta_timestamp(set_rows['video_timestamp'])
            set_dT = set_dT.append(delT)
        
    experiments['set_delta_time'] = set_dT
    experiments['exp_delta_time'] = exp_dT
    return experiments

def get_rig_experiments_df(features_files, csv_files):
    '''
    Get experiments data from the files located in the main directory and from
    the experiments database
    '''
    
    def _read_db(x):
        db, _ = read_rig_csv_db(x)
        db.columns = [x.strip() for x in db.columns]
        exp_name = os.path.basename(x).replace('.csv', '').replace('.xlsx', '')
        db['exp_name'] = exp_name
        return db
    
    db_csv = pd.concat([_read_db(x) for x in csv_files], ignore_index=True)
    db_csv.rename(columns={'Set_N': 'set_n', 'Camera_N': 'channel' , 'Rig_Pos':'stage_pos'}, inplace=True)
    
    
    fparts_tab = gecko_fnames_to_table([x.replace('_features.hdf5', '.hdf5') for x in features_files ])
    fparts_tab['exp_name'] = fparts_tab['directory'].apply(lambda x : x.split(os.sep)[-1])
    
    experiments = pd.merge(fparts_tab, db_csv, on=['exp_name', 'set_n', 'channel', 'stage_pos'])
    experiments = _get_set_delta_t(experiments)
    return experiments

    
if __name__ == '__main__':
    database_dir = '/Users/ajaver/OneDrive - Imperial College London/compare_strains_DB'
    root_dir = '/Volumes/behavgenom_archive$/Avelino/Worm_Rig_Tests/'
    exp_set = 'short_movies_new' #'movies_2h'#'Agar_Test' #'Test_20161027' # 'L4_Long_Rec' #'Test_Food'#
    exp_set_dir = os.path.join(root_dir, exp_set)
    
    database_name = os.path.join(database_dir, 'control_experiments_{}.db'.format(exp_set))
    
    
    csv_dir = os.path.join(exp_set_dir, 'ExtraFiles')
    feats_dir = os.path.join(exp_set_dir, 'Results')
    
    
    csv_files = glob.glob(os.path.join(csv_dir, '*.csv')) + glob.glob(os.path.join(csv_dir, '*.xlsx'))
    features_files = glob.glob(os.path.join(feats_dir, '**/*_features.hdf5'), recursive=True)
    
    experiments = get_rig_experiments_df(features_files, csv_files)
    save_into_db(database_name, experiments)
    