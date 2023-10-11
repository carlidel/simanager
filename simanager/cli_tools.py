# simanager/cli_tool.py
import argparse
import os
import sys
import time

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
        "--name", help="Name of the simulation folder", default="sim_scan"
    )

    # Subcommand: create
    subparsers.add_parser(
        "create",
        help="Create a new simulation. Expects a 'simulation_study.yaml' file in the current directory.",
    )

    # Subcommand: run-local
    run_local_parser = subparsers.add_parser("run-local", help="Run simulation locally")
    run_local_parser.add_argument(
        "config",
        help="Configuration file",
    )
    run_local_parser.add_argument("--simpath", help="Simulation path", default="./")

    # Subcommand: run-htcondor
    # Add similar configuration for 'run-htcondor'
    run_htcondor_parser = subparsers.add_parser(
        "run-htcondor", help="Run simulation on HTCondor"
    )
    run_htcondor_parser.add_argument(
        "config",
        help="Configuration file",
    )
    run_htcondor_parser.add_argument("--simpath", help="Simulation path", default="./")

    # Subcommand: run-slurm
    # Add similar configuration for 'run-slurm'
    run_slurm_parser = subparsers.add_parser(
        "run-slurm", help="Run simulation on SLURM"
    )
    run_slurm_parser.add_argument(
        "config",
        help="Configuration file",
    )
    run_slurm_parser.add_argument("--simpath", help="Simulation path", default="./")

    # Subcommand: reset
    reset_parser = subparsers.add_parser("reset", help="Reset simulation")
    # set boolean flags to True by default
    reset_parser.add_argument(
        "--reset-all", help="Reset all simulations", action="store_true"
    )
    reset_parser.add_argument(
        "--restore-original",
        help="Restore original files",
        action="store_true",
    )
    reset_parser.add_argument(
        "--clear-out-folder",
        help="Clear out folder",
        action="store_true",
    )
    reset_parser.add_argument(
        "--clear-err-folder",
        help="Clear err folder",
        action="store_true",
    )
    reset_parser.add_argument(
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
        copy_template(args.name)
    elif args.subcommand == "run-local":
        # load the simulation
        sim = SimulationStudy.load_folder(args.simpath)
        # load the config yaml file into a dict
        with open(args.config, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        # run the simulation, pass the config dict as kwargs
        job_run_local(sim, **config)
        sim.print_sim_status()
    elif args.subcommand == "run-htcondor":
        # load the simulation
        sim = SimulationStudy.load_folder(args.simpath)
        # load the config yaml file into a dict
        with open(args.config, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        # run the simulation, pass the config dict as kwargs
        job_run_htcondor(sim, **config)
        sim.print_sim_status()
    elif args.subcommand == "run-slurm":
        # load the simulation
        sim = SimulationStudy.load_folder(args.simpath)
        # load the config yaml file into a dict
        with open(args.config, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
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


if __name__ == "__main__":
    main()
