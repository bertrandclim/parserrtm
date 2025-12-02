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


config.RET_UNWRITTEN_VARS_NONE = False #zero-fill instead of NA-fill missing values

def fpaths_union(fpaths_a, fpaths_b, verbose=True):
    fna, fnb = [p.name for p in fpaths_a], [p.name for p in fpaths_b]
    fnab = set(fna).intersection(fnb)
    fpaths_a_thin = filter(lambda p: p.name in fnab, fpaths_a)
    fpaths_b_thin = filter(lambda p: p.name in fnab, fpaths_b)
    if verbose:
        a_but_not_b = set(fna).difference(fnb)
        b_but_not_a = set(fnb).difference(fna)
        if a_but_not_b:
            print(f'removed {a_but_not_b} from fpaths_a')
        if b_but_not_a:
            print(f'remove {b_but_not_a} from fpaths_b')
    return list(fpaths_a_thin), list(fpaths_b_thin)

def read_input(*args):
    if len(args) == 1:
        return Input(args[0])
    else:
        return Input(args)

class Input(ABC):
    '''
    Abstract base class for representing RRTM Inputs

    This allows for code sharing between longwave and shortwave variants, 
    which have different formats for the necessary input files.
    '''
    def __repr__(self):
        recs = { }
        for rec in ['1.1','1.2','1.4']:
            for field in self.get_fields(rec):
                val = getattr(self,field)
                recs[field] = val
        return str(recs)
    
    def __str__(self):
        recs = { }
        for rec in ['1.1','1.2','1.4']:
            for field in self.get_fields(rec):
                val = getattr(self,field)
                recs[field] = val
        return str(recs)
    
    def __init__(self, args, **kwargs):
        
        #treat as a filename if argument is filepath-like
        if isinstance(args, (str, os.PathLike)):
            fpath = args
            self.read_input_rrtm(fpath, **kwargs)
            self.fpath_input_rrtm = fpath

        #treat as a dictionary of fields if argument is dict-like
        elif isinstance(args, abc.Mapping):
            self.from_dict(args,**kwargs)

        
        
        #treat as a list of filenames if argument is list-like
        # if length 1, assume input_rrtm
        elif isinstance(args, abc.Sequence) and (len(args)==1):
            fpath = args
            self.read_input_rrtm(fpath[0],**kwargs)
            self.fpath_input_rrtm = fpath[0]

        # if length 2, assume input_rrtm and in_cld_rrtm
        elif isinstance(args, abc.Sequence) and (len(args)==2):
            fpath = args
            self.read_input_rrtm(fpath[0],**kwargs)
            self.read_in_cld_rrtm(fpath[1],**kwargs)
            self.fpath_input_rrtm = fpath[0]
            self.fpath_in_cld_rrtm = fpath[1]

        # if length 3, assume input_rrtm, in_cld_rrtm, and in_aer_rrtm
        # allow for in_cld_rrtm to be None or 'none'
        elif isinstance(args, abc.Sequence) and (len(args)==3):
            fpath = args
            self.read_input_rrtm(fpath[0],**kwargs)
            self.fpath_input_rrtm = fpath[0]
            if fpath[1]:
                if str(fpath[1]).lower() != 'none':
                    self.read_in_cld_rrtm(fpath[1],**kwargs)
                    self.fpath_in_cld_rrtm = fpath[1]
            self.read_in_aer_rrtm(fpath[2],**kwargs)
            self.fpath_in_aer_rrtm = fpath[2]
        
        else:
            raise TypeError('Expected one of {} or {} of length 2 or 3, got {} instead'.format(
                (abc.Mapping,str,os.PathLike),abc.Sequence, type(args)))
        
        #derived parameter for number of streams,
        #specified differently for LW and SW.
        #only needed for cloudy cases
        if self.ICLD == 1:
            self.NSTR = 0
            #shortwave
            if hasattr(self,'ISTRM'):
                if self.ISTRM == 0:
                    self.NSTR = 4
                elif self.ISTRM == 1:
                    self.NSTR = 8
                elif self.ISTRM == 2:
                    self.NSTR = 16
            #longwave
            if hasattr(self,'NUMANGS'):
                if (self.ISCAT==1) or (self.ISCAT==2):
                    if self.NUMANGS==0:
                        self.NSTR=4
                    elif self.NUMANGS==1:
                        self.NSTR=8
                    elif self.NUMANGS==2:
                        self.NSTR=16
                    else:
                        raise ValueError(f"'{self.NUMANGS}' not a valid NUMANGS value, \
                        must be 0, 1, or 2 when ISCAT > 0")
        
    def __getitem__(self, item):
         return getattr(self,item)

    def __setitem__(self, item, val):
        setattr(self,item, val)

    def from_dict(self,args,file='cld',lazy=False):
        '''Add dictionary keys to a parserrtm.Input object.
        
        Dictionary keys are treated as field names. Optionally
        initialize needed fields for valid file(s).
        
        Parameters
        ---------
        self : parserrtm.Input
            Input object to which to apply dictionary
        args : dict-like
            dictionary containing field:value pairs to apply
        file : str, optional
            key indicating which file types for which to fill in missing fields.
            Options 'gas','aer','cld','aercld'. Default is 'cld'. Meanings:
            - gas:    input_rrtm only
            - aer:    input_rrtm and in_aer_rrtm
            - cld:    input_rrtm and in_cld_rrtm
            - aercld: input_rrtm, in_cld_rrtm, and in_aer_rrtm
            Only used if lazy is False.
        lazy : bool, optional
            Skip checking and filling in any needed fields for a valid input file 
            that are missing in args. Default is False (i.e. filling-in is the default).
    
        Returns
        --------
        self : parserrtm.Input
            Input object with fields initialized according to arguments
        '''
        #1. put all supplied fields into self
        for name,value in args.items():
            setattr(self,name,value)
    
        #2. initialize any missing fields with default values, if lazy==False
        if not lazy:
            # initialize fields needed to write different files based on "file" argument
            
            # always prepare input_rrtm
            #1. fill in fields needed for logical record order,
            #   if not already supplied. NB: this list is excessive
            required = ['IATM','ICLD','IAER','NMOL','IXSECT','IXMOLS','IBMAX','MODEL','IXSECT','IPRFL']
            for name in required:
                if not hasattr(self,name):
                    default = 7 if name == 'NMOL' else 0
                    setattr(self,name,default)
        
            #2. get all needed fields via logical record order
            records = self.get_logical_record_order('input_rrtm')
            for record in records:
                names = self.get_fields(record)
                for name in names:
                    if not hasattr(self,name):
                        if 'CHAR' in name:
                            default = " "
                        else:
                            default = 0
                        setattr(self,name,default)
                            
            if file in ('cld','aercld'):
                # prepare in_cld_rrtm
                #1. fill in fields needed for logical record order,
                #   if not already supplied. 
                required = ['INFLAG']
                for name in required:
                    if not hasattr(self,name):
                        default = 0
                        setattr(self,name,default)
            
                #2. get all needed fields via logical record order
                records = self.get_logical_record_order('in_cld_rrtm')
                for record in records:
                    names = self.get_fields(record)
                    for name in names:
                        if not hasattr(self,name):
                            if 'CHAR' in name:
                                default = " "
                            else:
                                default = 0
                            setattr(self,name,default)

            #TODO: defaults and requirements for in_aer_rrtm are unknown
            if file in ('aer','aercld'):
                # prepare in_aer_rrtm
                #1. fill in fields needed for logical record order,
                #   if not already supplied. 
                required = ['INFLAG']
                for name in required:
                    if not hasattr(self,name):
                        default = 0
                        setattr(self,name,default)
            
                #2. get all needed fields via logical record order
                records = self.get_logical_record_order('in_aer_rrtm')
                for record in records:
                    names = self.get_fields(record)
                    for name in names:
                        if not hasattr(self,name):
                            if 'CHAR' in name:
                                default = " "
                            else:
                                default = 0
                            setattr(self,name,default)
            return self
        
    def broadcast_scalars(self,file='cld'):
        '''
        Broadcast any scalar fields in repeated (listed) records to proper lengths

        file : str, optional
            key indicating which file types for which to fill in missing fields.
            Options 'gas','aer','cld','aercld'. Default is 'cld'. Meanings:
            - gas:    input_rrtm only
            - aer:    input_rrtm and in_aer_rrtm
            - cld:    input_rrtm and in_cld_rrtm
            - aercld: input_rrtm, in_cld_rrtm, and in_aer_rrtm
        '''
        if file == 'cld':
            files = ['input_rrtm','in_cld_rrtm']
        elif file == 'gas':
            files = ['input_rrtm']
        elif file == 'aer':
            files = ['input_rrtm','in_aer_rrtm']
        elif file == 'aercld':
            files == ['input_rrtm','in_cld_rrtm','in_aer_rrtm']
        else:
            files = [file]
        for file in files:
            records = self.get_logical_record_order(file)
            for record in records:
                if Input.islist(record):
                    length = self.record_len(record)
                    names  = self.get_fields(record)
                    for name in names:
                        val = getattr(self,name)
                        if not isinstance(val,list):
                            setattr(self,name,[val]*length)
        return self
    
    def print(self):
        self.fancy_print('input_rrtm')
        if self.ICLD>0:
            self.fancy_print('in_cld_rrtm')
        if self.IAER>0:
            self.fancy_print('in_aer_rrtm')

    def fancy_print(self, file='input_rrtm'):
        '''
        Print out all fields record-by-record to the console
        '''
        
        records = self.get_logical_record_order(file)
        for rec in records:
            print('-----------------------------')
            print(f'{rec}: \n',end='')
            fields = self.get_fields(rec)
            d      = {key:getattr(self,key) for key in fields}
            if not Input.islist(rec):
                print(d)
            else:
                #dict of lists to DataFrame
                df = pd.DataFrame(d)
                with pd.option_context('display.max_rows', 10, 
                                       'display.max_columns', 10, 
                                       'display.float_format','{:,.2E}'.format):
                    print(df)
        print('-----------------------------')

    #TODO: verify that these lists are comprehensive between the two input specifications
    def islist(rec):
        '''
        return if record is a list (True) or scalar (False)
        '''
        lists = ['2.1.1','2.1.2','2.1.3','2.2.3','2.2.4','2.2.5','3.5','3.6.1',
                 '3.8.1','3.8.2','C1.2','C1.3','C1.3a','A2.1','A2.1.1','A2.2','A2.3']
        return rec in lists

    def record_len(self,rec):
        '''
        Return number of times a record is repeated.
        '''
        lens = {
            '2.1.1': lambda self: self.NLAYRS,
            '2.1.2': lambda self: self.NLAYRS,
            '2.1.3': lambda self: self.NLAYRS,
            '2.2.3': lambda self: self.NLAYRS,
            '2.2.4': lambda self: self.NLAYRS,
            '2.2.5': lambda self: self.NLAYRS,
            '3.5':   lambda self: self.IMMAX,
            '3.6.1': lambda self: self.IMMAX,
            '3.8.1': lambda self: self.LAYX,
            '3.8.2': lambda self: self.LAYX,
            'C1.2':  lambda self: 1 if type(self.CLAY) != list else len(self.CLAY),
            'C1.3':  lambda self: 1 if type(self.CLAY) != list else len(self.CLAY),
            'C1.3a': lambda self: 15,
            'A2.1':  lambda self: self.NAER,
            'A2.1.1':lambda self: sum(self.NLAY),
            'A2.2':  lambda self: self.NAER,
            'A2.3':  lambda self: self.NAER if self.IPHA<2 else self.NSTR*self.NAER
        }
        return lens[rec](self)
    
    @abstractmethod
    def get_logical_record_order(self,file='input_rrtm'):
        pass

    @abstractmethod
    def get_explicit_record_order(self,file='input_rrtm'):
        pass

    def copy(self):
        return copy.deepcopy(self)

    def write(self,fpath=None, file='auto', fnames=None):
        '''
        Write instance of parserrtm.Input to text files needed to run RRTM.

        Note that these files are always called INPUT_RRTM, IN_CLD_RRTM, IN_AER_RRTM because this
        is required to run RRTM. Use folder organization for more descriptive filenames.
        
        -------------
        Arguments:
        self        : parserrtm.Input
        fpath       : (str or PathLike, optional) folder where input files are written
                      If fpath is not specified, files are written to the current working directory.
        file        : (str, optional) kind of file to write. Options are 'input_rrtm', 'in_cld_rrtm', 'in_aer_rrtm', or 'auto' (default).
        fname       : (list, optional) list of filenames to write. Specified in the order INPUT_RRTM, IN_CLD_RRTM, IN_AER_RRTM as
                      applicable according to `file`. By default, filenames are INPUT_RRTM, IN_CLD_RRTM, IN_AER_RRTM since this is what 
                      is required by the RRTM executable.

        -------------
        Returns:
        None
        -------------
        '''
        files = [ ]
        if file == 'auto':
            files.append('input_rrtm')
            if self.ICLD > 0:
                files.append('in_cld_rrtm')
            if hasattr(self,'IAER'):
                if self.IAER > 0:
                    files.append('in_aer_rrtm')

        # add directory
        if fpath == None:
            fpath = Path.cwd()
        fpaths = {'input_rrtm':  Path(fpath)/'INPUT_RRTM',
                'in_cld_rrtm': Path(fpath)/'IN_CLD_RRTM',
                'in_aer_rrtm': Path(fpath)/'IN_AER_RRTM'}
        
        # apply filenames
        if fnames:
            for i,file in enumerate(files):
                fpaths[file] = Path(fpath)/fnames[i]
        
        # write applicable files
        methods = {'input_rrtm':self.write_input_rrtm, 
                   'in_cld_rrtm':self.write_in_cld_rrtm, 
                   'in_aer_rrtm':self.write_in_aer_rrtm}
        for file in files:
            methods[file](fpaths[file])
            
        return
    
    def write_input_rrtm(self,fpath):
        records = self.get_explicit_record_order('input_rrtm')
        rundupe = self.copy()
        with open(fpath,'w') as f:
            f.write('\n')
            f.write('\n')
            f.write('file auto-generated by parserrtm\n')
            for rec in records:
                line = rundupe.write_record(rec)
                f.write(line+'\n')
            f.write('%')

    def write_in_cld_rrtm(self,fpath):
        records = self.get_explicit_record_order('in_cld_rrtm')
        rundupe = self.copy()
        with open(fpath,'w') as f:
            for rec in records:
                line = rundupe.write_record(rec)
                f.write(line+'\n')
            f.write('%\n')
            f.write('file auto-generated by parserrtm')

    def write_in_aer_rrtm(self,fpath):
        records = self.get_explicit_record_order('in_aer_rrtm')
        rundupe = self.copy()
        with open(fpath,'w') as f:
            for rec in records:
                line = rundupe.write_record(rec)
                f.write(line+'\n')
            f.write('%\n')
            f.write('file auto-generated by parserrtm')

    def write_record(self,rec):
        '''
        RRTM record writer. Parse a record line using Fortran formats.
        Destructively writes out lists (should be run on a copy of self).
        
        -------------
        Arguments:
        self        : instance of parserrtm.Input
        rec         : (str) record name to write out
        -------------
        Returns:
        line        : (str) line formatted to fields
        -------------
        '''
        #get params for reader by polling self
        fmt    = self.get_format(rec)
        names  = self.get_fields(rec)
        
        #get list of fields to write
        vals = [ ]
        for key in names:
            attr = getattr(self,key)
            if type(attr) == list:
                val = attr.pop(0)
            else:
                val = attr
            vals.append(val)
        
        #parse fields from file line
        writer = FortranRecordWriter(fmt)
        line   = writer.write(vals)
        
        return line
    
    @abstractmethod
    def read_in_cld_rrtm(self,fpath):
        pass

    @abstractmethod
    def read_input_rrtm(self,fpath):
        pass

    def read_in_aer_rrtm(self,fpath):
        '''
        Read and interpret "IN_AER_RRTM" text file into the current instance.
        
        "IN_AER_RRTM" contains information about aerosol layers in the model and
        is only used if IAER (record 1.2) = 10 in RRTM_SW. Note that an "INPUT_RRTM"
        file must already be read into self before reading "IN_AER_RRTM".
        ''' 
        with open(fpath,'r') as f:
            #read lines into list
            lines = f.readlines()
            self.lines = lines
            
        #get start and end lines (start line is zero)
        start_i, end_i = Input.get_input_rrtm_file_bounds(self.lines,file='in_aer_rrtm')
        
        #set read position to starting line
        self.read_i = start_i
        
        #iterate/read over records
        self.read_record('A1.1')
        for i in range(self.NAER):
            self.read_record('A2.1',mode='new' if i==0 else 'append')
            #NOTE: this approach gives AOD flattened dimensions of (0,...,NLAY(NAER=0),...,NLAY(NAER=0)+NLAY(NAER=1),...,sum(NLAY(NAER)))
            for j in range(self.NLAY[-1] if isinstance(self.NLAY,list) else self.NLAY):
                self.read_record('A2.1.1',mode='new' if (i == 0) & (j ==0) else 'append')
        for i in range(self.NAER):
            #fields are SSA(IB) with a length of NAER
            self.read_record('A2.2',mode='new' if i==0 else 'append')
            if (self.IPHA[-1] if isinstance(self.IPHA,list) else self.IPHA) == 2:
                for i in self.NSTR:
                    #left unsupported because records would be different.
                    #instead of IPHASE(IB) with dimensions of NAER,
                    # it would be IPHASE(IB,NSTR) with dimensions of NAER,
                    # where NSTR is an index for each stream.
                    raise NotImplementedError('Direct aerosol phase-function specification not yet supported!')
                    self.read_record('A2.3',mode='new' if i==0 else 'append')
            else:
                self.read_record('A2.3')
        
        #check that we read up to the expected end of records
        if self.read_i != end_i:
            warnings.warn(f'{fpath} read finished on line {self.read_i} instead of {end_i} -- some of input is unread!')
            
        del self.lines
        return self

    def get_input_rrtm_file_bounds(lines,file='input_rrtm'):
        '''
        Find start and end lines for "INPUT_RRTM"  or "IN_CLD_RRTM" file.
        
        -------------
        Arguments:
        lines (list): list of lines of file (from file.readlines())
        file   (str): type of input file ('input_rrtm', 'in_cld_rrtm', or 'in_aer_rrtm')
        -------------
        Returns:
        start_i, end_i (int): line positions of first and last lines of file
        -------------
        '''

        #find start ('$') and end ('%') positions
        starts = [i for i,s in enumerate(lines) if s[0]=='$']
        ends   = [i for i,s in enumerate(lines) if s[0]=='%']
        
        #in_cld_rrtm has no starting '$' character and begins on the first line
        if file in ['in_cld_rrtm','in_aer_rrtm']:
            starts = [0]

        #in_aer_rrtm has no ending '$' character required so assume input ends with file
        if file == 'in_aer_rrtm':
            ends.append(len(lines)-1)

        #check '$' and '%' only occur once and '$' comes before '%'
        if (len(starts)==len(ends)==1) and (starts<ends):
            start_i, end_i = starts[0], ends[0]
        else:
            raise IOError(f"start lines '{starts}' and end lines '{ends}' not valid. Start is a line beginning with '$',\
            end is a line beginning with '%', and input file must have exactly one start and end with the start occurring before the end.")

        return start_i, end_i
    
    def read_record(self,rec,mode='new'):
        '''
        RRTM record reader. Parse a line using Fortran formats.
        Read into self.
        
        -------------
        Arguments:
        self        : instance of RRTM_LW parser class
        rec         : which record next line of file is
        mode        : options ('new','append','append depth'): 
                            -- new: create/overwrite attribute with read value
                            -- append: append new value to end of what's already there
                            -- append depth: convert last element to list and append (create list of lists)
        -------------
        Returns:
        self        : instance with fields of record added as attributes
        -------------
        '''
        #get params for reader by polling self
        s      = self.lines[self.read_i]
        fmt    = self.get_format(rec)
        names  = self.get_fields(rec)
        
        #parse fields from file line
        reader = FortranRecordReader(fmt)
        fields = reader.read(s)
        
        #assign fields as attributes
        for key,val in zip(names,fields):
            if mode=='new':
                setattr(self,key,val)
            
            elif mode=='append':
                l = getattr(self,key)
                if type(l) != list:
                    l = [l]
                l.append(val)
                setattr(self,key,l)
                
            elif mode=='append depth':
                l  = getattr(self,key)
                l2 = l[-1]
                if type(l2) != list:
                    l2 = [l2]
                l2.append(val)
                l[-1] = l2
                setattr(self,key,l)
            
        #step forwards one line
        self.read_i += 1
        return
    
    def read_greedy_record(self,rec):
        '''
        RRTM record reader. Parse a line using Fortran formats.
        Read into self. Read lines until all fields of record are filled.
        Note this only works for lines with generic formats (e.g. '(8F10.3)').

        -------------
        Arguments:
        self        : instance of RRTM_LW parser class
        rec         : which record next line of file is
        -------------
        Returns:
        self        : instance with fields added as attributes
        -------------
        '''
        #get params for reader by polling self
        s      = self.lines[self.read_i]
        fmt    = self.get_format(rec)
        names  = self.get_fields(rec)
        
        #record desired number of fields
        inames = len(names)
        
        #make an empty record
        record = { }
        
        #read once
        #parse fields from file line
        reader = FortranRecordReader(fmt)
        fields = reader.read(s)
        for key,val in zip(names,fields):
            record[key] = val
        self.read_i += 1
                
        #if fields are still missing, keep reading
        while len(record.keys()) < inames:
            #remove keys from names
            names = list(filter(lambda var: var not in list(record.keys()),names))
            
            #read with remaining names
            #parse fields from file line
            fields = reader.read(self.lines[self.read_i])
            for key,val in zip(names,fields):
                record[key] = val
            self.read_i += 1
        
        #write back to self after finished
        for key,val in record.items():
            setattr(self,key,val)
        return
    
    @abstractmethod
    def get_format(self,rec): 
        '''
        Get dict of Fortran format-strings for each record.

        It's a method since some record formats (xsec records 2.1.1-3 and 2.2.4-5) 
        depend on the values of other records (IFORM and IFRMX).
        '''
        pass

    @abstractmethod
    def get_fields(self,rec):
        '''
        Get dict of lists of field names for each record.

        It's a method since the number and names of many records' fields 
        depend on a field stored in some previous record. If a value is a
        function, it will be evaluated with the fields currently read in
        as attributes.
        '''
        pass
