import os
import subprocess
from datetime import datetime
from multiprocessing import Manager, Pool

import yaml

from .simulation_study import SimulationStudy

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


def execute_command(
    command,
    folder_path,
    stdout_file,
    stderr_file,
    gpu_id,
    simulation_info,
    lock,
    simulation_study: SimulationStudy,
):
    """Executes a command.

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
        The ID of the GPU to use. If it is -1, the command will be executed on
        the CPU.
    simulation_info : dict
        The dictionary containing the simulation info. Composed of manager.list
        objects, so it can be shared between processes.
    lock : multiprocessing.Lock
        The lock to use when updating the simulation info.
    simulation_study : SimulationStudy
        The simulation study.
    """
    # check if the run flag is set to 0
    if simulation_info["run_flag"].value == 0:
        print(f"Skipping simulation in folder {folder_path}...")
        return False

    # Set the CUDA_VISIBLE_DEVICES environment variable to the GPU ID
    env = os.environ.copy()
    if gpu_id != -1:
        env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    simulation_name = os.path.basename(folder_path)

    # Update the simulation status
    with lock:
        simulation_info["sim_not_started"].remove(simulation_name)
        simulation_info["sim_running"].append(simulation_name)
        simulation_study.set_sim_status(simulation_name, "running")

    # Execute the command using subprocess
    try:
        stdout_file = open(stdout_file, "w", encoding="utf-8")
        stderr_file = open(stderr_file, "w", encoding="utf-8")
        print(
            f"Running simulation in folder {folder_path}"
            + (f" on GPU {gpu_id}..." if gpu_id != -1 else "on CPU...")
        )
        subprocess.run(
            command,
            stdout=stdout_file,
            stderr=stderr_file,
            env=env,
            cwd=folder_path,
            check=True,
        )
        stdout_file.close()
        stderr_file.close()
    except KeyboardInterrupt:
        print(
            f"KeyboardInterrupt detected, stopping simulation in folder {folder_path}"
            + (f" on GPU {gpu_id}..." if gpu_id != -1 else "on CPU...")
        )
        stdout_file.close()
        stderr_file.close()
        # Update the simulation status
        with lock:
            simulation_info["sim_running"].remove(simulation_name)
            simulation_info["sim_interrupted"].append(simulation_name)
            simulation_study.set_sim_status(simulation_name, "interrupted")
        return False
    except subprocess.CalledProcessError:
        print(
            f"Error running simulation in folder {simulation_name}"
            + (f" on GPU {gpu_id}..." if gpu_id != -1 else "on CPU...")
        )
        # Update the simulation status
        with lock:
            simulation_info["sim_running"].remove(simulation_name)
            simulation_info["sim_error"].append(simulation_name)
            simulation_study.set_sim_status(simulation_name, "error")
        return False
    else:
        print(
            f"Finished running simulation in folder {simulation_name}"
            + (f" on GPU {gpu_id}..." if gpu_id != -1 else "on CPU...")
        )
        # Update the simulation status once the simulation is finished
        with lock:
            simulation_info["sim_running"].remove(simulation_name)
            simulation_info["sim_finished"].append(simulation_name)
            simulation_study.set_sim_status(simulation_name, "finished")
        return True


