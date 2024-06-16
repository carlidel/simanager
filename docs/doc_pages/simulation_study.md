# Overview of ```SimulationStudy```

## Introduction

```SimulationStudy``` is a dataclass that is used to represent a simulation study. It is used to create the directory structure of the study, and to launch the simulations. It is also used to keep track of the status of the simulations, and to easily inspect the results of the study.

A ```SimulationStudy``` is created by loading a folder with a ```simulation_study.yaml``` file, which contains the parameters of the study. The position of the ```simulation_study.yaml``` file is expected to be the root of the study. The ```SimulationStudy``` dataclass is then used by the manager to create the directory structure and launch the simulations.

The ```SimulationStudy``` dataclass contains a list of ```ParameterInspection``` dataclasses, which are used to generate the specialized parameter files for each simulation. The ```ParameterInspection``` dataclass is a container for the parameters to be varied, and it is used to generate a list of specialized parameter files, which will be used by the manager to create the various simulation cases to specialize and launch.

## Structure of ```simulation_study.yaml```

Here is a template of a ```simulation_study.yaml``` file:

```yaml
study_name: "name_of_the_study"
original_folder: "$STUDYPATH/master_study"
main_file: "main_script.sh"
config_file: "params.yaml"
# The following parameters are used to generate the study
parameters_inspected:
  - parameter_name: "parameters/seed"
    inspection_method: "range"
    min_value: 1
    max_value: 4
    combination_idx: 0
    combination_method: "meshgrid"
    parameter_file_name: "mxatt"
  # ...other parameters...

test_case:
    - parameters/num_particles: 1

environ_dict:
    WEIRDPATH: "/this/is/a/weird_path"
```

The ```study_name``` key is used to specify the name of the study, and will name consequently the folder containing the simulation files and the directory structure.

The ```original_folder``` key is used to specify the path of the master study, which will be copied into the study folders and then specialized accordingly. In the ```original_folder``` there must be:
    * The ```main_file```, a bash script that will launch/execute the simulation or run other simulation files.
    * The ```config_file```, a .yaml file that will contain the various parameters of the simulation. It is expected that the ```SimulationStudy``` only scans parameters that are already present in the ```config_file```.
    * All other support files needed by the simulation (it is currently expected that the main script will launch a Python script, which then loads the YAML parameter file, so the current defaults and examples are for Python simulations).

The ```parameters_inspected``` list, contains a list of ```ParameterInspection``` dataclasses, and specifies the parameters to be varied. Refer to the ```ParameterInspection``` page for more information on how to specify the parameters to be varied.

The ```test_case``` key is used to specify a list of parameters to be used for a test case. This way, one can easily set up a quick test case to check that the simulation is working as expected. The test case will be placed in a ```test``` folder, which will be created in the ```study_name\scan``` folder, next to the other simulation cases.

The ```environ_dict``` key is used to specify a dictionary of environment variables to be used for the path expansion. Refer to the ```ParameterInspection``` page for more information on how to use this feature.

## Important guidelines to follow

1. The job in the ```original_folder``` **must** ultimately generate all the output files in a folder named ```output_files``` in the same folder as the main script. This is necessary in order to be able to easily transfer the output files to the desired location, and to be able to easily inspect the results of the study.
2. In the case of remote job executions, the tracking of the state of the simulations has to be explicitly checked with the command ```simanager status```, which will print the status of the simulations. This is necessary because the remote job execution does not allow for the immediate inspection of the simulation status, and it is probed (partially) by the manager by checking the presence of flag files in the folder ```remote_touch_files```.
3. In the case of HTcondor executions, where EOS files might be required to be staged in, there is the possibility to leverage on an internal routine for EOS-compliant stage-in. Currently, filepath specified at the first level of depth in the parameter file are detected and moved to a folder named ```eos_files``` in the scratch disk of the remote machine. This is done by the ```simanager run_htcondor``` command, which will stage-in the EOS files before launching the simulations.

## Getting started quickly with the CLI tools

### 1. Bootstrap a new study from a template

The ```simanager``` CLI tool can be used to create a new study from a template. The template is a folder containing a ```simulation_study.yaml``` file, alongside some support files. The ```simanager``` CLI tool can be used as follows:
```bash
simanager copy-template -n <name_of_the_root_folder>
```
and will create a new folder with the name specified by the ```-n``` flag, and copy the template files into it. The ```-n``` flag is optional, and if not specified, the name of the folder will be ```sim_study```.

Note that then the next commands must be executed from within the folder of the ```simulation_study.yaml``` file.

### 2. Initialize the folder structure

Once the ```simulation_study.yaml``` file is ready, the folder structure can be initialized by means of the ```simanager``` CLI tool:
```bash
simanager create
```
This will create the folder structure of the study, and will copy the ```original_folder``` into the ```study_name\scan``` folder, alongside some support folders. The ```SimulationStudy``` is now ready to be run on the various platforms.

### 3. Run the study

The ```SimulationStudy``` can then be passed to three different executor functions, which will launch the simulations in the desired environment, namely:
```bash
simanager run_local
simanager run_htcondor
simanager run_slurm
```
these commands will look by default for a ```run_config.yaml``` file in the root folder of the study, which will contain the arguments of the executor functions. The ```run_config.yaml``` file is optional, and if not present, the executor functions will use the default arguments. Refer to the docstring of the executor functions for more information on the arguments.

### 4. cat out and err files

From within the directory of the ```simulation_study.yaml```, you can run the command ```simanager cat-out``` and ```simanager cat-err``` to have automatically printed on terminal the content of the out and err files of the various jobs, which by default are placed into... an ```out``` and ```err``` folder!

### 5. NUKE IT ALL

From within the directory of the ```simulation_study.yaml```, you can run the command ```simanager nuke``` to delete the entire study folder. This command is **DANGEROUS** and will delete the entire study folder, so use it with caution.