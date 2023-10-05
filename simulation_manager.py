"""simulation_manager.py
Contains the SimulationManager abstract class, which is the base class for all 
simulation managers, which are specialized to different computing environments.
"""
import os
import pickle
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from multiprocessing import Manager, Pool

import numpy as np
import yaml


def clone_folder_content(source_folder, destination_folder):
    """
    Clones the content of a folder to another folder.
    """
    for item in os.listdir(source_folder):
        source_path = os.path.join(source_folder, item)
        destination_path = os.path.join(destination_folder, item)
        if os.path.isdir(source_path):
            shutil.copytree(source_path, destination_path)
        else:
            shutil.copy2(source_path, destination_path)


def float_filename_fomratter(float_number, truncate=3):
    """Formats a float number to a string with a maximum number of digits."""
    string = "{:.{prec}}".format(float(float_number), prec=truncate)
    string = string.replace(".", "d")
    return string


def update_nested_dict(nested_dict, key_chain, value):
    """
    Updates a nested dictionary with a value given a chain of keys.

    Parameters
    ----------
    nested_dict
        The nested dictionary to update.
    key_chain : str
        The chain of keys to access the value to update.
    value
        The value to update.

    Raises
    ------
    KeyError
        If the key is not found in the dictionary.
    """
    keys = key_chain.split("/")
    current_dict = nested_dict
    for key in keys[:-1]:
        if key not in current_dict:
            raise KeyError(f"Key '{key}' not found in dictionary")
        current_dict = current_dict[key]
        if not isinstance(current_dict, dict):
            raise ValueError(f"Key '{key}' is not a dictionary")
    current_dict[keys[-1]] = value


@dataclass
class ParameterInspection:
    parameter_name: str
    inspection_method: str
    # optional values
    min_value: float = None
    max_value: float = None
    n_samples: int = None
    values: list = None
    combination_idx: int = -1
    combination_method: str = None
    parameter_file_name: str = None

    @classmethod
    def from_dict(cls, dictionary):
        return cls(**dictionary)

    @classmethod
    def from_yaml(cls, yaml_path: str):
        with open(yaml_path, "r", encoding="utf-8") as f:
            dictionary = yaml.safe_load(f)
        return cls.from_dict(dictionary)

    def __post_init__(self):
        if self.inspection_method == "linspace":
            if not (
                self.min_value is not None
                and self.max_value is not None
                and self.n_samples is not None
            ):
                raise ValueError(
                    "If inspection_method is linspace, min_value, max_value, and n_samples must be specified."
                )
            self.values = list(
                np.linspace(self.min_value, self.max_value, self.n_samples)
            )
        elif self.inspection_method == "logspace":
            if not (
                self.min_value is not None
                and self.max_value is not None
                and self.n_samples is not None
            ):
                raise ValueError(
                    "If inspection_method is logspace, min_value, max_value, and n_samples must be specified."
                )
            self.values = list(
                np.logspace(
                    np.log10(self.min_value), np.log10(self.max_value), self.n_samples
                )
            )
        elif self.inspection_method == "custom":
            if not self.values is not None:
                raise ValueError(
                    "If inspection_method is custom, values must be specified."
                )

        if self.parameter_file_name is None:
            self.parameter_file_name = self.parameter_name


