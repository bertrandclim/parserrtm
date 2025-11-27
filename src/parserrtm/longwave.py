    
from .input import Input
import warnings

class InputLW(Input):
    '''Specification of inputs for an RRTM-LW calculation

    RRTM has many options which require different input variables.
    This class stores input variables and automates the I/O process
    for the complex text files required to run RRTM-LW.
    
    See the file `rrtm_instructions` as a part of the RRTM-LW source code
    for definitions of each variable name.

    See the examples distributed as a part of this repository for examples
    of the variables necessary for various kinds of calculations.
    '''

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
                for i in range(abs(self.IMMAX)):
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
                raise ValueError(f"'{self.NUMANGS}' not a valid NUMANGS value, \
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

    def get_logical_record_order(self,file='input_rrtm'):
            '''
            Get record order to print out. Logical order means
            no repeated records.
            
            Options: file = 'input_rrtm', 'in_cld_rrtm'
            '''
            
            #go through logic
            if file == 'input_rrtm':
                records = ['1.1','1.2','1.4']
                if self.IATM == 0:
                    records.append('2.1')
                    records.append('2.1.1')
                    records.append('2.1.2')
                    if self.NMOL > 7:
                        records.append('2.1.3')
                    if self.IXSECT == 1:
                        records.append('2.2')
                        records.append('2.2.1')
                        records.append('2.2.2')
                        records.append('2.2.3') #dummy
                        records.append('2.2.4')
                        if self.IXMOLS > 7:
                            records.append('2.2.5')
                elif self.IATM == 1:
                    records.append('3.1')
                    records.append('3.2')
                    if self.IBMAX == 0:
                        records.append('3.3A')
                    else:
                        records.append('3.3B') #GREEDY
                    if self.MODEL == 0:
                        records.append('3.4')
                        records.append('3.5')
                        records.append('3.6.1')
                    if self.IXSECT == 1:
                        records.append('3.7')
                        records.append('3.7.1')
                        if self.IPRFL == 0: 
                            records.append('3.8')
                            records.append('3.8.1')
                            records.append('3.8.2')

            elif file == 'in_cld_rrtm':
                #iterate/read over records
                records = ['C1.1']
                if (self.INFLAG == 1) or (self.INFLAG == 2):
                        records.append('C1.2')
                elif (self.INFLAG == 0) or (self.INFLAG == 10):
                    for i in range(len(self.CLAY)): #number of cloudy layers
                        records.append('C1.3')
                        if self.INFLAG == 10:
                            raise NotImplementedError('INFLAG=10 (spectrally-resolved COD) not yet supported!')
                            for i in range(15):
                                records.append('C1.3a')
            
            return records
    
    def get_explicit_record_order(self,file='input_rrtm'):
        '''Get line-by-line records to print out.
        
        Options: file = 'input_rrtm', 'in_cld_rrtm'
        '''
        #go through logic
        if file == 'input_rrtm':
            records = ['1.1','1.2','1.4']
            if self.IATM == 0:
                records.append('2.1')
                for i in range(self.NLAYRS):
                    records.append('2.1.1')
                    records.append('2.1.2')
                    if self.NMOL > 7:
                        records.append('2.1.3')
                if self.IXSECT == 1:
                    records.append('2.2')
                    records.append('2.2.1')
                    records.append('2.2.2')
                    for i in range(self.NLAYRS):
                        records.append('2.2.3') #dummy
                        records.append('2.2.4')
                        if self.IXMOLS > 7:
                            records.append('2.2.5')
            elif self.IATM == 1:
                records.append('3.1')
                records.append('3.2')
                if self.IBMAX == 0:
                    records.append('3.3A')
                else:
                    records.append('3.3B') #GREEDY
                if self.MODEL == 0:
                    records.append('3.4')
                    for i in range(abs(self.IMMAX)):
                        records.append('3.5')
                        records.append('3.6.1')
                if self.IXSECT == 1:
                    records.append('3.7')
                    records.append('3.7.1')
                    if self.IPRFL == 0: 
                        records.append('3.8')
                        for i in range(self.LAYX):
                            records.append('3.8.1')
                            records.append('3.8.2')

        elif file == 'in_cld_rrtm':
            #iterate/read over records
            records = ['C1.1']
            if (self.INFLAG == 1) or (self.INFLAG == 2):
                for i in range(1 if type(self.CLAY) != list else len(self.CLAY)): #number of cloudy layers
                    records.append('C1.2')
            elif (self.INFLAG == 0) or (self.INFLAG == 10):
                for i in range(1 if type(self.CLAY) != list else len(self.CLAY)): #number of cloudy layers
                    records.append('C1.3')
                    if self.INFLAG == 10:
                        raise NotImplementedError('INFLAG=10 (spectrally-resolved COD) not yet supported!')
                        for i in range(15):
                            records.append('C1.3a')
        return records
    
    def get_format(self,rec): 
        '''
        Get dict of Fortran format-strings for each record.

        It's a method since some record formats (xsec records 2.1.1-3 and 2.2.4-5) 
        depend on the values of other records (IFORM and IFRMX).
        '''
        
        #dictionary of all record formats. Dynamic formats are stored as methods.
        #changed all E formats to ES and two E formats to F to align with example input file encoding
        formats = {
            '1.1':    '(1A80)',
            '1.2':    '(49X, I1, 19X, I1, 12X, I1, I2, 2X, I3, 4X, I1)',
            '1.4':    '(F10.3,  1X, I1, 2X, I1, 16F5.3)', #changed from E to F
            '2.1':    '(1X,I1, I3, I5)',
            '2.1.1':  lambda self: f"({'F10.4' if self.IFORM==0 else 'ES15.7'}, F10.4, 23X, F8.3, F7.2,  7X, F8.3,   F7.2)",
            '2.1.2':  lambda self: f"({'8ES10.3' if self.IFORM==0 else '8ES15.7'})",
            '2.1.3':  lambda self: f"({'8ES10.3' if self.IFORM==0 else '8ES15.7'})",
            '2.2':    '(I5)',
            '2.2.1':  '(7A10,(/,8A10))',
            '2.2.2':  '(1X,I1)',
            '2.2.3':  '(A1)', #dummy record
            '2.2.4':  lambda self: f"({'7ES10.3' if self.IFRMX==0 else '7ES15.7'})",
            '2.2.5':  lambda self: f"({'8ES10.3' if self.IFRMX==0 else '8ES15.7'})",
            '3.1':    '(I5, 5X, I5, 5X, I5, I5, I5, 3X, I2, F10.3, 20X, F10.3)',
            '3.2':    '(F10.3,  F10.3)',
            '3.3A':   '(F10.3,  F10.3,  F10.3, F10.3, F10.3)',
            '3.3B':   '(8F10.3)',
            '3.4':    '(I5, 3A8)',
            '3.5':    '(F10.3, F10.3, F10.3, 5X, A1, A1, 3X, 28A1)', #changed from E to F
            '3.6.1':  '(8ES10.3)',
            '3.7':    '(I5, I5, I5)',
            '3.7.1':  '(7A10,(/,8A10))',
            '3.8':    '(I5, I5, A50)',
            '3.8.1':  '(F10.3, 5X, 35A1)',
            '3.8.2':  '(8ES10.3)',
            'C1.1':   '(3X, I2,  4X, I1,  4X, I1)',
            'C1.2':   '(A1, 1X, I3, ES10.3, ES10.3, ES10.3, ES10.3, ES10.3)', #changed from E10.5 to ES10.3
            'C1.3':   '(A1, 1X, I3, ES10.3, ES10.3, ES10.3, ES10.3, ES10.3)', #changed from E10.5 to ES10.3
            'C1.3A':  '(15X, E10.5, E10.5, 16E10.5)'
        }
        
        #get format
        fmt = formats[rec]
        
        #if format is a method, evaluate it
        if hasattr(fmt, '__call__'):
            fmt = fmt(self)
            
        #return format
        return fmt
    
    def get_fields(self,rec):
        '''
        Get dict of lists of field names for each record.

        It's a method since the number and names of many records' fields 
        depend on a field stored in some previous record. If a value is a
        function, it will be evaluated with the fields currently read in
        as attributes.
        '''
        
        #dictionary of all record formats. Dynamic formats are stored as methods.
        records_fields = {
            '1.1':     ['CXID'],
            '1.2':     ['IATM',  'IXSECT', 'ISCAT',  'NUMANGS',   'IOUT',   'ICLD'],
            '1.4':     ['TBOUND',  'IEMIS', 'IREFLECT', *[f'SEMISS({IB})' for IB in range(1,16+1)]],
            '2.1':     ['IFORM', 'NLAYRS', 'NMOL'],
            '2.1.1':   ['PAVE',  'TAVE',    'PZ(L-1)',  'TZ(L-1)',   'PZ(L)',  'TZ(L)'],
            '2.1.2':   ['WKL(1,L)','WKL(2,L)','WKL(3,L)','WKL(4,L)','WKL(5,L)','WKL(6,L)','WKL(7,L)','WBROAD(L)'],
            '2.1.3':   lambda self: [f'WKL({M},L)' for M in range(self.NMOL-7)],
            '2.2':     ['IXMOLS'],
            '2.2.1':   lambda self: [f'XSNAME({I})' for I in range(1, self.IXMOLS+1)],
            '2.2.2':   ['IFRMX'],
            '2.2.3':   ['_'], #dummy record
            '2.2.4':   lambda self: [f'XAMNT({I})' for I in range(1, 8)],
            '3.1':     ['MODEL',   'IBMAX',  'NOPRNT',  'NMOL', 'IPUNCH',   'MUNITS',    'RE',      'CO2MX'],
            '3.2':     ['HBOUND','HTOA'],
            '3.3A':    ['AVTRAT', 'TDIFF1', 'TDIFF2', 'ALTD1', 'ALTD2'],
            '3.3B':    lambda self: [f"{'Z' if self.IBMAX>0 else 'P'}BND({I})" for I in range(1, abs(self.IBMAX)+1)],
            '3.4':     ['IMMAX','HMOD'],
            '3.5':     ['ZM', 'PM', 'TM', 'JCHARP', 'JCHART', *[f'JCHAR({K})'for K in range(1,28+1)]],
            '3.6.1':   lambda self: [f'VMOL({K})'for K in range(1,self.NMOL+1)],
            '3.7':     ['IXMOLS','IPRFL','IXSBIN'],
            '3.7.1':   lambda self: [f'XSNAME({I})' for I in range(1, self.IXMOLS+1)],
            '3.8':     ['LAYX','IZORP','XTITLE'],
            '3.8.1':   ['ZORP', *[f'JCHARX({K})'for K in range(1,28+1)]], #JCHAR(K) is already taken by record 3.5
            '3.8.2':   lambda self: [f'DENX({K})' for K in range(1, self.IXMOLS+1)],
            'C1.1':    ['INFLAG', 'ICEFLAG', 'LIQFLAG'],
            'C1.2':    ['TESTCHAR','CLAY','CLDFRAC','CWP','FRACICE','EFFSIZEICE','EFFSIZELIQ'], #changed LAY to CLAY to differentiate from aerosol
            'C1.3':    lambda self: ['TESTCHAR', 'CLAY', 'CLDFRAC', 'TAUCLD', 
                                     'SINGLE-SCATTERING ALBEDO', *[f'PMOM({N})' for N in range(self.NSTR)]],
            'C1.3A':   lambda self: ['TAUCLD', 'SINGLE-SCATTERING ALBEDO', *[f'PMOM({N})' for N in range(self.NSTR)]]
        }
        
        #get fields
        fields = records_fields[rec]
        
        #if fields is a method, evaluate it
        if hasattr(fields, '__call__'):
            fields = fields(self)
            
        #return fields
        return fields