# Using parameter_inspection

## Overview and examples

The dataclass ```ParameterInspection``` is used to inspect the parameters of a ```SimulationStudy```. It is used to interpret the list of parameters to inspect indicated in the ```simulation_study.yaml file```. These scan instructions are expected to be placed under the ```parameters_inspected``` key of the yaml file, and are expected to follow the following format:

```yaml
    - parameter_name: # Full dictionary key of the parameter 
        inspection_method: # Method used to inspect the parameter
        min_value: # Minimum value of the parameter
        max_value: # Maximum value of the parameter
        n_samples: # Number of samples to be generated
        values: # Custom values to be used
        combination_idx: # Index if the parameter is part of a combination of parameters
        combination_method: # Method used to combine multiple parameters
        force_type: # Force the type of the parameter
        parameter_file_name: # Name to use in the folder name
```

Note that some of these keys are optional, while others are mandatory depending on the inspection method used. For a better overview of the different inspection methods, please refer to the docstring of the ```ParameterInspection``` dataclass.

Let us assume that we have in our master study the following parameter file:

```yaml
# parameters.yaml

input_file: "initial_conditions_1.txt"
output_file: "output_file.txt"

my_seed: 1234

settings:
    num_particles: 256
    magic_numbers: [1, 2, 3]
    a_random_float: 0.5

simulation_parameters:
    max_attempts: 100
    timeout_seconds: 600
```

We can then define the ```parameters_inspected``` key in the ```simulation_study.yaml``` file as follows in order to achieve the following parameter scans:

### Simple scan of individual parameters

```yaml
parameters_inspected:
  - parameter_name: "settings/a_random_float"
    inspection_method: "linspace"
    min_value: 0.0
    max_value: 6.0
    n_samples: 10
    force_type: "float"
    parameter_file_name: "rndf"
  - parameter_name: "my_seed"
    inspection_method: "custom"
    values: [1, 2, 3, 4, 5]
    force_type: "int"
    parameter_file_name: "s"
```

This will generate a total of 50 parameter combinations, which will then follow the convention ```case_rndf_<value>_s_<value>```.

Note how the ```parameter_name``` key is used to specify the full dictionary key of the parameter to be inspected. When a parameter is in a nested dictionary, like the ```a_random_float``` parameter, a path-like notation is used.

Note that the ```force_type``` key is used to force the type of the parameter, which is useful when the parameter is not a float or an integer, but a string or a list. In this case, the ```force_type``` key is not necessary, since the parameter is already an integer, but it is used for demonstration purposes. The ```custom``` inspection method is used to specify a list of values to be used for the parameter scan. The ```linspace``` inspection method is used to generate a linearly spaced list of values between the ```min_value``` and the ```max_value```. Refer to the docstring of the ```ParameterInspection``` dataclass for more information and alternative inspection methods.

### Combination of parameters

```yaml
parameters_inspected:
  - parameter_name: "settings/num_particles"
    inspection_method: "custom"
    values: [15, 18, 42, 256]
    combination_idx: 0
    combination_method: "individual"
    parameter_file_name: "np"
  - parameter_name: "settings/magic_numbers"
    inspection_method: "custom"
    values: [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]]
    combination_idx: 0
    combination_method: "individual"
    parameter_file_name: "mn"
```

This will generate a total of 4 parameter combinations, which correspond to a zip-like combination of the two lists of values. The ```combination_idx``` key is used to specify the index of the parameter combination, while the ```combination_method``` key is used to specify the method used to combine the parameters. In this case, the ```individual``` method is used to generate a zip-like combination of the parameters. Refer to the docstring of the ```ParameterInspection``` dataclass for more information and alternative combination methods.

### Specialization of a path-like parameter

```yaml
parameters_inspected:
  - parameter_name: "input_file"
    inspection_method: "custom"
    values: [
        "$STUDYPATH/../input_data/initial_conditions_1.txt",
        "$STUDYPATH/../input_data/initial_conditions_2.txt",
        "$STUDYPATH/../input_data/initial_conditions_3.txt"
        "$WEIRDPATH/initial_conditions_3.txt"
    ]
    force_type: "path"    
    parameter_file_name: "in"

environ_dict:
    WEIRDPATH: "/this/is/a/weird_path"
```

This will generate a total of 4 parameter combinations, which correspond to the 4 different paths specified in the ```values``` key. Note that the ```force_type``` key is used to force the type of the parameter to be a path. This is necessary to enforce the correct path expansion. Note that the ```environ_dict``` key is used to specify a dictionary of environment variables to be used for the path expansion. Refer to the ```SimulationStudy``` docstring for that term. In this case, the ```WEIRDPATH``` environment variable is used to expand the path ```$WEIRDPATH/initial_conditions_3.txt```. The variable ```STUDYPATH``` is automatically defined by the manager as the path where the file ```simulation_study.yaml``` is located.

Consider using this method also for a single path parameter, since it is more robust to changes in the folder structure of the study. If the value provided is only one, the ```parameter_file_name``` key is not necessary and, if not provided, the case name will not be uselessly expanded more.



