# simanager/cli_tool.py
import argparse
import os
import re
import subprocess
import sys
import time
import warnings

import yaml

from .copy_template import copy_template
from .job_run_htcondor import job_run_htcondor
from .job_run_local import job_run_local
from .job_run_slurm import job_run_slurm
from .simulation_study import SimulationStudy


def generate_parser():
    parser = argparse.ArgumentParser(description="General Simulation Manager")

    # Create subparsers for each subcommand
    subparsers = parser.add_subparsers(title="Subcommands", dest="subcommand")

    # Subcommand: template
    template_parser = subparsers.add_parser(
        "copy-template", help="Copy the template simulation in the current directory"
    )
    template_parser.add_argument(
        "-n", "--name", help="Name of the simulation folder", default="sim_scan"
    )

    # Subcommand: create
    subparsers.add_parser(
        "create",
        help="Create a new simulation. Expects a 'simulation_study.yaml' file in the current directory.",
    )

    # Subcommand: run-local
    run_local_parser = subparsers.add_parser("run-local", help="Run simulation locally")
    run_local_parser.add_argument(
        "-c",
        "--config",
        help="Configuration file",
        default="run_config.yaml",
    )
    run_local_parser.add_argument("--simpath", help="Simulation path", default="./")
    run_local_parser.add_argument(
        "-t", "--run-test", help="Run the test simulation", action="store_true"
    )

    # Subcommand: run-htcondor
    # Add similar configuration for 'run-htcondor'
    run_htcondor_parser = subparsers.add_parser(
        "run-htcondor", help="Run simulation on HTCondor"
    )
    run_htcondor_parser.add_argument(
        "-c",
        "--config",
        help="Configuration file",
        default="run_config.yaml",
    )
    run_htcondor_parser.add_argument("--simpath", help="Simulation path", default="./")
    run_htcondor_parser.add_argument(
        "-t", "--run-test", help="Run the test simulation", action="store_true"
    )

    # Subcommand: run-slurm
    # Add similar configuration for 'run-slurm'
    run_slurm_parser = subparsers.add_parser(
        "run-slurm", help="Run simulation on SLURM"
    )
    run_slurm_parser.add_argument(
        "-c",
        "--config",
        help="Configuration file",
        default="run_config.yaml",
    )
    run_slurm_parser.add_argument("--simpath", help="Simulation path", default="./")
    run_slurm_parser.add_argument(
        "-t", "--run-test", help="Run the test simulation", action="store_true"
    )

    # Subcommand: reset
    reset_parser = subparsers.add_parser("reset", help="Reset simulation")
    # set boolean flags to True by default
    reset_parser.add_argument(
        "--reset-all", help="Reset all simulations", action="store_true"
    )
    reset_parser.add_argument(
        "-r",
        "--restore-original",
        help="Restore original files",
        action="store_true",
    )
    reset_parser.add_argument(
        "-o",
        "--clear-out-folder",
        help="Clear out folder",
        action="store_true",
    )
    reset_parser.add_argument(
        "-e",
        "--clear-err-folder",
        help="Clear err folder",
        action="store_true",
    )
    reset_parser.add_argument(
        "-l",
        "--clear-log-folder",
        help="Clear log folder",
        action="store_true",
    )
    reset_parser.add_argument("--simpath", help="Simulation path", default="./")

    # Subcommand: nuke
    nuke_parser = subparsers.add_parser(
        "nuke", help="nuke down the simulation for good!"
    )
    nuke_parser.add_argument("--simpath", help="Simulation path", default="./")

    # Subcommand: status
    status_parser = subparsers.add_parser("status", help="Print simulation status")
    status_parser.add_argument("--simpath", help="Simulation path", default="./")

    # Subcommand: cat-err
    cat_err_parser = subparsers.add_parser(
        "cat-err", help="Print contents of err files"
    )
    cat_err_parser.add_argument("--simpath", help="Simulation path", default="./")
    cat_err_parser.add_argument("--errpath", help="Error path", default="err")
    cat_err_parser.add_argument("--idx", help="Simulation index", default=-1, type=int)

    # Subcommand: cat-out
    cat_out_parser = subparsers.add_parser(
        "cat-out", help="Print contents of out files"
    )
    cat_out_parser.add_argument("--simpath", help="Simulation path", default="./")
    cat_out_parser.add_argument("--outpath", help="Output path", default="out")
    cat_out_parser.add_argument("--idx", help="Simulation index", default=-1, type=int)

    # Subcommand: cat-log
    cat_log_parser = subparsers.add_parser(
        "cat-log", help="Print contents of log files"
    )
    cat_log_parser.add_argument("--simpath", help="Simulation path", default="./")
    cat_log_parser.add_argument("--logpath", help="Log path", default="log")
    cat_log_parser.add_argument("--idx", help="Simulation index", default=-1, type=int)

    # Subcommand: extract-file
    extract_file_parser = subparsers.add_parser(
        "extract-file",
        help="Extract output files from a simulation and places them in a target folder. If the target folder does not exist, it will be created. If the target file is a symlink, an equivalent symlink will be created in the target folder.",
    )
    extract_file_parser.add_argument("--simpath", help="Simulation path", default="./")
    extract_file_parser.add_argument(
        "--target", help="Target folder", default="extracted_files"
    )
    extract_file_parser.add_argument(
        "--file",
        help="Regex of files to extract. If not specified, all .h5 and .pkl files will be extracted.",
        default=None,
    )

    # Subcommand: self-update
    subparsers.add_parser(
        "self-update",
        help="CURSED AND CRISPY: Update simanager to the latest version. Assumes that the package is installed with 'pip install -e' and that the directory is a clone of the git repo.",
    )

    # Subcommand: remove-log-files
    remove_log_files = subparsers.add_parser(
        "remove-log-files",
        help="Remove all log, err, out files from the simulation folder. To be considered only when these files constitute a large portion of the disk space and are not needed anymore. It will keep one log, err, out file just for reference.",
    )
    remove_log_files.add_argument("--simpath", help="Simulation path", default="./")

    return parser


