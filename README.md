# parserrtm
Python wrapper for RRTM_LW ASCII text interface. Below are some resources for compiling and running RRTM_LW, which dovetail into instructions how to use `parserrtm` to run RRTM_LW.

# getting started

## 1. compile RRTM_LW
### On a supercomputer
What I did on the RMACC Alpine supercomputer:

1. Launch into a compiling node (this varies from machine to machine)
  ```bash
acompile
```
2. Load the `pgf90` compiler
   ```bash
   module load nvhpc_sdk
   ``` 
4. Clone needed repositories
   ```bash
   git clone https://github.com/AER-RC/RRTM_LW
   git clone https://github.com/AER-RC/aer_rt_utils_f77
   ```
3. Compile. If maketools are not installed use your package manager to install them.
   ```bash
   cd ./RRTM_LW
   make -f makefiles/make_rrtm

If you want to use another compiler or platform, you need to link the relevant file in aer_rt_utils_f77 into `./RRTM_LW/src`. For example, to use the GNU Fortran compiler:
```bash
cd ./RRTM_LW
ln -s ../aer_rt_utils_f77/util_gfortran.f ./src/util_gfortran.f
```
and then change `FC_TYPE` from `pgi` to `FC_TYPE=gnu` in `makefiles/makefile.common`. But this only works by default on MacOS. If you want to use the GNU compiler on Linux, then add 
```bash
# Open source GNU Fortran 95/2003 compiler
                ifeq ($(FC_TYPE),gnu)
                        FC = gfortran
                        FCFLAG =   -fdefault-integer-8 -fdefault-real-8 -Wall -frecord-marker=4 --std=legacy
                        UTIL_FILE = util_gfortran.f
                endif
```
under the `ifeq ($(PLATFORM),Linux)` codeblock in `makefiles/makefile.common`. Note that `makefile.common` needs `--std=legacy` added to the `FCFLAG` line under the Darwin code block as well if you're compiling for MacOS.
At some point I might make fork the repo with a fixed `makefile.common`.

But when I compiled RRTM_LW this way, the test cases using DISORT `ISCAT=1` would fail, though the other test cases succeeded. 
So I would reccomend the `pgf90` compiler. Note that the other compilers (`ifort`,`g95`) no longer appear to be supported for MacOS.

### On a local machine
Since I wanted to use DISORT (`ISCAT=1`) for my calculations, I used `lima` to run a linux virtual machine with the `pgf90` compiler.
1. Install lima (more info [here](https://jvns.ca/blog/2023/07/10/lima--a-nice-way-to-run-linux-vms-on-mac/))
```bash
brew install lima
```
2. Boot up and launch into the virtual machine
```bash
limactl start default
lima
```
3. Install the PGF compiler (more info [here](https://developer.nvidia.com/hpc-sdk-downloads))... it's big and takes a while to finish.
```bash
curl https://developer.download.nvidia.com/hpc-sdk/ubuntu/DEB-GPG-KEY-NVIDIA-HPC-SDK | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-hpcsdk-archive-keyring.gpg
echo 'deb [signed-by=/usr/share/keyrings/nvidia-hpcsdk-archive-keyring.gpg] https://developer.download.nvidia.com/hpc-sdk/ubuntu/amd64 /' | sudo tee /etc/apt/sources.list.d/nvhpc.list
sudo apt-get update -y
sudo apt-get install -y nvhpc-23-9
```
4. Install maketools
  ```bash
sudo apt-get install make
```
5. Restart the virtual machine and launch back in
  ```bash
exit
limactl stop default
limactl start default
lima
```
6. Add the PGF compilers to the shell path ([source](https://docs.nvidia.com/hpc-sdk/hpc-sdk-install-guide/index.html#install-linux-end-usr-env-settings))
  ```bash
NVARCH=`uname -s`_`uname -m`; export NVARCH
NVCOMPILERS=/opt/nvidia/hpc_sdk; export NVCOMPILERS
MANPATH=$MANPATH:$NVCOMPILERS/$NVARCH/23.9/compilers/man; export MANPATH
PATH=$NVCOMPILERS/$NVARCH/23.9/compilers/bin:$PATH; export PATH
```
7. Clone needed repositories
   ```bash
   git clone https://github.com/AER-RC/RRTM_LW
   git clone https://github.com/AER-RC/aer_rt_utils_f77
   ```
8. Compile RRTM.
   ```bash
   cd ./RRTM_LW
   make -f makefiles/make_rrtm

## 2. Run RRTM test cases to verify compilation
The GitHub version of RRTM doesn't come with run examples; only the version hosted on AER's website (v3.3) does.
1. Download test cases
```bash
wget http://files.aer.com/rtweb/aer_rrtm/aer_rrtm_v3.3.tar.gz
tar -xvf ./aer_rrtm_v3.3.tar.gz
```
2. Point test case script to RRTM binary. In `/run_examples/script.run_testcases`, replace `rrtm` with `path/to/rrtm/binary` (e.g. `$rrtm_prog = ../../RRTM_LW/rrtm_v3.3.1_linux_pgf90`).

3. The script to run test cases uses `tcsh`, so if `tcsh` is not installed, install it now
  ```bash
sudo apt-get install tcsh
```

4. Run test cases. After each "Running..." statement, a "FORTRAN STOP" should be printed to indicate successful termination.
```bash
cd ../rrtm_lw/run_examples
./script.run_testcases
```

