import os
import re
import subprocess
from datetime import datetime

import yaml

from .simulation_study import SimulationStudy

INSTRUCTIONS_SLURM_DEFAULT = """#!/bin/bash

#SBATCH --job-name=__REPLACE_WITH_JOB_NAME__
#SBATCH --output=__REPLACE_WITH_SLURM_OUT_PATH__
#SBATCH --error=__REPLACE_WITH_SLURM_ERR_PATH__
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
pwd

# load python environment
source __REPLACE_WITH_VENV_PATH__

# run the simulation main file
# stdout and stderr are redirected to $3 and $4
bash $2 > $3 2> $4

# final instructions

# create a marker file to signal that the simulation is finished in SIMPATH
touch $SIMPATH/remote_finished
"""

SUBMISSION_SLURM_DEFAULT = """#!/bin/bash

# Define three lists as arrays
SIMPATHS=__REPLACE_WITH_SIMPATHS__
OUTPATHS=__REPLACE_WITH_OUTPATHS__
ERRPATHS=__REPLACE_WITH_ERRPATHS__

# Calculate the length of one of the lists (assuming all lists have the same length)
length=${#SIMPATHS[@]}

# Iterate over the indices of the arrays
for ((i = 0; i < length; i++)); do
    SIM=${SIMPATHS[i]}
    OUT=${OUTPATHS[i]}
    ERR=${ERRPATHS[i]}

    # submit the job
    sbatch __REPLACE_WITH_SLURM_SUBMIT_FILE__ $SIM __REPLACE_WITH_MAINFILE__ $OUT $ERR
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
    stdout_path_slurm : str
        The path to the file where the stdout files will be saved in the
        SLURM submit file.
    stderr_path : str
        The path to the folder where the stderr files will be saved.
    stderr_path_slurm : str
        The path to the file where the stderr files will be saved in the
        SLURM submit file.
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
    sim_folder = os.path.join(simulation_study.study_path, simulation_study.study_name)
    slurm_instructions = kwargs.pop("slurm_instructions", INSTRUCTIONS_SLURM_DEFAULT)
    stdout_path = kwargs.pop("stdout_path", os.path.join(sim_folder, "out"))
    stdout_path_slurm = kwargs.pop(
        "stdout_path_slurm", os.path.join(sim_folder, "out", "slurm.out")
    )
    stderr_path = kwargs.pop("stderr_path", os.path.join(sim_folder, "err"))
    stderr_path_slurm = kwargs.pop(
        "stderr_path_slurm", os.path.join(sim_folder, "err", "slurm.err")
    )
    log_path = kwargs.pop("log_path", os.path.join(sim_folder, "log"))
    request_gpus = kwargs.pop("request_gpus", False)
    request_cpus = kwargs.pop("request_cpus", 1)
    request_ram = kwargs.pop("request_ram", 2 * request_cpus)
    time_limit = kwargs.pop("time_limit", "02:00:00")
    venv_path = kwargs.pop("venv_path", "/home/HPC/camontan/anaconda3/bin/activate")
    partition_option = kwargs.pop("partition_option", "slurm_hpc_acc")
    slurm_submit_template = kwargs.pop(
        "slurm_submit_template", SUBMISSION_SLURM_DEFAULT
    )

    # if unexpected keyword arguments are passed, raise an error
    if kwargs:
        raise ValueError(
            "Unexpected keyword arguments passed: " + ", ".join(kwargs.keys())
        )

    # create the folder "slurm_support" in the study folder
    slurm_support_folder = os.path.join(sim_folder, "slurm_support")
    os.makedirs(slurm_support_folder, exist_ok=True)

    # specialization of the SLURM file
    slurm_instructions = slurm_instructions.replace(
        "__REPLACE_WITH_JOB_NAME__", simulation_study.study_name
    )
    slurm_instructions = slurm_instructions.replace(
        "__REPLACE_WITH_SLURM_OUT_PATH__", stdout_path_slurm
    )
    slurm_instructions = slurm_instructions.replace(
        "__REPLACE_WITH_SLURM_ERR_PATH__", stderr_path_slurm
    )
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
    for sim in simulations_to_run:
        folder_path = os.path.join(root_folder, "scan", sim)

        queue_simpath_list.append(folder_path)
        queue_outpath_list.append(os.path.join(stdout_path, sim + ".out"))
        queue_errpath_list.append(os.path.join(stderr_path, sim + ".err"))

        print(f"Added {sim} to the queue file")

    print("Total number of jobs:", len(simulations_to_run))

    # specialize the submission file
    slurm_submit_template = slurm_submit_template.replace(
        "__REPLACE_WITH_SIMPATHS__",
        "(" + " ".join([f'"{s}"' for s in queue_simpath_list]) + ")",
    )
    slurm_submit_template = slurm_submit_template.replace(
        "__REPLACE_WITH_OUTPATHS__",
        "(" + " ".join([f'"{s}"' for s in queue_outpath_list]) + ")",
    )
    slurm_submit_template = slurm_submit_template.replace(
        "__REPLACE_WITH_ERRPATHS__",
        "(" + " ".join([f'"{s}"' for s in queue_errpath_list]) + ")",
    )
    slurm_submit_template = slurm_submit_template.replace(
        "__REPLACE_WITH_MAIN_FILE__", simulation_study.main_file
    )

    slurm_submit_template = slurm_submit_template.replace(
        "__REPLACE_WITH_SLURM_SUBMIT_FILE__", slurm_submit_file
    )
    slurm_submit_template = slurm_submit_template.replace(
        "__REPLACE_WITH_MAINFILE__", simulation_study.main_file
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