@dataclass
class SimulationStudy:
    """Class that contains the information about a simulation study.

    Parameters
    ----------
    study_name : str
        The name of the study.
    study_path : str, optional
        The path to the study folder. The default is os.getcwd().
    original_folder : str
        The path to the folder containing the original files to clone.
    main_file : str
        The name of the main file to execute. Must be a bash file.
    config_file : str
        The name of the file containing the parameters to update. Must be a yaml.
    parameters_inspected : list, optional
        The list of parameters to inspect. The default is None. Must be a list of
        ParameterInspection objects.
    """

    study_name: str
    study_path: str = os.getcwd()
    original_folder: str
    main_file: str
    config_file: str
    parameters_inspected: list[ParameterInspection] = field(default_factory=list)
    folders_created: bool = False

    def __post_init__(self):
        self.original_folder = os.path.abspath(self.original_folder)

    @classmethod
    def load_folder(cls, folder_path: str):
        """Loads a simulation study from a folder.

        Parameters
        ----------
        folder_path : str
            The path to the folder containing the simulation study.

        Returns
        -------
        simulation_study : SimulationStudy
            The simulation study.
        """
        simulation_study_file = os.path.join(folder_path, "simulation_study.yaml")
        with open(simulation_study_file, "r", encoding="utf-8") as f:
            simulation_study = yaml.safe_load(f)
        return cls(**simulation_study)

    def build_parameter_combinations(self):
        """Builds the parameter combinations.

        Returns
        -------
        combinations : list
            List of tuples, where each tuple contains the name of the parameter,
            the filename version of the parameter name, the value of the
            parameter, the number of values of the parameter, and the type of
            combination (single or multi).
        """
        p_names = [p.parameter_name for p in self.parameters_inspected]
        p_values = [p.values for p in self.parameters_inspected]
        p_idx = np.array([p.combination_idx for p in self.parameters_inspected])
        p_combo_methods = np.array(
            [p.combination_method for p in self.parameters_inspected]
        )
        p_file_names = [p.parameter_file_name for p in self.parameters_inspected]

        single_combinations = []
        for idx in p_idx:
            if p_idx == -1:
                single_combinations.append(
                    (
                        p_names[idx],
                        p_file_names[idx],
                        p_values[idx],
                        len(p_values[idx]),
                        "single",
                    )
                )

        unique_idx = np.unique(p_idx[p_idx != -1])
        joined_combinations = []
        for val in unique_idx:
            idxs = np.where(p_idx == val)[0]
            names = [p_names[idx] for idx in idxs]
            file_names = [p_file_names[idx] for idx in idxs]
            values = [p_values[idx] for idx in idxs]
            combo_method = p_combo_methods[idxs[0]]
            # check if all combo methods with same idx are the same
            if not all(p_combo_methods[idxs] == combo_method):
                raise ValueError(
                    "All combination methods with the same idx must be the same."
                )

            if combo_method == "individual":
                joined_combinations.append(
                    (names, file_names, values, len(values[0]), "multi")
                )
            elif combo_method == "meshgrid":
                vv = np.meshgrid(*values)
                vv = [v.flatten() for v in vv]
                joined_combinations.append((names, file_names, vv, len(vv[0]), "multi"))

        combinations = single_combinations + joined_combinations
        return combinations

    def yield_parameter_combinations(self):
        """Yields the parameter combinations. Yields progressively the various
        combinations of all parameters.

        Returns
        -------
        current_combination : list
            List of tuples, where each tuple contains the name of the parameter,
            the filename version of the parameter name, the value of the
            parameter, and the type of combination (single or multi).
        """
        combinations = self.build_parameter_combinations()
        n_values = np.array([c[3] for c in combinations], dtype=int)
        current_idx = np.zeros(len(n_values), dtype=int)
        total_combinations = np.prod([c[3] for c in combinations])
        print(f"Total number of parameter combinations: {total_combinations}")

        for i in range(total_combinations):
            # get the current combination
            current_combination = []
            for j, c in enumerate(combinations):
                if c[4] == "single":
                    current_combination.append((c[0], c[1], c[2][current_idx[j]], c[4]))
                elif c[4] == "multi":
                    for k, v in enumerate(c[2]):
                        current_combination.append(
                            (c[0][k], c[1][k], v[current_idx[j]], c[4])
                        )
            # update the indices
            current_idx += 1
            for idx, max_val in zip(current_idx, n_values):
                if idx == max_val:
                    current_idx[idx] = 0
                else:
                    break

            yield current_combination

    def initialize_folders(self):
        """Creates the folders for the study."""
        main_folder = os.path.join(self.study_path, self.study_name)
        os.makedirs(main_folder, exist_ok=True)
        os.makedirs(os.path.join(main_folder, "out"), exist_ok=True)
        os.makedirs(os.path.join(main_folder, "err"), exist_ok=True)
        os.makedirs(os.path.join(main_folder, "log"), exist_ok=True)

        os.makedirs(os.path.join(main_folder, "original_folder"), exist_ok=True)
        # clone the original folder content
        clone_folder_content(
            self.original_folder, os.path.join(main_folder, "original_folder")
        )

        simulation_info = {}
        # write the complete path of the main folder
        simulation_info["root_folder"] = os.path.abspath(main_folder)
        simulation_info["sim_not_started"] = []
        simulation_info["sim_finished"] = []
        simulation_info["sim_interrupted"] = []
        simulation_info["sim_error"] = []
        simulation_info["sim_running"] = []

        # create a folder for each parameter combination
        simulation_combos = {}
        for i, combination in enumerate(self.yield_parameter_combinations()):
            str_blocks = [
                c[1] + "_" + float_filename_fomratter(c[2]) for c in combination
            ]
            foldername = "case_" + "_".join(str_blocks)
            folder_path = os.path.join(main_folder, "scan", foldername)
            os.makedirs(folder_path, exist_ok=True)
            clone_folder_content(
                os.path.join(main_folder, "original_folder"), folder_path
            )

            # open the parameter file and update the parameters
            parameter_file = os.path.join(folder_path, self.config_file)
            with open(parameter_file, "r", encoding="utf-8") as f:
                parameters = yaml.safe_load(f)

            for c in combination:
                update_nested_dict(parameters, c[0], c[2])

            parameters["simulation_status"] = "not_started"
            simulation_info["sim_not_started"].append(foldername)
            # save the parameter file
            with open(parameter_file, "w", encoding="utf-8") as f:
                yaml.dump(parameters, f)

            # save the combination info
            simulation_combos[foldername] = combination

        # save the master parameters file
        simulation_info_file = os.path.join(main_folder, "simulation_info.yaml")
        with open(simulation_info_file, "w", encoding="utf-8") as f:
            yaml.dump(simulation_info, f)

        simulation_study_file = os.path.join(main_folder, "simulation_study.yaml")
        with open(simulation_study_file, "w", encoding="utf-8") as f:
            yaml.dump(asdict(self), f)

        # save the combinations info
        simulation_combos_file = os.path.join(main_folder, "simulation_combos.pkl")
        with open(simulation_combos_file, "wb") as f:
            pickle.dump(simulation_combos, f)

        self.folders_created = True

    def set_sim_status(self, sim_name, status):
        """Sets the simulation status in the simulation info file inside its folder.

        Parameters
        ----------
        sim_name : str
            The name of the simulation.
        status : str
            The status to set. Must be one of the following: 'not_started',
            'running', 'finished', 'interrupted', 'error'.
        """
        # load the simulation info
        simulation_info_file = os.path.join(
            self.study_path, self.study_name, "simulation_info.yaml"
        )
        with open(simulation_info_file, "r", encoding="utf-8") as f:
            simulation_info = yaml.safe_load(f)

        # update the simulation status
        # check if the simulation is in one of the lists
        if (
            sim_name
            not in simulation_info["sim_not_started"]
            + simulation_info["sim_running"]
            + simulation_info["sim_finished"]
            + simulation_info["sim_interrupted"]
            + simulation_info["sim_error"]
        ):
            raise ValueError(
                f"Simulation {sim_name} not found in simulation info file."
            )

        # update the simulation status in its folder
        folder_path = os.path.join(self.study_path, self.study_name, "scan", sim_name)
        parameter_file = os.path.join(folder_path, self.config_file)
        with open(parameter_file, "r", encoding="utf-8") as f:
            parameters = yaml.safe_load(f)

        parameters["simulation_status"] = status

        with open(parameter_file, "w", encoding="utf-8") as f:
            yaml.dump(parameters, f)

    def print_sim_status(self, update_remote_status=True):
        """Prints the simulation status. If update_remote_status is True, also
        checks if the simulations running remotely are finished by checking the
        existence of the file 'remote_finished' in the simulation folders and
        updates the simulation status accordingly.

        Parameters
        ----------
        update_remote_status : bool, optional
            If True, also checks if the simulations running remotely are
            finished by checking the existence of the file 'remote_finished' in
            the simulation folders and updates the simulation status
            accordingly. The default is True.
        """
        # load the simulation info
        simulation_info_file = os.path.join(
            self.study_path, self.study_name, "simulation_info.yaml"
        )
        with open(simulation_info_file, "r", encoding="utf-8") as f:
            simulation_info = yaml.safe_load(f)

        if update_remote_status:
            sim_to_check = (
                simulation_info["sim_not_started"] + simulation_info["sim_running"]
            )
            for sim in sim_to_check:
                folder_path = os.path.join(
                    self.study_path, self.study_name, "scan", sim
                )
                if os.path.exists(os.path.join(folder_path, "remote_finished")):
                    try:
                        simulation_info["sim_running"].remove(sim)
                        print(f"Removed {sim} from sim_running")
                    except ValueError:
                        pass
                    try:
                        simulation_info["sim_not_started"].remove(sim)
                        print(f"Removed {sim} from sim_running")
                    except ValueError:
                        pass
                    simulation_info["sim_finished"].append(sim)
                    self.set_sim_status(sim, "finished")
                    print(f"Simulation {sim} finished remotely.")

        print("------------------------------------------------------------")
        print("Simulation status:")
        print("------------------------------------------------------------")
        print(
            f"Number of simulations not started: {len(simulation_info['sim_not_started'])}"
        )
        print(f"Number of simulations running: {len(simulation_info['sim_running'])}")
        print(f"Number of simulations finished: {len(simulation_info['sim_finished'])}")
        print(
            f"Number of simulations interrupted: {len(simulation_info['sim_interrupted'])}"
        )
        print(f"Number of simulations with error: {len(simulation_info['sim_error'])}")
        print("------------------------------------------------------------")
        print("Simulations not started:")
        print("------------------------------------------------------------")
        for sim in simulation_info["sim_not_started"]:
            print(sim)
        print("------------------------------------------------------------")
        print("Simulations running:")
        print("------------------------------------------------------------")
        for sim in simulation_info["sim_running"]:
            print(sim)
        print("------------------------------------------------------------")
        print("Simulations finished:")
        print("------------------------------------------------------------")
        for sim in simulation_info["sim_finished"]:
            print(sim)
        print("------------------------------------------------------------")
        print("Simulations interrupted:")
        print("------------------------------------------------------------")
        for sim in simulation_info["sim_interrupted"]:
            print(sim)
        print("------------------------------------------------------------")
        print("Simulations with error:")
        print("------------------------------------------------------------")
        for sim in simulation_info["sim_error"]:
            print(sim)
        print("------------------------------------------------------------")

    def reset_simulations(self, reset_all=False, restore_original=False):
        """Reset the simulation folders to the initial state.

        Parameters
        ----------
        reset_all : bool
            If True, resets all the simulations. If False, resets only the
            simulations that are not finished.
        restore_original : bool
            If True, restores the original folder content. If False, leaves the
            current folder content and only resets the simulation status.
        """
        main_folder = os.path.join(self.study_path, self.study_name)
        simulation_info_file = os.path.join(main_folder, "simulation_info.yaml")
        simulation_combos_file = os.path.join(main_folder, "simulation_combos.pkl")

        with open(simulation_info_file, "r", encoding="utf-8") as f:
            simulation_info = yaml.safe_load(f)

        with open(simulation_combos_file, "rb") as f:
            simulation_combos = pickle.load(f)

        sim_to_reset = []
        if reset_all:
            sim_to_reset = (
                simulation_info["sim_not_started"]
                + simulation_info["sim_running"]
                + simulation_info["sim_finished"]
                + simulation_info["sim_error"]
            )
        else:
            sim_to_reset = (
                simulation_info["sim_not_started"]
                + simulation_info["sim_running"]
                + simulation_info["sim_error"]
            )

        for sim in sim_to_reset:
            folder_path = os.path.join(main_folder, "scan", sim)
            if restore_original:
                shutil.rmtree(folder_path)
                clone_folder_content(
                    os.path.join(main_folder, "original_folder"), folder_path
                )
                # open the parameter file and update the parameters
                parameter_file = os.path.join(folder_path, self.config_file)
                with open(parameter_file, "r", encoding="utf-8") as f:
                    parameters = yaml.safe_load(f)

                for c in simulation_combos[sim]:
                    update_nested_dict(parameters, c[0], c[2])

                parameters["simulation_status"] = "not_started"

                # save the parameter file
                with open(parameter_file, "w", encoding="utf-8") as f:
                    yaml.dump(parameters, f)
            else:
                self.set_sim_status(sim, "not_started")
                # if the simulation folder has the file 'remote_finished', remove it
                if os.path.exists(os.path.join(folder_path, "remote_finished")):
                    os.remove(os.path.join(folder_path, "remote_finished"))

            # update the simulation status
            simulation_info["sim_not_started"].append(sim)
            try:
                simulation_info["sim_running"].remove(sim)
                print(f"Removed {sim} from sim_running")
            except ValueError:
                pass
            try:
                simulation_info["sim_finished"].remove(sim)
                print(f"Removed {sim} from sim_finished")
            except ValueError:
                pass
            try:
                simulation_info["sim_error"].remove(sim)
                print(f"Removed {sim} from sim_error")
            except ValueError:
                pass

        # save the simulation info
        with open(simulation_info_file, "w", encoding="utf-8") as f:
            yaml.dump(simulation_info, f)