def confirm_execution(timeout):
    print("Are you sure you want to execute this command?")
    print(f"Press Enter to proceed or CTRL+C to cancel ({timeout} seconds timeout):")

    start_time = time.time()
    input_thread = sys.stdin.readline()
    elapsed_time = time.time() - start_time

    # If the user presses Enter or the timeout (in seconds) is reached, execute the command
    if not input_thread.strip() or elapsed_time >= timeout:
        return True
    else:
        return False


def main():
    parser = generate_parser()
    args = parser.parse_args()

    # If no subcommand is specified, print help and exit
    if args.subcommand is None:
        parser.print_help()
        return

    # Handle subcommands and their respective arguments/options here
    if args.subcommand == "create":
        # Handle 'create' subcommand
        print("Creating simulation from configuration file.")
        # Create a new simulation from the configuration file
        sim = SimulationStudy.load_folder("./")
        sim.initialize_folders()
        sim.print_sim_status()
    elif args.subcommand == "copy-template":
        print("Copying template simulation.")
        # Copy the template simulation
        copy_template(folder_name=args.name)
    elif args.subcommand == "run-local":
        # load the simulation
        sim = SimulationStudy.load_folder(args.simpath)
        # load the config yaml file into a dict
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if "run_local" in config:
                config = config["run_local"]
                if config is None:
                    config = {}
        except FileNotFoundError:
            warnings.warn(
                f"Config file '{args.config}' not found. Using default config."
            )
            config = {}
        config["run_test"] = args.run_test
        if args.run_test:
            print("RUNNING TEST SIMULATION.")
        # run the simulation, pass the config dict as kwargs
        job_run_local(sim, **config)
        sim.print_sim_status()
    elif args.subcommand == "run-htcondor":
        # load the simulation
        sim = SimulationStudy.load_folder(args.simpath)
        # load the config yaml file into a dict
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if "run_htcondor" in config:
                config = config["run_htcondor"]
                if config is None:
                    config = {}
        except FileNotFoundError:
            warnings.warn(
                f"Config file '{args.config}' not found. Using default config."
            )
            config = {}
        config["run_test"] = args.run_test
        if args.run_test:
            print("RUNNING TEST SIMULATION.")
        # run the simulation, pass the config dict as kwargs
        job_run_htcondor(sim, **config)
        sim.print_sim_status()
    elif args.subcommand == "run-slurm":
        # load the simulation
        sim = SimulationStudy.load_folder(args.simpath)
        # load the config yaml file into a dict
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if "run_slurm" in config:
                config = config["run_slurm"]
                if config is None:
                    config = {}
            config["run_test"] = args.run_test
            if args.run_test:
                print("RUNNING TEST SIMULATION.")
        except FileNotFoundError:
            warnings.warn(
                f"Config file '{args.config}' not found. Using default config."
            )
            config = {}
        # run the simulation, pass the config dict as kwargs
        job_run_slurm(sim, **config)
        sim.print_sim_status()
    elif args.subcommand == "reset":
        # load the simulation
        sim = SimulationStudy.load_folder(args.simpath)

        if args.restore_original:
            try:
                if not confirm_execution(7):
                    print("Aborting.")
                    return
            except KeyboardInterrupt:
                print("Aborting.")
                return
        # reset the simulation
        sim.reset_simulations(
            reset_all=args.reset_all,
            restore_original=args.restore_original,
            clear_out_folder=args.clear_out_folder,
            clear_err_folder=args.clear_err_folder,
            clear_log_folder=args.clear_log_folder,
        )
        sim.print_sim_status()
    elif args.subcommand == "nuke":
        # load the simulation
        sim = SimulationStudy.load_folder("./")
        # nuke the simulation
        try:
            if not confirm_execution(60):
                print("Aborting.")
                return
        except KeyboardInterrupt:
            print("Aborting.")
            return
        sim.nuke_simulation()
    elif args.subcommand == "status":
        # load the simulation
        sim = SimulationStudy.load_folder(args.simpath)
        # print the simulation status
        sim.print_sim_status()
    elif args.subcommand == "cat-err":
        # load the simulation
        sim = SimulationStudy.load_folder(args.simpath)
        # get the path of the err folder
        sim_folder = os.path.join(sim.study_path, sim.study_name)
        err_folder = os.path.join(sim_folder, args.errpath)
        err_files = os.listdir(err_folder)
        if args.idx == -1:
            # print the contents of all err files
            for err_file in err_files:
                lenght_terminal = os.get_terminal_size().columns
                print("=" * lenght_terminal)
                print(err_file)
                print("=" * lenght_terminal)
                print("")
                with open(
                    os.path.join(err_folder, err_file), "r", encoding="utf-8"
                ) as f:
                    print(f.read())
        else:
            # print the contents of the err file with index args.idx
            with open(
                os.path.join(err_folder, err_files[args.idx]), "r", encoding="utf-8"
            ) as f:
                print(f.read())
    elif args.subcommand == "cat-out":
        # load the simulation
        sim = SimulationStudy.load_folder(args.simpath)
        # get the path of the out folder
        sim_folder = os.path.join(sim.study_path, sim.study_name)
        out_folder = os.path.join(sim_folder, args.outpath)
        out_files = os.listdir(out_folder)
        if args.idx == -1:
            # print the contents of all out files
            for out_file in out_files:
                lenght_terminal = os.get_terminal_size().columns
                print("=" * lenght_terminal)
                print(out_file)
                print("=" * lenght_terminal)
                print("")
                with open(
                    os.path.join(out_folder, out_file), "r", encoding="utf-8"
                ) as f:
                    print(f.read())
                print("")
        else:
            # print the contents of the out file with index args.idx
            with open(
                os.path.join(out_folder, out_files[args.idx]), "r", encoding="utf-8"
            ) as f:
                print(f.read())
    elif args.subcommand == "cat-log":
        # load the simulation
        sim = SimulationStudy.load_folder(args.simpath)
        # get the path of the log folder
        sim_folder = os.path.join(sim.study_path, sim.study_name)
        log_folder = os.path.join(sim_folder, args.logpath)
        log_files = os.listdir(log_folder)
        if args.idx == -1:
            # print the contents of all log files
            for log_file in log_files:
                lenght_terminal = os.get_terminal_size().columns
                print("=" * lenght_terminal)
                print(out_file)
                print("=" * lenght_terminal)
                print("")
                with open(
                    os.path.join(log_folder, log_file), "r", encoding="utf-8"
                ) as f:
                    print(f.read())
                print("")
        else:
            # print the contents of the log file with index args.idx
            with open(
                os.path.join(log_folder, log_files[args.idx]), "r", encoding="utf-8"
            ) as f:
                print(f.read())
    elif args.subcommand == "extract-file":
        # load the simulation
        sim = SimulationStudy.load_folder(args.simpath)
        # extract the file
        sim_folder = os.path.join(sim.study_path, sim.study_name)
        scan_folder = os.path.join(sim_folder, "scan")
        # get list of all files in a sim finished folder
        files = os.listdir(os.path.join(scan_folder, sim.finished[0]))
        # filter files based on regex
        if args.file is not None:
            files = [f for f in files if re.match(args.file, f)]
        else:
            files = [f for f in files if re.match(r".*\.(h5|pkl)", f)]

        # create target folder
        os.makedirs(os.path.join(sim_folder, args.target), exist_ok=True)

        # extract files
        for sim in sim.finished:
            sim_folder = os.path.join(scan_folder, sim)
            for f in files:
                new_filename = f"{sim}_{f}"
                is_symlink = os.path.islink(os.path.join(sim_folder, f))
                if is_symlink:
                    target = os.readlink(os.path.join(sim_folder, f))
                    os.symlink(target, os.path.join(sim_folder, new_filename))
                else:
                    # copy the file
                    os.system(
                        f"cp {os.path.join(sim_folder, f)} {os.path.join(sim_folder, new_filename)}"
                    )
    elif args.subcommand == "self-update":
        # get the directory of this python script
        this_directory = os.path.dirname(os.path.realpath(__file__))
        # attempt a git pull
        print("Attempting to update simanager...")
        subprocess.run(
            ["git", "pull"],
            cwd=this_directory,
            check=True,
        )
    elif args.subcommand == "remove-log-files":
        # load the simulation
        sim = SimulationStudy.load_folder(args.simpath)
        # remove log files
        sim_folder = os.path.join(sim.study_path, sim.study_name)
        log_folder = os.path.join(sim_folder, "log")
        out_folder = os.path.join(sim_folder, "out")
        err_folder = os.path.join(sim_folder, "err")
        log_files = os.listdir(log_folder)
        out_files = os.listdir(out_folder)
        err_files = os.listdir(err_folder)
        # remove all but one log file
        for log_file in log_files[:-1]:
            os.remove(os.path.join(log_folder, log_file))
            print(f"Removed {log_file}")
        # remove all but one out file
        for out_file in out_files[:-1]:
            os.remove(os.path.join(out_folder, out_file))
            print(f"Removed {out_file}")
        # remove all but one err file
        for err_file in err_files[:-1]:
            os.remove(os.path.join(err_folder, err_file))
            print(f"Removed {err_file}")
        print(f"Kept {log_files[-1]}, {out_files[-1]}, {err_files[-1]}")
        print("Done.")


if __name__ == "__main__":
    main()
