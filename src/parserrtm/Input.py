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
            if (fpath[1].lower() != 'none') and fpath[1]:
                self.read_in_cld_rrtm(fpath[1],**kwargs)
                self.fpath_in_cld_rrtm = fpath[1]
            self.read_in_aer_rrtm(fpath[2],**kwargs)
            self.fpath_in_aer_rrtm = fpath[2]
        
        else:
            raise TypeError('Expected one of {} or {} of length 2 or 3, got {} instead'.format(
                (abc.Mapping,str,os.PathLike),abc.Sequence, type(fpath)))
        
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
            files = ('input_rrtm','in_cld_rrtm')
        elif file == 'gas':
            files = ('input_rrtm')
        elif file == 'aer':
            files = ('input_rrtm','in_aer_rrtm')
        elif file == 'aercld':
            files == ('input_rrtm','in_aer_rrtm')
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
        lists = ['2.1.1','2.1.2','2.1.3','2.2.3','2.2.4','2.2.5','3.5','3.6.1','3.8.1','3.8.2','C1.2','C1.3','C1.3a']
        return rec in lists

    #TODO: add aerosol records
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
            'C1.2':  lambda self: 1 if type(self.LAY) != list else len(self.LAY),
            'C1.3':  lambda self: 1 if type(self.LAY) != list else len(self.LAY),
            'C1.3a': lambda self: 15
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

    def write(self,fpath=None, file='auto'):
        '''
        Write instance of parserrtm.Input to text files needed to run RRTM.

        Note that these files are always called INPUT_RRTM, IN_CLD_RRTM, IN_AER_RRTM because this
        is required to run RRTM. Use folder organization for more descriptive filenames.
        
        -------------
        Arguments:
        self        : parserrtm.Input
        fpath       : (str or PathLike, optional) folder where input files are written. Files are
                      always written with default filenames of INPUT_RRTM, IN_CLD_RRTM, and IN_AER_RRTM.
                      if fpath is not specified, files are written to the current working directory.
        file        : (str, optional) kind of file to write. Options are 'input_rrtm', 'in_cld_rrtm', 'in_aer_rrtm', or 'auto' (default).
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
            if self.IAER > 0:
                files.append('in_aer_rrtm')


        # use only default filenames
        if fpath == None:
            fpath = Path.cwd()
        fpaths = {'input_rrtm':  Path(fpath)/'INPUT_RRTM',
                'in_cld_rrtm': Path(fpath)/'IN_CLD_RRTM',
                'in_aer_rrtm': Path(fpath)/'IN_AER_RRTM'}
        
        # iterate over write methods
        methods = {'input_rrtm':self.write_input_rrtm, 
                   'in_aer_rrtm':self.write_in_cld_rrtm, 
                   'in_cld_rrtm':self.write_in_aer_rrtm}
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
    
    #NOTE: record order identical between SW and LW variants?
    def read_in_cld_rrtm(self, fpath):
        '''
        Read and interpret "IN_CLD_RRTM" text file into the current instance.
        
        "IN_CLD_RRTM" contains information about cloud layers in the model and
        is only used if ICLD (record 1.2) = 1 or 2. Note that an "INPUT_RRTM"
        file must already be read into self before reading "IN_CLD_RRTM",
        since the formatting of "IN_CLD_RRTM" depends on some fields from
        "INPUT_RRTM" (namely ISCAT and NUMANGS).
        
        Scan the content of a file and interpret each line according to 
        the format, sequence, and naming described in the documentation
        file "rrtm_instructions". Each field is read into an attribute
        of the current instance. Repeated fields (e.g. user-defined profiles) 
        are read into a list in order of occurrence.
        
        NOTE: 
            For INFLAG=10, the fields TAUCLD, SINGLE-SCATTERING ALBEDO, PMOM(0:NSTR)
            are a list of lists. What this means: each item in the outer list is a 
            cloudy layer, while each item in the inner list are the cloud properties 
            for the 16 spectral bands in ascending order. 

            The first band is specified as C1.3, while the next 15 bands are 
            specified as C1.3a, which has fewer fields, which makes the formatting a bit
            unusual. Since no examples in the source code use INFLAG=10, this is untested!

        -------------
        Arguments:
        self        : instance of rrtmparse Input class
        fpath       : path to "IN_CLD_RRTM" file
        -------------
        Returns:
        self        : instance with all fields stored as attributes
        -------------
        '''
        
        with open(fpath,'r') as f:
            #read lines into list
            lines = f.readlines()
            self.lines = lines
            
        #get start and end lines (start line is zero)
        start_i, end_i = Input.get_input_rrtm_file_bounds(self.lines,file='in_cld_rrtm')
        
        #set read position to starting line
        self.read_i = start_i
        
        #determine derived parameter NSTR (# of mom. of phase function needed)
        self.NSTR = 0
        if (self.ISCAT==1) or (self.ISCAT==2):
            if self.NUMANGS==0:
                self.NSTR=4
            elif self.NUMANGS==1:
                self.NSTR=8
            elif self.NUMANGS==2:
                self.NSTR=16
            else:
                raise ValueError(f"'{NUMANGS}' not a valid NUMANGS value, \
                must be 0, 1, or 2 when ISCAT > 0")
                
        #iterate/read over records
        self.read_record('C1.1')
        if (self.INFLAG == 1) or (self.INFLAG == 2):
            self.read_record('C1.2',mode='new')
            while self.read_i < end_i:
                self.read_record('C1.2',mode='append')
        elif (self.INFLAG == 0) or (self.INFLAG == 10):
            self.read_record('C1.3',mode='new')
            while self.read_i < end_i:
                self.read_record('C1.3',mode='append')
                if self.INFLAG == 10:
                    for i in range(15):
                        self.read_record('C1.3a',mode='append depth')
        
        #check that we read up to the expected end of records
        if self.read_i != end_i:
            warnings.warn(f'{fpath} read finished on line {self.read_i} instead of {end_i} -- some of input is unread!')
            
        del self.lines
        return self
    
    #NOTE: record order identical between SW and LW variants?
    def read_input_rrtm(self, fpath):
        '''
        Read and interpret "INPUT_RRTM" text file into the current instance.
        
        "INPUT_RRTM" contains the overall model setup and specifies surface
        boundary conditions, temperature and pressure profiles, which gases
        to simulate, and their concentration at levels.
        
        Scan the content of a file and interpret each line according to 
        the format, sequence, and naming described in the documentation
        file "rrtm_instructions". Each field is read into an attribute
        of the current instance. Repeated fields (e.g. user-defined profiles) 
        are read into a list in order of occurrence.

        -------------
        Arguments:
        self        : instance of parserrtm.Input
        fpath       : path to "INPUT_RRTM" file
        -------------
        Returns:
        self        : instance with all fields stored as attributes
        -------------
        '''
        #1. get file record layout
        #2. get field lists
        #3. loop over lines and store
        
        with open(fpath,'r') as f:
            #read lines into list
            lines = f.readlines()
            self.lines = lines
            
        #get start and end lines
        start_i, end_i = Input.get_input_rrtm_file_bounds(self.lines)
        
        #set read position to starting line
        self.read_i = start_i
        
        #sequentially read records of file
        self.read_record('1.1')
        self.read_record('1.2')
        self.read_record('1.4')
        if self.IATM == 0:
            self.read_record('2.1')
            for i in range(self.NLAYRS):
                self.read_record('2.1.1',mode='new' if i==0 else 'append')
                self.read_record('2.1.2',mode='new' if i==0 else 'append')
                if self.NMOL > 7:
                    self.read_record('2.1.3',mode='new' if i==0 else 'append')
            if self.IXSECT == 1:
                self.read_record('2.2')
                self.read_record('2.2.1')
                self.read_record('2.2.2')
                for i in range(self.NLAYRS):
                    self.read_record('2.2.3',mode='new' if i==0 else 'append') #dummy
                    self.read_record('2.2.4',mode='new' if i==0 else 'append')
                    if self.IXMOLS > 7:
                        self.read_record('2.2.5',mode='new' if i==0 else 'append')
        elif self.IATM == 1:
            self.read_record('3.1')
            self.read_record('3.2')
            if self.IBMAX == 0:
                self.read_record('3.3A')
            else:
                self.read_greedy_record('3.3B') #GREEDY
            if self.MODEL == 0:
                self.read_record('3.4')
                for i in range(self.IMMAX):
                    self.read_record('3.5',mode='new' if i==0 else 'append')
                    self.read_record('3.6.1',mode='new' if i==0 else 'append')
            if self.IXSECT == 1:
                self.read_record('3.7')
                self.read_record('3.7.1')
                if self.IPRFL == 0: 
                    self.read_record('3.8')
                    for i in range(self.LAYX):
                        self.read_record('3.8.1',mode='new' if i==0 else 'append')
                        self.read_record('3.8.2',mode='new' if i==0 else 'append')
                        
        if self.read_i != end_i:
            warnings.warn(f'{fpath} read finished on line {self.read_i} instead of {end_i} -- some of input is unread!')
            
        del self.lines
        return self
    
    #TODO: add in_aer_rrtm file support
    def get_input_rrtm_file_bounds(lines,file='input_rrtm'):
        '''
        Find start and end lines for "INPUT_RRTM"  or "IN_CLD_RRTM" file.
        
        -------------
        Arguments:
        lines (list): list of lines of file (from file.readlines())
        file   (str): type of input file ('input_rrtm' or 'in_cld_rrtm')
        -------------
        Returns:
        start_i, end_i (int): line positions of first and last lines of file
        -------------
        '''

        #find start ('$') and end ('%') positions
        starts = [i for i,s in enumerate(lines) if s[0]=='$']
        ends   = [i for i,s in enumerate(lines) if s[0]=='%']
        
        #in_cld_rrtm has no starting '$' character and begins on the first line
        if file == 'in_cld_rrtm':
            starts = [0]

        #check '$' and '%' only occur once and '$' comes before '%'
        if (len(starts)==len(ends)==1) and (starts<ends):
            start_i, end_i = starts[0], ends[0]
        else:
            raise IOError(f"{fpath}: start lines '{starts}' and end lines '{ends}' not valid. Start is a line beginning with '$',\
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