INITIAL_INSTRUCTIONS_LOCAL_DEFAULT = """
#!/bin/bash
# initial instructions
SIMPATH=$(pwd)
#___END_INITIAL_INSTRUCTIONS___
"""

FINAL_INSTRUCTIONS_LOCAL_DEFAULT = """
#___BEGIN_FINAL_INSTRUCTIONS___
# final instructions
OUTPUT_DIR=$SIMPATH
"""


def execute_command_on_gpu(
    command,
    folder_path,
    stdout_file,
    stderr_file,
    gpu_id,
    simulation_info,
    lock,
    simulation_study: SimulationStudy,
):
    """Executes a command on a GPU.

    Parameters
    ----------
    command : list
        The command to execute.
    folder_path : str
        The path to the folder where the command will be executed.
    stdout_file : file
        The file where the stdout will be redirected.
    stderr_file : file
        The file where the stderr will be redirected.
    gpu_id : int
        The ID of the GPU to use.
    simulation_info : dict
        The dictionary containing the simulation info. Composed of manager.list
        objects, so it can be shared between processes.
    lock : multiprocessing.Lock
        The lock to use when updating the simulation info.
    simulation_study : SimulationStudy
        The simulation study.
    """
    # Set the CUDA_VISIBLE_DEVICES environment variable to the GPU ID
    env = {"CUDA_VISIBLE_DEVICES": str(gpu_id)}

    # Update the simulation status
    with lock:
        simulation_info["sim_not_started"].remove(folder_path)
        simulation_info["sim_running"].append(folder_path)
        simulation_study.set_sim_status(folder_path, "running")

    # Execute the command using subprocess
    try:
        print(f"Running simulation in folder {folder_path} on GPU {gpu_id}...")
        process = subprocess.Popen(
            command,
            stdout=stdout_file,
            stderr=stderr_file,
            env=env,
            cwd=folder_path,
        )
        process.wait()
    except KeyboardInterrupt:
        print(
            f"KeyboardInterrupt detected, stopping simulation in folder {folder_path} on GPU {gpu_id}..."
        )
        # Update the simulation status
        with lock:
            simulation_info["sim_running"].remove(folder_path)
            simulation_info["sim_interrupted"].append(folder_path)
            simulation_study.set_sim_status(folder_path, "interrupted")
        if process.poll() is None:
            process.terminate()
    else:
        if process.returncode != 0:
            print(
                f"Error running simulation in folder {folder_path} on GPU {gpu_id}..."
            )
            # Update the simulation status
            with lock:
                simulation_info["sim_running"].remove(folder_path)
                simulation_info["sim_error"].append(folder_path)
                simulation_study.set_sim_status(folder_path, "error")
        else:
            print(
                f"Finished running simulation in folder {folder_path} on GPU {gpu_id}..."
            )
            # Update the simulation status once the simulation is finished
            with lock:
                simulation_info["sim_running"].remove(folder_path)
                simulation_info["sim_finished"].append(folder_path)
                simulation_study.set_sim_status(folder_path, "finished")


