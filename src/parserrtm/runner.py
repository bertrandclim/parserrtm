import numpy as np
import pandas as pd

import warnings
from pathlib import Path
import os,stat              # for chmod'ing output scripts and type-checking
import copy                 # for writing to file
from collections import abc # for type-checking
import contextlib           # for Runner to use multiple log files
import subprocess           # for Runner to execute rrtm from Python
import re                   # for Runner cleanup matching folder names
from abc import ABC, abstractmethod

from fortranformat import FortranRecordReader, FortranRecordWriter, config

class Runner:
    def __init__(self,n_workers=8,tmp_path='/private/tmp/lima',shell='/usr/local/bin/lima sh -c',
                 exec_path='~/linuxvm/rrtm_lw_pgf90/rrtm_v3.3_linux_pgf90',clean=True):
        #set attrs
        self.n_workers = n_workers
        self.clean     = clean
        self.tmp_path  = Path.expanduser(Path(tmp_path))
        self.exec_path = Path.expanduser(Path(exec_path))
        if shell:
            self.shell = shell
        else:
            self.shell = ''
        #pick unqiue identifier
        self.uid = '{:04d}'.format(np.random.randint(10000))
        #remove other worker directories
        if self.clean:
            Runner.rmdirs(self.tmp_path,'any')
        else:
            Runner.rmdirs(self.tmp_path,self.uid)
        #make worker directories
        dirs = Runner.mkdirs(self.n_workers,self.tmp_path,self.uid)
        self.dirs = dirs
        #link executable into worker directories
        Runner.lndirs(self.dirs,self.exec_path)
        return

    def mkdirs(n_workers,tmp_dir,uid):
        '''create worker directories'''
        dirpaths = [tmp_dir/f'rrtm{uid}_worker{i:02d}' for i in range(n_workers)]
        _        = [Path.mkdir(p) for p in dirpaths]
        print(f'created {len(dirpaths)} worker directories at {tmp_dir}')
        return dirpaths

    def lndirs(dirpaths,exec_path):
        '''symlink executable into worker dirs'''
        for p in dirpaths:
            subprocess.run(['ln','-s',(exec_path).resolve(),'rrtm'],cwd=p,check=True)
        return

    def rmdirs(path,uid,rms=['OUTPUT_RRTM','INPUT_RRTM','IN_CLD_RRTM','IN_AER_RRTM',"'&1'",r'\&1',
                             'OUT_CLD_RRTM','TAPE6','TAPE7','rrtm.log','rrtm']):
        '''remove unused rrtm worker directories'''

        #if uid is specified, match that 4-digit string.
        #if uid == 'any', match any 4-digit number
        if uid=='any':
            uid='\\d{4}'

        #make a regex to match worker directory names
        #format is rrtmXXXX_workerYY: XXXX is uid and YY is worker number
        exp = re.compile(f'rrtm{uid}_worker\\d+')

        #get all matching paths in path
        paths = filter(lambda p: exp.fullmatch(p.name),path.glob('*'))
        paths = list(paths)

        #remove directories
        for p in paths:
            #remove all accepted temporary files
            _ = [(p/name).unlink(missing_ok=True) for name in rms]
            #try removing directory
            p.rmdir()
        print(f'removed {len(paths)} worker directories at {path}')
        return

    def run(self,inputs,verbose=True,ignored_warnings = ['Warning: ieee_underflow is signaling',
                                                         'Warning: ieee_inexact is signaling',
                                                         'FORTRAN STOP']):
        '''run RRTM on a list of parserrtm.Inputs and return output'''
        outputs = [ ]
        logs = [ ]
        i=0
        if verbose: print(f'starting {len(inputs)} jobs')
        while i<len(inputs):
            if verbose: print(f'{len(inputs)-i} jobs remaining')
            
            #wipe worker directories
            if verbose: print(f'\t wiping {len(self.dirs)} directories. Running:')
            for dir in self.dirs:
                p = subprocess.run(self.argproc('rm OUTPUT_RRTM INPUT_RRTM IN_CLD_RRTM OUT_CLD_RRTM TAPE6 TAPE7 rrtm.log'),
                                   cwd=dir,stderr=subprocess.DEVNULL,stdout=subprocess.DEVNULL)
            
            ps = [ ]
            logfilepaths = [dir/'rrtm.log' for dir in self.dirs]
            with contextlib.ExitStack() as stack:
                logfiles = [stack.enter_context(open(fname,'w')) for fname in logfilepaths]
                #submit jobs
                for j,dir in enumerate(self.dirs):
                    if i<len(inputs):
                        input = inputs[i]
                    else:
                        break
                    if verbose: print(f'\t \t {input.CXID[1:16]} in {dir.name}')
                    input.write(fpath=dir,file='auto')
                    p = subprocess.Popen(self.argproc('./rrtm'),shell=False,cwd=dir,stdout=logfiles[j],stderr=subprocess.STDOUT)
                    ps.append(p)
                    #print(f'\t \t {i}')
                    i+=1

                if verbose: print('\t waiting...',end='')
                #wait for jobs to finish and check for successful execution
                for j,p in enumerate(ps):
                    returncode = p.wait()
                    if returncode != 0:
                        print(f'worker {self.dirs[j]} failed!')
                        raise subprocess.CalledProcessError(returncode,p.args)
                if verbose: print('finished')
                #print(f'\t {i}')
        
            #collect outputs
            if verbose: print(f'\t reading {len(ps)} outputs')
            for p,dir in zip(ps,self.dirs):
                #read outputs
                outputs.append(read_output(dir/'OUTPUT_RRTM'))
                #read logs
                with open(dir/'rrtm.log','r') as f:
                    log=f.read().splitlines() 
                    #check for successful completion
                    if log[-1] != 'FORTRAN STOP':
                        raise UserError(f"RRTM run in {dir}/rrtm.log did not terminate sucessfully! 'FORTRAN STOP' expected, got {log[-1]} instead")
                    for line in log:
                        if line not in ignored_warnings:
                            warnings.warn(f'{dir}/rrtm.log has non-accepted warning \'{line}\'')
                    logs.append(log)
        if verbose: print(f'{len(inputs)-i} jobs remaining')
        if verbose: print(f'finished {len(inputs)} jobs')
        return outputs, logs

    def argproc(self,cmd):
        '''format arguments to subprocess based on self.shell'''
        return splitfirst(prepend(self.shell,cmd))

