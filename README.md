# parserrtm
A high-level interface for running the Rapid Radiative Transfer Model (RRTM) in Python, both longwave (RRTM_LW) and shortwave (RRTM_LW) versions. A high-level interface helps because the Fortran text file inputs are unreadable by humans. With this library, all you interact with are named input parameters and calculation results.

For example, you can simply take an existing example input file and modify the field of interest to you. The library takes care of underlying file I/O and just gives you a dataset with the results of your calculation.

# installing parserrtm

Two components are needed: (1) this Python library and (2) executables for the RRTM Fortran codes. The Python library is easy to install and linux binaries of the RRTM executables are distributed in `/rrtm_lw/` and `/rrtm_sw/`. 

For MacOS, I reccomend using `lima` for a Linux virtual machine. If the binaries don't work on your system, you will need to compile RRTM from source (see `rrtm_compiling_guide.md`).

## from pypi
```
git clone https://github.com/bertrandclim/parserrtm.git
pip install parserrtm
```
## from git repo
```
git clone https://github.com/bertrandclim/parserrtm.git
cd parserrtm
python3 -m build
pip install dist/parserrtm-0.0.1.tar.gz
```

# after installing
First, you should benchmark your RRTM executable. Open `/tests/run_stock_examples.ipynb` in Jupyterlab (or similar) and hit `notebook -> run all cells`. This will run a series of example cases for RRTM_LW and RRTM_SW and validate the output.

# overview
`parserrtm` offers three high-level classes for running this radiative transfer model: `InputLW`, `InputSW`, and `Runner`.

The `InputLW` and `InputSW` classes expose RRTM parameter fields as attributes you can assign to or declare (see `rrtm_lw/rrtm_instructions` and `rrtm_sw/rrtm_sw_instructions` for a definition of fields). Each instance holds all the data for a single RRTM run.

You can initialize an `InputLW` or `InputSW` object from existing RRTM input files or a dictionary. Once you have an `InputLW` or `InputSW` that sets up the kind of calculation you want, you can simply modify the attributes of interest for your research and rerun the calculations.

Calculations are handled by the `Runner` class. It takes a series of input objects, runs RRTM, and loads the output back into Python.

Coming soon: some usage example tutorials and documentation pages. For now, the docstrings of `Runner`, `Input`, `InputSW`, and `InputLW` should be a good starting point.