def job_run_local(simulation_study: SimulationStudy, **kwargs):
    """Runs the simulation study locally.

    Parameters
    ----------
    simulation_study : SimulationStudy
        The simulation study to run.
    kwargs
        Keyword arguments.

    Keyword Arguments
    -----------------
    initial_instructions : str
        The initial instructions to add to the main file.
    final_instructions : str
        The final instructions to add to the main file.
    stdout_path : str
        The path to the folder where the stdout files will be saved.
    stderr_path : str
        The path to the folder where the stderr files will be saved.
    log_path : str
        The path to the folder where the log files will be saved.
    gpu_available_list : list
        The list of available GPUs.

    Raises
    ------
    ValueError
        If the simulation study folders are not created.
    """
    initial_instructions = kwargs.get(
        "initial_instructions", INITIAL_INSTRUCTIONS_LOCAL_DEFAULT
    )
    final_instructions = kwargs.get(
        "final_instructions", FINAL_INSTRUCTIONS_LOCAL_DEFAULT
    )
    stdout_path = kwargs.get(
        "stdout_path", os.path.join(simulation_study.study_path, "out")
    )
    stderr_path = kwargs.get(
        "stderr_path", os.path.join(simulation_study.study_path, "err")
    )
    log_path = kwargs.get("log_path", os.path.join(simulation_study.study_path, "log"))

    gpu_available_list = kwargs.get("gpu_available_list", [])

    # load the simulation info
    simulation_info_file = os.path.join(
        simulation_study.study_path, simulation_study.study_name, "simulation_info.yaml"
    )
    with open(simulation_info_file, "r", encoding="utf-8") as f:
        simulation_info = yaml.safe_load(f)

    # get the list of simulations to run
    simulations_to_run = simulation_info["sim_not_started"]
    # get the root folder
    root_folder = simulation_info["root_folder"]

    # update the simulations' main file with run_local instructions
    stdout_file_list = []
    stderr_file_list = []

    for i, sim in enumerate(simulations_to_run):
        folder_path = os.path.join(root_folder, "scan", sim)
        main_file = os.path.join(folder_path, simulation_study.main_file)

        with open(main_file, "r", encoding="utf-8") as f:
            main_file_content = f.read()

        main_file_content = (
            initial_instructions + "\n" + main_file_content + "\n" + final_instructions
        )

        with open(main_file, "w", encoding="utf-8") as f:
            f.write(main_file_content)

        stdout_file_list.append(
            open(os.path.join(stdout_path, sim + ".out"), "w", encoding="utf-8")
        )
        stderr_file_list.append(
            open(os.path.join(stderr_path, sim + ".err"), "w", encoding="utf-8")
        )

    # run the simulations in parallel
    n_gpu_available = len(gpu_available_list)

    if n_gpu_available == 0:
        subprocess_list = []
        for i, sim in enumerate(simulations_to_run):
            folder_path = os.path.join(root_folder, "scan", sim)
            main_file = os.path.join(folder_path, simulation_study.main_file)

            subprocess_list.append(
                subprocess.Popen(
                    ["bash", main_file],
                    stdout=stdout_file_list[i],
                    stderr=stderr_file_list[i],
                    cwd=folder_path,
                )
            )

            # update the simulation status
            simulation_info["sim_not_started"].remove(sim)
            simulation_info["sim_running"].append(sim)
            simulation_study.set_sim_status(sim, "running")

            # save the simulation info
            with open(simulation_info_file, "w", encoding="utf-8") as f:
                yaml.dump(simulation_info, f)

        # wait for all the simulations to finish but while also checking if a
        # KeyboardInterrupt occurred, if it did, stop the simulations still
        # running and update the simulation info accordingly
        try:
            starting_time = datetime.now()
            print("Running simulations...")
            print(f"Started running at {starting_time}...")
            for i, sim in enumerate(simulations_to_run):
                subprocess_list[i].wait()
        except KeyboardInterrupt:
            print("KeyboardInterrupt detected, stopping simulations...")
            for i, sim in enumerate(simulations_to_run):
                # check if the simulation is still running
                # if not, update simulation_info accordingly
                if subprocess_list[i].poll() is not None:
                    # check the return code
                    if subprocess_list[i].returncode == 0:
                        simulation_info["sim_finished"].append(sim)
                        simulation_study.set_sim_status(sim, "finished")
                    else:
                        simulation_info["sim_error"].append(sim)
                        simulation_study.set_sim_status(sim, "error")
                    simulation_info["sim_running"].remove(sim)
                else:
                    # if still running, kill the process
                    subprocess_list[i].kill()
                    simulation_info["sim_interrupted"].append(sim)
                    simulation_info["sim_running"].remove(sim)
                    simulation_study.set_sim_status(sim, "interrupted")
        else:
            finishing_time = datetime.now()
            print("Finished running simulations...")
            print(f"Finished running at {finishing_time}...")
            print(f"Total running time: {finishing_time - starting_time}...")

            # update the simulation status
            for i, sim in enumerate(simulations_to_run):
                # check the return code
                if subprocess_list[i].returncode == 0:
                    simulation_info["sim_finished"].append(sim)
                    simulation_study.set_sim_status(sim, "finished")
                else:
                    simulation_info["sim_error"].append(sim)
                    simulation_study.set_sim_status(sim, "error")
                simulation_info["sim_running"].remove(sim)
        finally:
            # save the simulation info
            with open(simulation_info_file, "w", encoding="utf-8") as f:
                yaml.dump(simulation_info, f)

            # close the files
            for f in stdout_file_list:
                f.close()
            for f in stderr_file_list:
                f.close()
    else:
        # In this case, we first separate the simulations to run in groups
        # equal to the number of available GPUs, and then we run each group
        # in parallel using the GPUs available on separate pools of one worker.
        # This way, we can run multiple simulations in parallel, but each
        # simulation will use only one GPU. With no risk of running two or more
        # simulations on the same GPU.

        manager = Manager()
        shared_sim_status = {
            "sim_not_started": manager.list(simulation_info["sim_not_started"]),
            "sim_finished": manager.list(simulation_info["sim_finished"]),
            "sim_interrupted": manager.list(simulation_info["sim_interrupted"]),
            "sim_error": manager.list(simulation_info["sim_error"]),
            "sim_running": manager.list(simulation_info["sim_running"]),
        }
        lock = manager.Lock()

        argument_dict = {i: [] for i in gpu_available_list}

        for i, sim in enumerate(simulations_to_run):
            gpu_idx = i % n_gpu_available
            argument_dict[gpu_idx].append(
                (
                    [
                        "bash",
                        os.path.join(
                            root_folder, "scan", sim, simulation_study.main_file
                        ),
                    ],
                    os.path.join(root_folder, "scan", sim),
                    stdout_file_list[i],
                    stderr_file_list[i],
                    gpu_available_list[gpu_idx],
                    shared_sim_status,
                    lock,
                    simulation_study,
                )
            )

        try:
            # create the pools
            starting_time = datetime.now()
            print("Running simulations...")
            print(f"Started running at {starting_time}...")
            pool_list = []
            for key in argument_dict.keys():
                pool_list.append(Pool(1))
                pool_list[-1].map(
                    lambda args: execute_command_on_gpu(*args), argument_dict[key]
                )
        except KeyboardInterrupt:
            stopping_time = datetime.now()
            print("KeyboardInterrupt detected, stopping simulations...")
            print(f"Stopped running at {stopping_time}...")
            for pool in pool_list:
                pool.terminate()
                pool.join()
        else:
            stopping_time = datetime.now()
            print("Finished running simulations...")
            print(f"Finished running at {stopping_time}...")
            # close the pools
            for pool in pool_list:
                pool.close()
                pool.join()
        finally:
            print(f"Total running time: {stopping_time - starting_time}...")
            print("Updating simulation info...")
            # update the simulation status from the shared dictionary
            simulation_info["sim_not_started"] = list(
                shared_sim_status["sim_not_started"]
            )
            simulation_info["sim_finished"] = list(shared_sim_status["sim_finished"])
            simulation_info["sim_interrupted"] = list(
                shared_sim_status["sim_interrupted"]
            )
            simulation_info["sim_error"] = list(shared_sim_status["sim_error"])
            simulation_info["sim_running"] = list(shared_sim_status["sim_running"])
            # save the simulation info
            with open(simulation_info_file, "w", encoding="utf-8") as f:
                yaml.dump(simulation_info, f)

            # close the files
            for f in stdout_file_list:
                f.close()
            for f in stderr_file_list:
                f.close()


