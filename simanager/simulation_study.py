import os
import pickle
import shutil
from dataclasses import asdict, dataclass, field
from itertools import product
import pandas as pd

import numpy as np
import yaml

from .parameter_inspection import ParameterInspection
from .tools import (
    clone_folder_content,
    number_filename_formatter,
    float_representer,
    int_representer,
    numpy_scalar_representer,
    update_nested_dict,
    flatten_dict,
    insert_nested_dict_in_dataframe,
)


@dataclass
class SimulationStudy:
    """Class that contains the information about a simulation study.

    Parameters
    ----------
    study_name : str
        The name of the study.
    study_path : str, optional
        The path to the study folder. If it is set at "./", the study folder
        will be created in the current working directory. Note that this value
        can be retrieved by using the environment variable $STUDYPATH. Use it
        to make the parameter file more portable!
    original_folder : str
        The path to the folder containing the original files to clone.
    main_file : str
        The name of the main file to execute. Must be a bash file.
    config_file : str
        The name of the file containing the parameters to update. Must be a yaml.
    parameters_inspected : list, optional
        The list of parameters to inspect. The default is None. Must be a list of
        ParameterInspection objects.
    environ_dict : dict, optional
        Dictionary containing the environment variables to set. The default is
        an empty dictionary. Use it to set "universal" environment variables
        that can help you manage the simulations on different machines.
    test_case : dict, optional
        Dictionary containing the parameters for a quick simulation case to be
        run for a quick test run, in order to check the correct behaviour of the
        master study. By default, a test with the first combination of
        parameters is generated.
    """

    study_name: str
    study_path: str
    original_folder: str
    main_file: str
    config_file: str
    parameters_inspected: list[ParameterInspection]
    environ_dict: dict = field(default_factory=dict)
    test_case: dict = field(default_factory=dict)
    folders_created: bool = False

    def __post_init__(self):
        # if self.study_path == "./":
        self.study_path = os.path.abspath(self.study_path)

        # set $STUDYPATH environment variable to the study path
        os.environ["STUDYPATH"] = self.study_path

        # self.original_folder = os.path.abspath(self.original_folder)
        # unpack $STUDYPATH environment variable in the original folder
        self.original_folder = os.path.abspath(os.path.expandvars(self.original_folder))
        self.output_path = os.path.abspath(
            os.path.join(self.study_path, self.study_name, "output_files")
        )

        # construct from the list of parameters inspected the list of parameters
        # using the dataclass ParameterInspection
        if self.parameters_inspected is None:
            self.parameters_inspected = []
        else:
            self.parameters_inspected = [
                ParameterInspection.from_dict(p) for p in self.parameters_inspected
            ]

        # if environ_dict is not empty, set the environment variables
        if self.environ_dict:
            for k, v in self.environ_dict.items():
                os.environ[k] = v

        # Register the custom representers for numerical types
        yaml.add_representer(int, int_representer)
        yaml.add_representer(float, float_representer)
        yaml.add_representer(np.int64, numpy_scalar_representer)
        yaml.add_representer(np.float64, numpy_scalar_representer)

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
        simulation_study["study_path"] = folder_path
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
        for idx in np.where(p_idx == -1)[0]:
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
                # check if all values have the same length
                if not all(len(v) == len(values[0]) for v in values):
                    raise ValueError(
                        "All values must have the same length for individual combination."
                    )
                vv = list(zip(*values))
                id_equiv = list(zip(*[range(len(v)) for v in values]))

                joined_combinations.append(
                    (names, file_names, vv, len(vv), "multi", id_equiv)
                )
            elif combo_method == "meshgrid":
                vv = np.meshgrid(*values)
                vv = [v.flatten().tolist() for v in vv]
                id_equiv = np.meshgrid(*[range(len(v)) for v in values])
                id_equiv = [v.flatten().tolist() for v in id_equiv]
                vv = list(zip(*vv))
                id_equiv = list(zip(*id_equiv))
                joined_combinations.append(
                    (names, file_names, vv, len(vv), "multi", id_equiv)
                )
            elif combo_method == "product":
                vv = list(product(*values))
                id_equiv = list(product(*[range(len(v)) for v in values]))
                print(vv)
                print(id_equiv)
                joined_combinations.append(
                    (names, file_names, vv, len(vv), "multi", id_equiv)
                )

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

        for _ in range(total_combinations):
            # get the current combination
            current_combination = []
            for j, c in enumerate(combinations):
                if c[4] == "single":
                    current_combination.append(
                        (c[0], c[1], c[2][current_idx[j]], c[4], current_idx[j])
                    )
                elif c[4] == "multi":
                    for k, v in enumerate(c[1]):
                        current_combination.append(
                            (
                                c[0][k],
                                c[1][k],
                                c[2][current_idx[j]][k],
                                c[4],
                                c[5][current_idx[j]][k],
                            )
                        )
            # update the indices
            current_idx[0] += 1
            for i, (idx, max_val) in enumerate(zip(current_idx, n_values)):
                if idx == max_val:
                    current_idx[i] = 0
                    if i + 1 < len(current_idx):
                        current_idx[i + 1] += 1
                    else:
                        pass

            yield current_combination

    def initialize_folders(self):
        """Creates the folders for the study."""
        main_folder = os.path.join(self.study_path, self.study_name)
        os.makedirs(main_folder, exist_ok=True)
        os.makedirs(os.path.join(main_folder, "out"), exist_ok=True)
        os.makedirs(os.path.join(main_folder, "err"), exist_ok=True)
        os.makedirs(os.path.join(main_folder, "log"), exist_ok=True)

        os.makedirs(os.path.join(main_folder, "output_files"), exist_ok=True)
        os.makedirs(os.path.join(main_folder, "remote_touch_files"), exist_ok=True)
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
                c[1] + "_" + number_filename_formatter(c[2], c[4])
                for c in combination
                if c[1] is not None
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

            if i == 0:
                # create the test case folder
                folder_path = os.path.join(main_folder, "scan", "test")
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

                # extra specifications for test case
                for key, item in self.test_case.items():
                    update_nested_dict(parameters, key, item)

                # save the parameter file
                with open(parameter_file, "w", encoding="utf-8") as f:
                    yaml.dump(parameters, f)

                print("Test case folder created at: ", folder_path)

                # create the information DataFrame
                keys_for_df = list(flatten_dict(parameters).keys())
                # add extra columns for the folder name and output path
                keys_for_df += ["folder_name", "output_path"]
                dataframe_info = pd.DataFrame(columns=keys_for_df)
            
            # make the extra_dict with the folder name and output path
            extra_dict = {
                "folder_name": foldername,
                "output_path": os.path.join(self.output_path, foldername),
            }
            # add a row to the dataframe
            dataframe_info = insert_nested_dict_in_dataframe(
                dataframe_info, parameters, extra_dict
            )

        # count the final number of folders created
        n_folders = len(os.listdir(os.path.join(main_folder, "scan")))
        print(f"Number of folders created: {n_folders}")
        # print the number of folders that were expected
        print(f"Number of folders expected: {len(simulation_combos) + 1}")
        # if the number of folders created is different from the expected, raise a warning
        if n_folders != len(simulation_combos) + 1:
            print(
                "WARNING: The number of folders created is different from the expected."
            )

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
        
        # save the information DataFrame
        # if present, remove the column "simulation_status"
        if "simulation_status" in dataframe_info.columns:
            dataframe_info = dataframe_info.drop(columns=["simulation_status"])

        dataframe_info_file = os.path.join(main_folder, "simulation_info.csv")
        dataframe_info.to_csv(dataframe_info_file, index=False)
        dataframe_info.to_pickle(dataframe_info_file.replace(".csv", ".pkl"))

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

        # where is the simulation in the dictionary simulation_info?
        # find it and move the simulation in the new status
        if sim_name in simulation_info["sim_not_started"]:
            simulation_info["sim_not_started"].remove(sim_name)
            prev_loc = "not_started"
        elif sim_name in simulation_info["sim_running"]:
            simulation_info["sim_running"].remove(sim_name)
            prev_loc = "running"
        elif sim_name in simulation_info["sim_finished"]:
            simulation_info["sim_finished"].remove(sim_name)
            prev_loc = "finished"
        elif sim_name in simulation_info["sim_interrupted"]:
            simulation_info["sim_interrupted"].remove(sim_name)
            prev_loc = "interrupted"
        elif sim_name in simulation_info["sim_error"]:
            simulation_info["sim_error"].remove(sim_name)
            prev_loc = "error"
        else:
            raise ValueError(
                f"Simulation {sim_name} not found in simulation info file."
            )

        # move the simulation in the new status
        simulation_info[f"sim_{status}"].append(sim_name)
        if status != prev_loc:
            print(f"Moved {sim_name} from {prev_loc} to {status}")

        # update the simulation status in its folder
        folder_path = os.path.join(self.study_path, self.study_name, "scan", sim_name)
        parameter_file = os.path.join(folder_path, self.config_file)
        with open(parameter_file, "r", encoding="utf-8") as f:
            parameters = yaml.safe_load(f)

        parameters["simulation_status"] = status

        with open(parameter_file, "w", encoding="utf-8") as f:
            yaml.dump(parameters, f)

        # save the simulation info
        with open(simulation_info_file, "w", encoding="utf-8") as f:
            yaml.dump(simulation_info, f)

    def _update_remote_status(self):
        simulation_info_file = os.path.join(
            self.study_path, self.study_name, "simulation_info.yaml"
        )
        with open(simulation_info_file, "r", encoding="utf-8") as f:
            simulation_info = yaml.safe_load(f)

        sim_to_check = (
            simulation_info["sim_not_started"] + simulation_info["sim_running"]
        )
        folder_path = os.path.join(
            self.study_path, self.study_name, "remote_touch_files"
        )
        for sim in sim_to_check:
            if os.path.exists(os.path.join(folder_path, "FINISHED_" + sim)):
                self.set_sim_status(sim, "finished")
                print(f"REMOTE CHECK: Simulation {sim} finished remotely.")
            elif os.path.exists(os.path.join(folder_path, "ERROR_" + sim)):
                self.set_sim_status(sim, "error")
                print(f"REMOTE CHECK: Simulation {sim} failed remotely.")
            elif os.path.exists(os.path.join(folder_path, "IO_ERROR_" + sim)):
                self.set_sim_status(sim, "error")
                print(f"REMOTE CHECK: Simulation {sim} failed remotely due to a OUTPUT TRANSFER error!!!!")
            else:
                # self.set_sim_status(sim, "not_started")
                print(f"REMOTE CHECK: Simulation {sim} has either not started or is still running.")
                # print("Not updating status.")

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
        if update_remote_status:
            self._update_remote_status()

        # load the simulation info
        simulation_info_file = os.path.join(
            self.study_path, self.study_name, "simulation_info.yaml"
        )
        with open(simulation_info_file, "r", encoding="utf-8") as f:
            simulation_info = yaml.safe_load(f)

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

        if len(simulation_info["sim_not_started"]) > 0:
            print("------------------------------------------------------------")
            print("Simulations not started:")
            print("------------------------------------------------------------")
            for sim in sorted(simulation_info["sim_not_started"]):
                print(sim)

        if len(simulation_info["sim_running"]) > 0:
            print("------------------------------------------------------------")
            print("Simulations running:")
            print("------------------------------------------------------------")
            for sim in sorted(simulation_info["sim_running"]):
                print(sim)

        if len(simulation_info["sim_finished"]) > 0:
            print("------------------------------------------------------------")
            print("Simulations finished:")
            print("------------------------------------------------------------")
            for sim in sorted(simulation_info["sim_finished"]):
                print(sim)

        if len(simulation_info["sim_interrupted"]) > 0:
            print("------------------------------------------------------------")
            print("Simulations interrupted:")
            print("------------------------------------------------------------")
            for sim in sorted(simulation_info["sim_interrupted"]):
                print(sim)

        if len(simulation_info["sim_error"]) > 0:
            print("------------------------------------------------------------")
            print("Simulations with error:")
            print("------------------------------------------------------------")
            for sim in sorted(simulation_info["sim_error"]):
                print(sim)
        print("------------------------------------------------------------")

    def reset_simulations(
        self,
        reset_all=False,
        restore_original=False,
        clear_out_folder=False,
        clear_err_folder=False,
        clear_log_folder=False,
    ):
        """Reset the simulation folders to the initial state.

        Parameters
        ----------
        reset_all : bool
            If True, resets all the simulations. If False, resets only the
            simulations that are not finished.
        restore_original : bool
            If True, restores the original folder content. If False, leaves the
            current folder content and only resets the simulation status.
        clear_out_folder : bool
            If True, clears the out folder. The default is False.
        clear_err_folder : bool
            If True, clears the err folder. The default is False.
        clear_log_folder : bool
            If True, clears the log folder. The default is False.
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
                + simulation_info["sim_interrupted"]
            )

        for sim in sim_to_reset:
            print(f"Resetting {sim}")
            folder_path = os.path.join(main_folder, "scan", sim)
            if restore_original:
                # remove the content of the folder
                shutil.rmtree(folder_path)
                # create the folder
                os.makedirs(folder_path, exist_ok=True)
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
                self.set_sim_status(sim, "not_started")
            else:
                self.set_sim_status(sim, "not_started")
                # if the simulation folder has its file in remote_touch_files
                # remove it
                if os.path.exists(
                    os.path.join(main_folder, "remote_touch_files", "FINISHED_" + sim)
                ):
                    os.remove(
                        os.path.join(
                            main_folder, "remote_touch_files", "FINISHED_" + sim
                        )
                    )
                if os.path.exists(
                    os.path.join(main_folder, "remote_touch_files", "ERROR_" + sim)
                ):
                    os.remove(
                        os.path.join(main_folder, "remote_touch_files", "ERROR_" + sim)
                    )

        if clear_out_folder:
            out_folder = os.path.join(main_folder, "out")
            for f in os.listdir(out_folder):
                os.remove(os.path.join(out_folder, f))

        if clear_err_folder:
            err_folder = os.path.join(main_folder, "err")
            for f in os.listdir(err_folder):
                os.remove(os.path.join(err_folder, f))

        if clear_log_folder:
            log_folder = os.path.join(main_folder, "log")
            for f in os.listdir(log_folder):
                os.remove(os.path.join(log_folder, f))

    def nuke_simulation(self):
        """Removes the entire folder where the simulation is contained!!!"""
        print("SO LONG AND THANKS FOR ALL THE FISH!")
        main_folder = os.path.join(self.study_path, self.study_name)
        shutil.rmtree(main_folder)
        print("NUKING COMPLETE!")
        print("DO YOU FEEL LIKE OPPENHEIMER YET?")

    @property
    def finished(self):
        """Returns a list of the simulations that are finished."""
        simulation_info_file = os.path.join(
            self.study_path, self.study_name, "simulation_info.yaml"
        )
        with open(simulation_info_file, "r", encoding="utf-8") as f:
            simulation_info = yaml.safe_load(f)

        return simulation_info["sim_finished"]

    @property
    def not_started(self):
        """Returns a list of the simulations that are not started."""
        simulation_info_file = os.path.join(
            self.study_path, self.study_name, "simulation_info.yaml"
        )
        with open(simulation_info_file, "r", encoding="utf-8") as f:
            simulation_info = yaml.safe_load(f)

        return simulation_info["sim_not_started"]

    @property
    def running(self):
        """Returns a list of the simulations that are running."""
        simulation_info_file = os.path.join(
            self.study_path, self.study_name, "simulation_info.yaml"
        )
        with open(simulation_info_file, "r", encoding="utf-8") as f:
            simulation_info = yaml.safe_load(f)

        return simulation_info["sim_running"]

    @property
    def interrupted(self):
        """Returns a list of the simulations that are interrupted."""
        simulation_info_file = os.path.join(
            self.study_path, self.study_name, "simulation_info.yaml"
        )
        with open(simulation_info_file, "r", encoding="utf-8") as f:
            simulation_info = yaml.safe_load(f)

        return simulation_info["sim_interrupted"]

    @property
    def error(self):
        """Returns a list of the simulations that have error."""
        simulation_info_file = os.path.join(
            self.study_path, self.study_name, "simulation_info.yaml"
        )
        with open(simulation_info_file, "r", encoding="utf-8") as f:
            simulation_info = yaml.safe_load(f)

        return simulation_info["sim_error"]
