import os
import shutil
import subprocess
from datetime import datetime

import pkg_resources
import yaml

from .simulation_study import SimulationStudy
from .tools import clean_script_from_templates

INITIAL_INSTRUCTIONS_HTCONDOR_DEFAULT = """#!/bin/bash
# initial instructions

export EOS_MGM_URL=root://eosuser.cern.ch

source __REPLACE_WITH_CVMFS_PATH__
source __REPLACE_WITH_VENV_PATH__

# echo the sourced environments
echo "CVMFS environment:"
echo "__REPLACE_WITH_CVMFS_PATH__"
echo "VENV environment:"
echo "__REPLACE_WITH_VENV_PATH__"

SIMPATH=$1
# two levels up from the current folder
STUDYPATH=$(dirname $(dirname $SIMPATH))
# add the folder output_files to the STUDYPATH
OUTPUTPATH=$STUDYPATH/output_files
# get the name of the simulation from SIMPATH
SIMNAME=$(basename $SIMPATH)

echo "SIMPATH:"
echo $SIMPATH

echo "STUDYPATH:"
echo $STUDYPATH

echo "OUTPUTPATH:"
echo $OUTPUTPATH

echo "SIMNAME:"
echo $SIMNAME

# copy all contents of the folder SIMNAME to the current folder
cp -r ./$SIMNAME/* .

# delete the local folder SIMNAME
rm -rf ./$SIMNAME

# execute eos_stage_in.py
python eos_stage_in.py --yaml_path "___REPLACE_WITH_YAML_NAME___"

#___END_INITIAL_INSTRUCTIONS___
"""

FINAL_INSTRUCTIONS_HTCONDOR_DEFAULT = """
#___BEGIN_FINAL_INSTRUCTIONS___

if [ $? -eq 0 ]; then
    command_success="true"
else
    command_success="false"
fi

# if exists, remove the folder ./input_eos
if [ -d "./input_eos" ]; then
    rm -rf ./input_eos
fi
    
# final instructions
EOS_DIR=__REPLACE_WITH_EOS_DIR__

# we assume that all output files are generated in a folder named "output_files"
# so we want to copy and rename the entire folder to the EOS directory
# while creating symbolic links in the general output folder

# first, print the contents of the output_files folder
echo "Contents of the output_files folder:"
ls -l ./output_files

# create the EOS directory
eos mkdir -p $EOS_DIR/$SIMNAME

echo "Copying output_files content to EOS"
eos cp -r -p ./output_files/* $EOS_DIR/$SIMNAME

# create a symbolic link of the output_files folder in the OUTPUTPATH
ln -s $EOS_DIR/$SIMNAME $OUTPUTPATH/$SIMNAME

# create a marker file to signal that the simulation is finished in SIMPATH
if [ $command_success == "true" ]; then
    touch $SIMPATH/../../remote_touch_files/FINISHED_$(basename $SIMPATH)
else
    touch $SIMPATH/../../remote_touch_files/ERROR_$(basename $SIMPATH)
fi

"""

HTCONDOR_SUBMIT_FILE_COMMON_BEG = """
universe   = vanilla

executable = $(Executable)
arguments  = $(Simpath)

output     = $(Outpath)
error      = $(Errpath)
log        = __REPLACE_WITH_LOG_PATH__

transfer_input_files = $(Simpath), __REPLACE_WITH_EOSSTAGEIN__
transfer_output_files = ""

# requirements = regexp("(CentOS7|AlmaLinux9)", OpSysAndVer)

request_cpus = __REPLACE_WITH_REQUEST_CPUS__

MY.JobFlavour = "__REPLACE_WITH_TIME_LIMIT__"

MY.AccountingGroup = "group_u_BE.ABP.normal"
# MY.WantOS = "el9"

"""

HTCONDOR_SUBMIT_FILE_COMMON_END = """
queue Executable,Simpath,Outpath,Errpath from __REPLACE_WITH_QUEUE_FILE__
"""

HTCONDOR_SUBMIT_FILE_DEFAULT_CPU = HTCONDOR_SUBMIT_FILE_COMMON_BEG + HTCONDOR_SUBMIT_FILE_COMMON_END