INITIAL_INSTRUCTIONS_HTCONDOR_DEFAULT = """
#!/bin/bash
# initial instructions

export EOS_MGM_URL=root://eosuser.cern.ch

source __REPLACE_WITH_CVMFS_PATH__
source __REPLACE_WITH_VENV_PATH__

SIMPATH=$1

mkdir ./output
OUTPUT_DIR="./output"
#___END_INITIAL_INSTRUCTIONS___
"""

FINAL_INSTRUCTIONS_HTCONDOR_DEFAULT = """
#___BEGIN_FINAL_INSTRUCTIONS___
# final instructions
EOS_DIR=__REPLACE_WITH_EOS_DIR__

# grab list of *.h5 files
h5_files=$(ls $OUTPUT_DIR/*.h5)
# copy them to EOS
for f in $h5_files
do
    echo "Copying $f to EOS"
    eos cp $f $EOS_DIR
done
# create a symbolic link of the various files in the output folder
for f in $h5_files
do
    echo "Creating symbolic link for $f"
    ln -s $f $OUTPUT_DIR/$(basename $f)
done

# grab list of *.pkl files
pkl_files=$(ls $OUTPUT_DIR/*.pkl)
# copy them to EOS
for f in $pkl_files
do
    echo "Copying $f to EOS"
    eos cp $f $EOS_DIR
done
# create a symbolic link of the various files in the output folder
for f in $pkl_files
do
    echo "Creating symbolic link for $f"
    ln -s $f $OUTPUT_DIR/$(basename $f)
done

# create a marker file to signal that the simulation is finished in SIMPATH
touch $SIMPATH/remote_finished

"""

