# parserrtm
A high-level interface for running the Rapid Radiative Transfer Model (RRTM) in Python, both longwave (RRTM_LW) and shortwave (RRTM_SW) versions. A high-level interface helps because the Fortran text file inputs are unreadable by humans and have a complicated structure. With this library, all you interact with are named input parameters and calculation results. The strength of `parserrtm` is that it supports (almost) every possible configuration of both models (reach out if a configuration you need isn't supported!).

With `parserrtm`, you can simply take an existing example input file and modify the field of interest to you by name. The library takes care of underlying file I/O and just gives you a dataset with the results of your calculation.

# installing parserrtm

Two components are needed: (1) this Python library and (2) executables for the RRTM Fortran codes. The Python library is easy to install and I have a [compilation guide](https://github.com/bertrandclim/parserrtm/blob/main/rrtm_compiling_guide.md) for getting the RRTM executables from `rrtm_lw/` and `rrtm_sw/` in this repository. If you are running anything other than Red Hat Enterprise Linux 8.10, you will probably need to compile RRTM.

I've only ever successfully compiled RRTM on linux with the PGI/NVIDIA compiler, so if you're on another OS I'd reccomend using a virtual machine (like `lima` for macOS).

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

The `InputLW` and `InputSW` classes expose RRTM parameter fields as attributes you can assign to or declare. For explanations of these parameter fields, see `rrtm_lw/rrtm_instructions` and `rrtm_sw/rrtm_sw_instructions`. Each instance of `InputLW` or `InputSW` holds all the data for a single RRTM run.

You can initialize an `InputLW` or `InputSW` object from existing RRTM input text files or a dictionary. Once you have an `InputLW` or `InputSW` object that sets up the kind of calculation you want, you can simply modify the attributes of interest and rerun the calculations.

Calculations are handled by the `Runner` class. `Runner` takes a series of input objects, runs RRTM (in parallel) for each input, and loads the output back into Python.

Coming soon: some usage example tutorials and documentation pages. For now, the docstrings of `Runner`, `Input`, `InputSW`, and `InputLW` should be a good starting point.