HTCONDOR_SUBMIT_FILE_DEFAULT_GPU = (
    HTCONDOR_SUBMIT_FILE_COMMON_BEG + 
"""
requirements = regexp("(V100|A100)", Target.GPUs_DeviceName)

request_GPUs = __REPLACE_WITH_REQUEST_GPUS__
""" +
    HTCONDOR_SUBMIT_FILE_COMMON_END)


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
        default is "longlunch".
    cvmfs_path : str
        The path to the CVMFS environment to use.
        Default is "/cvmfs/sft.cern.ch/lcg/views/LCG_104a_cuda/x86_64-el9-gcc11-opt/setup.sh".
    venv_path : str
        The path to the virtual environment to use.
        Default is the same as cvmfs_path.
    eos_dir : str
        The path to the EOS directory where to copy the output files.
    bump_schedd : bool
        If True, bumps the schedd before submitting the jobs.
        Default is False.
    run_test : bool
        If True, runs only the test case, by default False.
    test_time_limit : str
        The time limit for the test case. By default, "espresso".

    Raises
    ------
    ValueError
        If the simulation study folders are not created.
    """
    sim_folder = os.path.join(simulation_study.study_path, simulation_study.study_name)

    initial_instructions = kwargs.pop(
        "initial_instructions", INITIAL_INSTRUCTIONS_HTCONDOR_DEFAULT
    )
    final_instructions = kwargs.pop(
        "final_instructions", FINAL_INSTRUCTIONS_HTCONDOR_DEFAULT
    )
    stdout_path = kwargs.pop("stdout_path", os.path.join(sim_folder, "out"))
    stderr_path = kwargs.pop("stderr_path", os.path.join(sim_folder, "err"))
    log_path = kwargs.pop("log_path", os.path.join(sim_folder, "log"))
    request_gpus = kwargs.pop("request_gpus", False)
    request_cpus = kwargs.pop("request_cpus", 1)
    time_limit = kwargs.pop("time_limit", "longlunch")
    bump_schedd = kwargs.pop("bump_schedd", False)
    run_test = kwargs.pop("run_test", False)
    test_time_limit = kwargs.pop("test_time_limit", "espresso")

    htcondor_submit_str = kwargs.pop(
        "htcondor_submit_template",
        HTCONDOR_SUBMIT_FILE_DEFAULT_CPU
        if not request_gpus
        else HTCONDOR_SUBMIT_FILE_DEFAULT_GPU,
    )

    cvmfs_path = kwargs.pop(
        "cvmfs_path",
        "/cvmfs/sft.cern.ch/lcg/views/LCG_104a_cuda/x86_64-el9-gcc11-opt/setup.sh",
    )
    # if no venv path is provided, just reload the cvmfs environment
    venv_path = kwargs.pop("venv_path", cvmfs_path)
    eos_dir = kwargs.pop("eos_dir", "/eos/user/c/camontan/data")

    # if unexpected keyword arguments are passed, raise an error
    if kwargs:
        raise ValueError(
            "Unexpected keyword arguments passed: " + ", ".join(kwargs.keys())
        )

    # create the folder "htcondor_support" in the study folder
    htcondor_support_folder = os.path.join(sim_folder, "htcondor_support")
    os.makedirs(htcondor_support_folder, exist_ok=True)

    # save the eos_stage_in.py file
    eos_sif_in = pkg_resources.resource_filename(
        "simanager", "templates/eos_stage_in/eos_stage_in.py"
    )
    # copy the file to the htcondor_support folder
    eos_sif_in_dest = os.path.join(htcondor_support_folder, "eos_stage_in.py")
    shutil.copyfile(eos_sif_in, eos_sif_in_dest)

    # specializations of the submit file
    htcondor_submit_str = htcondor_submit_str.replace(
        "__REPLACE_WITH_REQUEST_CPUS__", str(request_cpus)
    )
    htcondor_submit_str = htcondor_submit_str.replace(
        "__REPLACE_WITH_TIME_LIMIT__",
        time_limit if not run_test else test_time_limit
    )
    htcondor_submit_str = htcondor_submit_str.replace(
        "__REPLACE_WITH_QUEUE_FILE__",
        os.path.join(htcondor_support_folder, "queue.txt"),
    )
    htcondor_submit_str = htcondor_submit_str.replace(
        "__REPLACE_WITH_EOSSTAGEIN__", eos_sif_in_dest
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
    simulation_info_file = os.path.join(sim_folder, "simulation_info.yaml")
    with open(simulation_info_file, "r", encoding="utf-8") as f:
        simulation_info = yaml.safe_load(f)

    # get the list of simulations to run
    if run_test:
        simulations_to_run = ["test"]
    else:
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
    initial_instructions = initial_instructions.replace(
        "___REPLACE_WITH_YAML_NAME___", simulation_study.config_file
    )

    final_instructions = final_instructions.replace("__REPLACE_WITH_EOS_DIR__", eos_dir)

    queue_file_content = ""
    for sim in simulations_to_run:
        folder_path = os.path.join(root_folder, "scan", sim)
        main_file = os.path.join(folder_path, simulation_study.main_file)

        with open(main_file, "r", encoding="utf-8") as f:
            main_file_content = f.read()

        main_file_content = clean_script_from_templates(main_file_content)

        main_file_content = (
            initial_instructions + "\n" + main_file_content + "\n" + final_instructions
        )

        main_file_content = main_file_content.replace("__REPLACE_WITH_CASENAME__", sim)

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
        except KeyboardInterrupt:
            print("Keyboard interrupt detected, exiting...")
            print("Good luck!")
            return
        except Exception as e:
            print("An unexpected error occurred while bumping the schedd, exiting...")
            print("Good luck!")
            print("Error message:")
            print(e)
            raise e

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
    except KeyboardInterrupt:
        print("Keyboard interrupt detected, exiting...")
        print("----------------------------------------")
        print("You have been saved by the keyboard!")
        print("The jobs were not submitted!")
        print("----------------------------------------")
        return
    except Exception as e:
        print("An error occurred while submitting the jobs, exiting...")
        print("----------------------------------------")
        print("The gods are not pleased with you!")
        print("The jobs were not submitted!")
        print("----------------------------------------")
        print("Error message:")
        print(e)
        raise e

    now = datetime.now()
    print("Jobs submitted at", now)
    print("----------------------------------------")
    print("Good luck!")
    print("----------------------------------------")
    print("Remember to check the status of your jobs")
    print("by running `condor_q` or 'simanager status")
    print("----------------------------------------")