HTCONDOR_SUBMIT_FILE_DEFAULT_CPU = """
universe   = vanilla

executable = $(Executable)
arguments  = $(Simpath)

output     = $(Outpath)
error      = $(Errpath)
log        = __REPLACE_WITH_LOG_PATH__

transfer_output_files = ""

requirements = (TARGET.OpSysAndVer =?= "AlmaLinux9" || TARGET.OpSysAndVer =?= "CentOS7")

request_cpus = __REPLACE_WITH_REQUEST_CPUS__

+JobFlavour = "__REPLACE_WITH_TIME_LIMIT__"

+AccountingGroup = "group_u_BE.ABP.normal"

queue Executable,Simpath,Outpath,Errpath from __REPLACE_WITH_QUEUE_FILE__
"""

HTCONDOR_SUBMIT_FILE_DEFAULT_GPU = """
universe   = vanilla

executable = $(Executable)
arguments  = $(Simpath)

output     = $(Outpath)
error      = $(Errpath)
log        = __REPLACE_WITH_LOG_PATH__

transfer_output_files = ""

requirements = (regexp("(V100|A100)", Target.CUDADeviceName) && ( TARGET.OpSysAndVer =?= "AlmaLinux9" || TARGET.OpSysAndVer =?= "CentOS7"))

request_GPUs = __REPLACE_WITH_REQUEST_GPUS__
request_cpus = __REPLACE_WITH_REQUEST_CPUS__

+JobFlavour = "__REPLACE_WITH_TIME_LIMIT__"

+AccountingGroup = "group_u_BE.ABP.normal"

queue Executable,Simpath,Outpath,Errpath from __REPLACE_WITH_QUEUE_FILE__
"""


def job_run_htcondor(simulation_study: SimulationStudy, **kwargs):
    """Runs the simulation study on HTCondor. Takes in consideration the weird
    way the CERN shared filesystem works.

    Parameters
    ----------
    simulation_study : SimulationStudy
        The simulation study to run.
    kwargs
        Keyword arguments.

    Keyword Arguments
    -----------------
    initial_instructions : str
        The initial instructions to add to the main file.
    final_instructions : str
        The final instructions to add to the main file.
    stdout_path : str
        The path to the folder where the stdout files will be saved.
    stderr_path : str
        The path to the folder where the stderr files will be saved.
    log_path : str
        The path to the folder where the log files will be saved.
    htcondor_submit_template : str
        The template for the HTCondor submit file.
    request_gpus : bool
        If True, requests GPUs. By default, does not request GPUs.
    request_cpus : int
        The number of CPUs to request. By default, requests 1 CPU.
    time_limit : str
        The time limit for the simulations. Following the HTCondor format, that is
        * "espresso" for 20 minutes
        * "microcentury" for 1 hour
        * "longlunch" for 2 hours
        * "workday" for 8 hours
        * "tomorrow" for 1 day
        * "testmatch" for 3 days
        * "nextweek" for 1 week
    cvmfs_path : str
        The path to the CVMFS environment to use.
    venv_path : str
        The path to the virtual environment to use.
    eos_dir : str
        The path to the EOS directory where to copy the output files.
    bump_schedd : bool
        If True, bumps the schedd before submitting the jobs.

    Raises
    ------
    ValueError
        If the simulation study folders are not created.
    """
    initial_instructions = kwargs.get(
        "initial_instructions", INITIAL_INSTRUCTIONS_HTCONDOR_DEFAULT
    )
    final_instructions = kwargs.get(
        "final_instructions", FINAL_INSTRUCTIONS_HTCONDOR_DEFAULT
    )
    stdout_path = kwargs.get(
        "stdout_path", os.path.join(simulation_study.study_path, "out")
    )
    stderr_path = kwargs.get(
        "stderr_path", os.path.join(simulation_study.study_path, "err")
    )
    log_path = kwargs.get("log_path", os.path.join(simulation_study.study_path, "log"))
    request_gpus = kwargs.get("request_gpus", False)
    request_cpus = kwargs.get("request_cpus", 1)
    time_limit = kwargs.get("time_limit", "longlunch")
    bump_schedd = kwargs.get("bump_schedd", True)

    htcondor_submit_str = kwargs.get(
        "htcondor_submit_template",
        HTCONDOR_SUBMIT_FILE_DEFAULT_CPU
        if not request_gpus
        else HTCONDOR_SUBMIT_FILE_DEFAULT_GPU,
    )

    cvmfs_path = kwargs.get(
        "cvmfs_path",
        "/cvmfs/sft.cern.ch/lcg/views/LCG_102b_cuda/x86_64-centos7-gcc8-opt/setup.sh",
    )
    # if no venv path is provided, just reload the cvmfs environment
    venv_path = kwargs.get("venv_path", cvmfs_path)
    eos_dir = kwargs.get("eos_dir", "/eos/user/c/camontan/data")

    # create the folder "htcondor_support" in the study folder
    htcondor_support_folder = os.path.join(
        simulation_study.study_path, simulation_study.study_name, "htcondor_support"
    )
    os.makedirs(htcondor_support_folder, exist_ok=True)

    # specializations of the submit file
    htcondor_submit_str = htcondor_submit_str.replace(
        "__REPLACE_WITH_REQUEST_CPUS__", str(request_cpus)
    )
    htcondor_submit_str = htcondor_submit_str.replace(
        "__REPLACE_WITH_TIME_LIMIT__", time_limit
    )
    htcondor_submit_str = htcondor_submit_str.replace(
        "__REPLACE_WITH_QUEUE_FILE__",
        os.path.join(htcondor_support_folder, "queue.txt"),
    )
    if request_gpus:
        htcondor_submit_str = htcondor_submit_str.replace(
            "__REPLACE_WITH_REQUEST_GPUS__", "1"
        )
    # log name has the format htcondor_yyyy_mm_dd_hh_mm_ss.log
    log_name = "htcondor_" + datetime.now().strftime("%Y_%m_%d_%H_%M_%S") + ".log"
    htcondor_submit_str = htcondor_submit_str.replace(
        "__REPLACE_WITH_LOG_PATH__", os.path.join(log_path, log_name)
    )

    # save the submit file
    htcondor_submit_file = os.path.join(
        htcondor_support_folder, "htcondor_submit_file.sub"
    )
    with open(htcondor_submit_file, "w", encoding="utf-8") as f:
        f.write(htcondor_submit_str)

    # load the simulation info
    simulation_info_file = os.path.join(
        simulation_study.study_path, simulation_study.study_name, "simulation_info.yaml"
    )
    with open(simulation_info_file, "r", encoding="utf-8") as f:
        simulation_info = yaml.safe_load(f)

    # get the list of simulations to run
    simulations_to_run = simulation_info["sim_not_started"]
    # get the root folder
    root_folder = simulation_info["root_folder"]

    # specialize the initial and final instructions
    initial_instructions = initial_instructions.replace(
        "__REPLACE_WITH_CVMFS_PATH__", cvmfs_path
    )
    initial_instructions = initial_instructions.replace(
        "__REPLACE_WITH_VENV_PATH__", venv_path
    )
    final_instructions = final_instructions.replace("__REPLACE_WITH_EOS_DIR__", eos_dir)

    queue_file_content = ""
    for i, sim in enumerate(simulations_to_run):
        folder_path = os.path.join(root_folder, "scan", sim)
        main_file = os.path.join(folder_path, simulation_study.main_file)

        with open(main_file, "r", encoding="utf-8") as f:
            main_file_content = f.read()

        main_file_content = (
            initial_instructions + "\n" + main_file_content + "\n" + final_instructions
        )

        with open(main_file, "w", encoding="utf-8") as f:
            f.write(main_file_content)

        # fill the queue file line
        queue_file_content += f"{main_file}, {folder_path}, {os.path.join(stdout_path, sim + '.out')}, {os.path.join(stderr_path, sim + '.err')}\n"

        print(f"Added {sim} to the queue file")

    print("Total number of jobs:", len(simulations_to_run))

    # save the queue file
    queue_file = os.path.join(htcondor_support_folder, "queue.txt")
    with open(queue_file, "w", encoding="utf-8") as f:
        f.write(queue_file_content)

    if bump_schedd:
        # bump the schedd
        print("Bumping the schedd...")
        try:
            subprocess.run(["myschedd", "bump"], check=True)
        except subprocess.CalledProcessError:
            print("Error bumping the schedd, continuing anyway...")
            print("Good luck!")

    # submit the jobs while staying in the htcondor_support folder
    print("Submitting the jobs...")
    print("----------------------------------------")
    print("May the gods above and below be with you and have mercy")
    print("on your soul and your jobs!")
    print("----------------------------------------")
    try:
        subprocess.run(
            ["condor_submit", htcondor_submit_file],
            cwd=htcondor_support_folder,
            check=True,
        )
    except subprocess.CalledProcessError:
        print("Error submitting the jobs, exiting...")
        print("----------------------------------------")
        print("Impressive! Most impressive!")
        print("It looks like the gods hate you so much that the jobs")
        print("were not even submitted!")
        print("----------------------------------------")
        return

    now = datetime.now()
    print("Jobs submitted at", now)
    print("----------------------------------------")
    print("Good luck!")
    print("----------------------------------------")
    print("Remember to check the status of your jobs")
    print("by running the internal function print_sim_status")
    print("----------------------------------------")


