    
from .input import Input

class InputSW(Input):
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
                    for i in range(len(self.LAY)): #number of cloudy layers
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
                    for i in range(self.IMMAX):
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
                for i in range(1 if type(self.LAY) != list else len(self.LAY)): #number of cloudy layers
                    records.append('C1.2')
            elif (self.INFLAG == 0) or (self.INFLAG == 10):
                for i in range(1 if type(self.LAY) != list else len(self.LAY)): #number of cloudy layers
                    records.append('C1.3')
                    if self.INFLAG == 10:
                        raise NotImplementedError('INFLAG=10 (spectrally-resolved COD) not yet supported!')
                        for i in range(15):
                            records.append('C1.3a')
        return records
    
    def get_format(self,rec): 
        '''
        Get dict of Fortran format-strings for each record.

        It's a method since some record formats (e.g., xsec records 2.1.1-3 and 2.2.4-5) 
        depend on the values of other records (IFORM and IFRMX).
        '''
        
        #dictionary of all record formats. Dynamic formats are stored as methods.
        #changed all E formats to ES and two E formats to F to align with example input file encoding
        formats = {
            '1.1':    '(1A80)',
            '1.2':    '(18X, I2, 29X, I1, 32X, I1, 1X, I1, 2X, I3, 4X, I1, 3X, I1, I1)',
            '1.2.1':  '(12X, I3, F7.4, 4X, I1, 14F5.3)',
            '1.4':    '(11X,  I1, 2X, I1, 14F5.3)',
            '2.1':    '(1X,I1, I3, I5)', #same as LW, conditional on IATM=0
            '2.1.1':  lambda self: f"({'F10.4' if self.IFORM==0 else 'ES15.7'}, F10.4, 23X, F8.3, F7.2,  7X, F8.3,   F7.2)", #same as LW
            '2.1.2':  lambda self: f"({'8ES10.3' if self.IFORM==0 else '8ES15.7'})", #same as LW
            '2.1.3':  lambda self: f"({'8ES10.3' if self.IFORM==0 else '8ES15.7'})", #same as LW
            '3.1':    '(I5, 5X, I5, 5X, I5, I5, I5, 3X, I2, F10.3, 20X, F10.3, F10.3)',
            '3.2':    '(F10.3,  F10.3)', #same as LW
            '3.3A':   '(F10.3,  F10.3,  F10.3, F10.3, F10.3)', #same as LW
            '3.3B':   '(8F10.3)', #same as LW
            '3.4':    '(I5, 3A8)', #same as LW
            '3.5':    '(F10.3, F10.3, F10.3, 5X, A1, A1, 3X, 28A1)', #changed from E to F, same as LW
            '3.6.1':  '(8ES10.3)', #same as LW
            '3.8':    '(I5, I5, A50)', #same as LW
            '3.8.1':  '(F10.3, 5X, 35A1)', #same as LW
            '3.8.2':  '(8ES10.3)', #same as LW
            'C1.1':   '(4X, I1,  4X, I1,  4X, I1)', #very similar to LW
            'C1.2':   '(A1, 1X, I3, ES10.3, ES10.3, ES10.3, 16ES10.3)', #changed from E10.5 to ES10.3
            'C1.3':   '(A1, 1X, I3, ES10.3, ES10.3, ES10.3, ES10.3, ES10.3)', #changed from E10.5 to ES10.3, same as LW
            'A1.1':   '(3X, I2)',
            'A2.1':   '(3X, I2, 4X, I1, 4X, I1, 4X, I1, 3F8.2)',
            'A2.1.1': lambda self: f"(2X, I3, {'F7.4' if self.IAOD == 0 else '14F7.4'})",
            'A2.2':   '(14F5.2)',
            'A2.3':   '(14F5.2)'
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
            '1.2':     ['IAER', 'IATM', 'ISCAT',  'ISTRM',  'IOUT', 'ICLD', 'IDELM', 'ICOS'], #different from LW
            '1.2.1':   ['JULDAT', 'SZA', 'ISOLVAR', *[f'SOLVAR({IB})' for IB in range(16,29+1)]], #different from LW
            '1.4':     ['IEMIS', 'IREFLECT', *[f'SEMISS({IB})' for IB in range(1,16+1)]], #different from LW
            '2.1':     ['IFORM', 'NLAYRS', 'NMOL'],
            '2.1.1':   ['PAVE',  'TAVE',    'PZ(L-1)',  'TZ(L-1)',   'PZ(L)',  'TZ(L)'],
            '2.1.2':   ['WKL(1,L)','WKL(2,L)','WKL(3,L)','WKL(4,L)','WKL(5,L)','WKL(6,L)','WKL(7,L)','WBROAD(L)'],
            '2.1.3':   lambda self: [f'WKL({M},L)' for M in range(self.NMOL-7)],
            '3.1':     ['MODEL',   'IBMAX',  'NOPRNT',  'NMOL', 'IPUNCH',   'MUNITS',    'RE',      'CO2MX', 'REF_LAT'], #different from LW
            '3.2':     ['HBOUND','HTOA'],
            '3.3A':    ['AVTRAT', 'TDIFF1', 'TDIFF2', 'ALTD1', 'ALTD2'],
            '3.3B':    lambda self: [f"{'Z' if self.IBMAX>0 else 'P'}BND({I})" for I in range(1, abs(self.IBMAX)+1)],
            '3.4':     ['IMMAX','HMOD'],
            '3.5':     ['ZM', 'PM', 'TM', 'JCHARP', 'JCHART', *[f'JCHAR({K})'for K in range(1,28+1)]],
            '3.6.1':   lambda self: [f'VMOL({K})'for K in range(1,self.NMOL+1)],
            '3.8':     ['LAYX','IZORP','XTITLE'],
            '3.8.1':   ['ZORP', *[f'JCHARX({K})'for K in range(1,28+1)]], #JCHAR(K) is already taken by record 3.5
            '3.8.2':   lambda self: [f'DENX({K})' for K in range(1, self.IXMOLS+1)],
            'C1.1':    ['INFLAG', 'ICEFLAG', 'LIQFLAG'],
            'C1.3':    ['TESTCHAR','LAY','CLDFRAC', lambda self: 'TAUCLD' if self.INFLAG==0 else 'CWP',
                        'FRACICE','EFFSIZEICE','EFFSIZELIQ'], #C1.3 and C1.2 are swapped from LW
            'C1.2':    lambda self: ['TESTCHAR', 'LAY', 'CLDFRAC', 'TAUCLD' if self.INFLAG==0 else 'CWP', 
                                     'SINGLE-SCATTERING ALBEDO', *[f'PMOM({N})' for N in range(self.NSTR)]],
            'A1.1':    ['NAER'],
            'A2.1':    ['NLAY', 'IAOD', 'ISSA', 'IPHA', 'AERPAR(1)', 'AERPAR(2)', 'AERPAR(3)'],
            'A2.1.1': lambda self: ['LAY','AOD1'] if self.IAOD == 0 else ['LAY', *[f'AOD({IB})' for IB in range(16,29+1)]],
            'A2.2':    [*[f'SSA({IB})' for IB in range(16,29+1)]],
            'A2.3':    [*[f'PHASE({IB})' for IB in range(16,29+1)]]
        }
        
        #get fields
        fields = records_fields[rec]
        
        #if fields is a method, evaluate it
        if hasattr(fields, '__call__'):
            fields = fields(self)
            
        #return fields
        return fields