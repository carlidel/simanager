# simanager
## Description

```simanager``` is a simple manager for your simulations. It is designed to automatically create and manage a directory structure for your simulations, in order to keep your simulations organized and easy to find, and guarantee reproducibility.

Currently, it (tries to) support the following execution environments:

* Local machine;
* [SLURM](https://slurm.schedmd.com/) clusters on CNAF;
* [HTCondor](https://research.cs.wisc.edu/htcondor/) clusters on CERN's lxplus machines;

## Installation

```simanager``` is available on PyPI, so you can install it with:

```bash
pip install simanager
```

## Usage

```simanager``` expects a simulation study to be structured in a precise way. One must first create a master directory, which will contain:

* a main script in bash, which will be used to launch the simulation;
* a master parameter file in YAML, which will contain the parameters of the simulation and will be specialized by the manager for each simulation;
* all support files needed by the simulation (it is currently expected that the main script will launch a python script, which then loads the YAML parameter file, so the current defaults and examples are for python simulations).

After the master study is constructed, one can define a set of parameters to be varied, in order to do that, the ```ParameterInspection``` dataclass is defined in the ```simanager/parameter_inspection.py``` file. The ```ParameterInspection``` dataclass is a container for the parameters to be varied, and it is used to generate a list of specialized parameter files, which will be used by the manager to launch the simulations.

The best way to create a simulation study, is to compose in the desired root directory a ```simulation_study.yaml``` file, which will contain the parameters of the study. This file will be used to construct a ```SimulationStudy``` dataclass, which will be used by the manager to create the directory structure and launch the simulations.

Example of a ```simulation_study.yaml``` file:

```yaml
# simulation parameters
study_name: "test_local"
study_path: "./"
original_folder: "/home/camontan/cernbox/work/code/generic_study/tests/example_master_study"
main_file: "main_script.sh"
config_file: "params.yaml"
# The following parameters are used to generate the study
parameters_inspected:
  - parameter_name: "numeric_parameters/max_attempts"
    inspection_method: "range"
    min_value: 1
    max_value: 4
    combination_idx: 0
    combination_method: "meshgrid"
    parameter_file_name: "mxatt"
  - parameter_name: "numeric_parameters/timeout_seconds"
    inspection_method: "linspace"
    min_value: 1
    max_value: 2
    n_samples: 4
    combination_idx: 0
    combination_method: "meshgrid"
    parameter_file_name: "tout"
  - parameter_name: "numeric_list"
    inspection_method: "custom"
    values: [[1, 2, 3], [4, 5, 6]]
    parameter_file_name: "nlist"
```

Then one can load up the folder with the ```SimulationStudy``` dataclass:

```python
import simanager as sim
study = sim.SimulationStudy.load_folder("./")
```

The ```SimulationStudy``` dataclass will be used by the manager to create the directory structure and launch the simulations. The manager can be used as follows:

```python
study.initialize_folders()
study.print_sim_status()
```

The ```SimulationStudy``` can then be passed to three different executor functions, which will launch the simulations in the desired environment, namely:

1. ```sim.job_run_local```, which will launch the simulations on the local machine;
2. ```sim.job_run_slurm```, which will launch the simulations on a SLURM cluster;
3. ```sim.job_run_htcondor```, which will launch the simulations on a HTCondor cluster.