INSTRUCTIONS_SLURM_DEFAULT = """
#!/bin/bash

#SBATCH --job-name=__REPLACE_WITH_JOB_NAME__
#SBATCH --output=$3
#SBATCH --error=$4
#SBATCH --time=__REPLACE_WITH_TIME_LIMIT__
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=__REPLACE_WITH_REQUEST_CPUS__
#SBATCH --mem=__REPLACE_WITH_REQUEST_MEM__
#SBATCH --gres=__REPLACE_WITH_REQUEST_GPUS__
#SBATCH --partition=__REPLACE_WITH_PARTITION__

# initial instructions
# set simpath
SIMPATH=$1
cd $SIMPATH

# load python environment
source __REPLACE_WITH_VENV_PATH__

bash $2

# final instructions

# create a marker file to signal that the simulation is finished in SIMPATH
touch $SIMPATH/remote_finished
"""

SUBMISSION_SLURM_DEFAULT = """
#!/bin/bash

SIMPATHS=__REPLACE_WITH_SIMPATHS__
OUTPATHS=__REPLACE_WITH_OUTPATHS__
ERRPATHS=__REPLACE_WITH_ERRPATHS__

# iterate over the zip of the three lists
for SIMPATH OUTPATH ERRPATH in $(paste -d' ' <(echo $SIMPATHS) <(echo $OUTPATHS) <(echo $ERRPATHS))
do
    # submit the job
    sbatch __REPLACE_WITH_SLURM_SUBMIT_FILE__ $SIMPATH $OUTPATH $ERRPATH
done

"""