def command_executor(args):
    """Executes a command on a GPU.

    Parameters
    ----------
    args : tuple
        The arguments to pass to the execute_command_on_gpu function.

    Returns
    -------
    int
        The return code of the process.
    """
    execute_command(*args)
    return 0


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
    n_concurrent_jobs : int
        To be used if gpu_available_list is not passed. The number of
        concurrent jobs to run. By default, it is set to the number of CPUs
        available.

    Raises
    ------
    ValueError
        If the simulation study folders are not created.
    """
    initial_instructions = kwargs.pop(
        "initial_instructions", INITIAL_INSTRUCTIONS_LOCAL_DEFAULT
    )
    final_instructions = kwargs.pop(
        "final_instructions", FINAL_INSTRUCTIONS_LOCAL_DEFAULT
    )
    sim_folder = os.path.join(simulation_study.study_path, simulation_study.study_name)
    stdout_path = kwargs.pop("stdout_path", os.path.join(sim_folder, "out"))
    stderr_path = kwargs.pop("stderr_path", os.path.join(sim_folder, "err"))
    log_path = kwargs.pop("log_path", os.path.join(sim_folder, "log"))

    gpu_available_list = kwargs.pop("gpu_available_list", [])
    n_concurrent_jobs = kwargs.pop("n_concurrent_jobs", os.cpu_count())

    # if unexpected keyword arguments are passed, raise an error
    if kwargs:
        raise ValueError(
            "Unexpected keyword arguments passed: " + ", ".join(kwargs.keys())
        )

    # load the simulation info
    simulation_info_file = os.path.join(sim_folder, "simulation_info.yaml")
    with open(simulation_info_file, "r", encoding="utf-8") as f:
        simulation_info = yaml.safe_load(f)

    # get the list of simulations to run
    simulations_to_run = simulation_info["sim_not_started"].copy()
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

        # stdout_file_list.append(
        #     open(os.path.join(stdout_path, sim + ".out"), "w", encoding="utf-8")
        # )
        # stderr_file_list.append(
        #     open(os.path.join(stderr_path, sim + ".err"), "w", encoding="utf-8")
        # )

    # run the simulations in parallel
    n_gpu_available = len(gpu_available_list)

    if n_gpu_available == 0:
        for i, sim in enumerate(simulations_to_run):
            stdout_file_list.append(os.path.join(stdout_path, sim + ".out"))
            stderr_file_list.append(os.path.join(stderr_path, sim + ".err"))

        manager = Manager()
        shared_sim_status = {
            "sim_not_started": manager.list(simulation_info["sim_not_started"]),
            "sim_finished": manager.list(simulation_info["sim_finished"]),
            "sim_interrupted": manager.list(simulation_info["sim_interrupted"]),
            "sim_error": manager.list(simulation_info["sim_error"]),
            "sim_running": manager.list(simulation_info["sim_running"]),
            "run_flag": manager.Value("i", 1),
        }
        print("Shared simulation status:", shared_sim_status["sim_not_started"])
        lock = manager.Lock()

        argmunet_list = []
        for i, sim in enumerate(simulations_to_run):
            folder_path = os.path.join(root_folder, "scan", sim)
            main_file = os.path.join(folder_path, simulation_study.main_file)

            argmunet_list.append(
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
                    -1,
                    shared_sim_status,
                    lock,
                    simulation_study,
                )
            )
        try:
            starting_time = datetime.now()
            print("Running simulations...")
            pool = Pool(n_concurrent_jobs)
            result = pool.map_async(command_executor, argmunet_list)
            pool.close()
            print(f"Started running at {starting_time}...")
            result.get()
        except KeyboardInterrupt:
            print(
                "KeyboardInterrupt detected, wait for running simulations to finish gracefully..."
            )
            # set the run flag to 0
            with lock:
                shared_sim_status["run_flag"].value = 0

            try:
                result.get()
                pool.join()
            except KeyboardInterrupt:
                print("Ok then, force stop the simulations...")
                pool.terminate()
                pool.join()
        else:
            finishing_time = datetime.now()
            print("Finished running simulations...")
            print(f"Finished running at {finishing_time}...")
            print(f"Total running time: {finishing_time - starting_time}...")

        # update the simulation status from the shared dictionary
        simulation_info["sim_not_started"] = list(shared_sim_status["sim_not_started"])
        simulation_info["sim_finished"] = list(shared_sim_status["sim_finished"])
        simulation_info["sim_interrupted"] = list(shared_sim_status["sim_interrupted"])
        simulation_info["sim_error"] = list(shared_sim_status["sim_error"])
        simulation_info["sim_running"] = list(shared_sim_status["sim_running"])

        simulation_info["sim_interrupted"] += simulation_info["sim_running"]
        simulation_info["sim_running"] = []
        # save the simulation info
        with open(simulation_info_file, "w", encoding="utf-8") as f:
            yaml.dump(simulation_info, f)
    else:
        # In this case, we first separate the simulations to run in groups
        # equal to the number of available GPUs, and then we run each group
        # in parallel using the GPUs available on separate pools of one worker.
        # This way, we can run multiple simulations in parallel, but each
        # simulation will use only one GPU. With no risk of running two or more
        # simulations on the same GPU.
        for i, sim in enumerate(simulations_to_run):
            stdout_file_list.append(os.path.join(stdout_path, sim + ".out"))
            stderr_file_list.append(os.path.join(stderr_path, sim + ".err"))

        manager = Manager()
        shared_sim_status = {
            "sim_not_started": manager.list(simulation_info["sim_not_started"]),
            "sim_finished": manager.list(simulation_info["sim_finished"]),
            "sim_interrupted": manager.list(simulation_info["sim_interrupted"]),
            "sim_error": manager.list(simulation_info["sim_error"]),
            "sim_running": manager.list(simulation_info["sim_running"]),
            "run_flag": manager.Value("i", 1),
        }
        print("Shared simulation status:", shared_sim_status["sim_not_started"])
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
                pool_list[-1].map_async(command_executor, argument_dict[key])
                print(f"Created a pool with {len(argument_dict[key])} jobs...")
            for pool in pool_list:
                pool.close()
            # join the pools
            for pool in pool_list:
                pool.join()
        except KeyboardInterrupt:
            stopping_time = datetime.now()
            print(
                "KeyboardInterrupt detected, wait for running simulations to finish gracefully..."
            )
            # set the run flag to 0
            with lock:
                shared_sim_status["run_flag"].value = 0

            try:
                result.get()
                pool.join()
            except KeyboardInterrupt:
                print("Ok then! Force stop the simulations...")
                pool.terminate()
                pool.join()
        stopping_time = datetime.now()
        print("Finished running simulations...")
        print(f"Finished running at {stopping_time}...")
        print(f"Total running time: {stopping_time - starting_time}...")
        print("Updating simulation info...")
        # update the simulation status from the shared dictionary
        simulation_info["sim_not_started"] = list(shared_sim_status["sim_not_started"])
        simulation_info["sim_finished"] = list(shared_sim_status["sim_finished"])
        simulation_info["sim_interrupted"] = list(shared_sim_status["sim_interrupted"])
        simulation_info["sim_error"] = list(shared_sim_status["sim_error"])
        simulation_info["sim_running"] = list(shared_sim_status["sim_running"])

        simulation_info["sim_interrupted"] += simulation_info["sim_running"]
        simulation_info["sim_running"] = []
        # save the simulation info
        with open(simulation_info_file, "w", encoding="utf-8") as f:
            yaml.dump(simulation_info, f)