def prepend(shell,cmd):
    '''prepend shell to cmd if shell is non-empty str'''
    return [shell,cmd] if len(shell)>0 else [cmd]

def splitfirst(l):
    '''split first list element along spaces'''
    return [*l[0].split(),*(l[1:] if len(l)>1 else [])]

def read_output(fpath):
    calc_type = determine_output_type(fpath)
    if calc_type == 'longwave':
        return read_output_lw(fpath)
    elif calc_type == 'shortwave':
        return read_output_sw(fpath)

def read_output_lw(fpath):
    '''
    Read RRTM_LW ASCII output file and parse to xarray.Dataset.
    Adapted from https://github.com/climatedyn/RRTM_LW.
    Arguments:
        Absolute path to RRTM_LW output file
    Returns:
        Xarray.Dataset with contents of file
    '''
    
    #loop over file to get number of numeric lines to read
    with open(fpath,'r') as f:
        #load lines as list
        lnes = f.readlines()
        #find the line # of a form-feed+newline (this marks the end of the table)
        indx = lnes.index('\x0c\n')
        #get lines before column names and after table to save as metadata
        global_attrs = {'source': fpath,
                        'created_by':'parserrtm',
                        'output_header': lnes[0],
                        'output_footer': lnes[indx+1:]}

    #parse with pandas
    ds = pd.read_fwf(
                        fpath,
                        header=[1,2], #2nd and 3rd lines (1st gets auto-skipped)
                        nrows=indx-3, #remove three leading text lines
                        widths=[8,13,14,14,14,19], #field widths
                        index_col=0 #use LEVEL for index
                    ).to_xarray()

    #put units in attrs, format varnames
    ds = ds.rename({'index':'level'})
    rname = { }
    for var in ds.data_vars:
        if var[0].replace(' ','_').lower() == 'netflux': 
            rname[var] = 'net_flux'
        else:
            rname[var] = var[0].replace(' ','_').lower()
        ds[var].attrs['units'] = var[1]
    ds = ds.rename(rname)
    #store non-table data in global attrs
    ds.attrs = global_attrs
    return ds

def read_output_sw(fpath):
    '''
    Read RRTM_SW ASCII output file and parse to xarray.Dataset.
    Arguments:
        Absolute path to RRTM_SW output file
    Returns:
        Xarray.Dataset with contents of file
    '''
    #loop over file to get number of numeric lines to read
    with open(fpath,'r') as f:
        #load lines as list
        lines = f.readlines()
        #find the first line of the table (after "Wavenumbers: ...")
        for i,line in enumerate(lines):
            if line[1:12] == 'Wavenumbers':
                start_i = i+1
                break
        #find the line # of a form-feed+newline (this marks the end of the table)
        end_i = lines.index('\x0c\n')
        #get lines before column names and after table to save as metadata
        global_attrs = {'source': fpath,
                        'created_by':'parserrtm',
                        'output_header': lines[0],
                        'output_footer': lines[end_i+1:]}

        #parse with pandas
        ds = pd.read_fwf(
                            fpath,
                            header=[start_i-1, start_i], #2nd and 3rd lines (1st gets auto-skipped)
                            nrows=end_i-start_i-2, #remove three leading text lines
                            widths=[6,10,14,14,15,14,15,13], #field widths
                            index_col=0 #use LEVEL for index
                        ).to_xarray()

        #put units in attrs, format varnames
        ds = ds.rename({'index':'level'})
        rname = { }
        for var in ds.data_vars:
            if var[0].replace(' ','_').lower() == 'netflux': 
                rname[var] = 'net_flux'
            else:
                rname[var] = var[0].replace(' ','_').lower()
            ds[var].attrs['units'] = var[1]
        ds = ds.rename(rname)
        #store non-table data in global attrs
        ds.attrs = global_attrs
        return ds

def determine_output_type(fpath):
    with open(fpath) as f:
        i = 0
        while i<3:
            line = f.readline()
            i+=1
            #print(line[1:34])
            if line[1:34] == 'Wavenumbers:   10.0 - 3250.0 cm-1':
                return 'longwave'
            elif line[1:34] == 'Wavenumbers:   820. - 50000. cm-1':
                return 'shortwave'