def job_run_slurm(simulation_study: SimulationStudy, **kwargs):
    """Runs the simulation study on SLURM. Takes in consideration the weird
    way the CNAF shared filesystem works.

    Parameters
    ----------
    simulation_study : SimulationStudy
        The simulation study to run.
    kwargs
        Keyword arguments.

    Keyword Arguments
    -----------------
    slurm_instructions: str
        The instructions to add to the SLURM submit file.
    stdout_path : str
        The path to the folder where the stdout files will be saved.
    stderr_path : str
        The path to the folder where the stderr files will be saved.
    log_path : str
        The path to the folder where the log files will be saved.
    slurm_submit_template : str
        The template for the SLURM submit file.
    request_gpus : bool
        If True, requests GPUs. By default, does not request GPUs.
    request_cpus : int
        The number of CPUs to request. By default, requests 1 CPU.
    request_ram : int
        GB of RAM to be requested. By default, requests 2 GB * request_cpus.
    time_limit : str
        The time limit for the simulations. Following the SLURM format, that is
        hh:mm:ss, by default 2 hours.
    venv_path : str
        The path to the virtual environment to use.
    partition_option : str
        The partition to use. By default, no partition is specified.
    slurm_submit_template : str
        The template for the SLURM submit file.

    Raises
    ------
    ValueError
        If the simulation study folders are not created.
    """
    slurm_instructions = kwargs.get("slurm_instructions", INSTRUCTIONS_SLURM_DEFAULT)
    stdout_path = kwargs.get(
        "stdout_path", os.path.join(simulation_study.study_path, "out")
    )
    stderr_path = kwargs.get(
        "stderr_path", os.path.join(simulation_study.study_path, "err")
    )
    log_path = kwargs.get("log_path", os.path.join(simulation_study.study_path, "log"))
    request_gpus = kwargs.get("request_gpus", False)
    request_cpus = kwargs.get("request_cpus", 1)
    request_ram = kwargs.get("request_ram", 2 * request_cpus)
    time_limit = kwargs.get("time_limit", "02:00:00")
    venv_path = kwargs.get("venv_path", "/home/HPC/camontan/anaconda3/bin/python")
    partition_option = kwargs.get("partition_option", "")
    slurm_submit_template = kwargs.get(
        "slurm_submit_template", SUBMISSION_SLURM_DEFAULT
    )

    # create the folder "slurm_support" in the study folder
    slurm_support_folder = os.path.join(
        simulation_study.study_path, simulation_study.study_name, "slurm_support"
    )
    os.makedirs(slurm_support_folder, exist_ok=True)

    # specialization of the SLURM file
    slurm_instructions = slurm_instructions.replace(
        "__REPLACE_WITH_REQUEST_CPUS__", str(request_cpus)
    )
    slurm_instructions = slurm_instructions.replace(
        "__REPLACE_WITH_REQUEST_MEM__", str(request_ram) + "G"
    )
    slurm_instructions = slurm_instructions.replace(
        "__REPLACE_WITH_TIME_LIMIT__", time_limit
    )
    slurm_instructions = slurm_instructions.replace(
        "__REPLACE_WITH_VENV_PATH__", venv_path
    )
    slurm_instructions = slurm_instructions.replace(
        "__REPLACE_WITH_MAIN_FILE__", simulation_study.main_file
    )

    if request_gpus:
        slurm_instructions = slurm_instructions.replace(
            "__REPLACE_WITH_REQUEST_GPUS__", "gpu:1"
        )
    else:
        # remove the entire line where the gres is specified
        slurm_instructions = re.sub(
            r"#SBATCH --gres=__REPLACE_WITH_REQUEST_GPUS__\n", "", slurm_instructions
        )

    if partition_option != "":
        slurm_instructions = slurm_instructions.replace(
            "__REPLACE_WITH_PARTITION__", partition_option
        )
    else:
        # remove the entire line where the partition is specified
        slurm_instructions = re.sub(
            r"#SBATCH --partition=__REPLACE_WITH_PARTITION__\n", "", slurm_instructions
        )

    # save the SLURM file
    slurm_submit_file = os.path.join(
        slurm_support_folder,
        "slurm_submit_file.slurm",
    )
    with open(slurm_submit_file, "w", encoding="utf-8") as f:
        f.write(slurm_instructions)

    # load the simulation info
    simulation_info_file = os.path.join(
        simulation_study.study_path, simulation_study.study_name, "simulation_info.yaml"
    )
    with open(simulation_info_file, "r", encoding="utf-8") as f:
        simulation_info = yaml.safe_load(f)

    # get the list of simulations to run
    simulations_to_run = simulation_info["sim_not_started"]
    # get the root folder
    root_folder = simulation_info["root_folder"]

    queue_simpath_list = []
    queue_outpath_list = []
    queue_errpath_list = []
    for i, sim in enumerate(simulations_to_run):
        folder_path = os.path.join(root_folder, "scan", sim)

        queue_simpath_list.append(folder_path)
        queue_outpath_list.append(os.path.join(stdout_path, sim + ".out"))
        queue_errpath_list.append(os.path.join(stderr_path, sim + ".err"))

        print(f"Added {sim} to the queue file")

    print("Total number of jobs:", len(simulations_to_run))

    # specialize the submission file
    slurm_submit_template = slurm_submit_template.replace(
        "__REPLACE_WITH_SIMPATHS__", '"' + " ".join(queue_simpath_list) + '"'
    )
    slurm_submit_template = slurm_submit_template.replace(
        "__REPLACE_WITH_OUTPATHS__", '"' + " ".join(queue_outpath_list) + '"'
    )
    slurm_submit_template = slurm_submit_template.replace(
        "__REPLACE_WITH_ERRPATHS__", '"' + " ".join(queue_errpath_list) + '"'
    )

    slurm_submit_template = slurm_submit_template.replace(
        "__REPLACE_WITH_SLURM_SUBMIT_FILE__", slurm_submit_file
    )

    # save the submission file
    submission_file = os.path.join(
        slurm_support_folder,
        "submission_file.sh",
    )
    with open(submission_file, "w", encoding="utf-8") as f:
        f.write(slurm_submit_template)

    # submit the jobs while staying in the slurm_support folder
    print("Submitting the jobs...")
    print("----------------------------------------")
    print("May the gods above and below be with you and have mercy")
    print("on your soul and your jobs!")
    print("----------------------------------------")
    try:
        subprocess.run(
            ["bash", submission_file],
            cwd=slurm_support_folder,
            check=True,
        )
    except subprocess.CalledProcessError:
        print("Error submitting the jobs, exiting...")
        print("----------------------------------------")
        print("Impressive! Most impressive!")
        print("It looks like the gods hate you so much that the jobs")
        print("were not even submitted!")
        print("----------------------------------------")
        return

    now = datetime.now()
    print("Jobs submitted at", now)
    print("----------------------------------------")
    print("Good luck!")
    print("----------------------------------------")
    print("Remember to check the status of your jobs")
    print("by running the internal function print_sim_status")
    print("----------------------------------------")
