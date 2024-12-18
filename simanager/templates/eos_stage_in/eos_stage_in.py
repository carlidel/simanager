import argparse
import os
import subprocess

import yaml


def eos_stage_in(eos_path: str, destination: str):
    basename = os.path.basename(eos_path)
    # destination = os.path.join(destination, basename)
    os.makedirs(destination, exist_ok=True)
    print(f"Copying {eos_path} to {destination}")
    subprocess.run(["eos", "cp", eos_path, destination], check=True)
    return os.path.join(destination, basename)


def eos_stage_in_directory(eos_path: str, destination: str):
    basename = os.path.basename(eos_path)
    destination = os.path.join(destination, basename)
    # make sure both eos_path and destination end with a slash
    if not eos_path.endswith("/"):
        eos_path += "/"
    if not destination.endswith("/"):
        destination += "/"
    os.makedirs(destination, exist_ok=True)
    print(f"Copying {eos_path} to {destination}")
    subprocess.run(["eos", "cp", "-r", eos_path, destination], check=True)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--yaml_path", help="The path to the config file")
    args = parser.parse_args()

    with open(args.yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    to_move_dict = {}

    # scan the dictionary for eos paths
    for key, value in config.items():
        if isinstance(value, str) and (value.startswith("/eos") or value.startswith("/afs")):
            to_move_dict[key] = value

    # move the files
    for key, value in to_move_dict.items():
        # if value is a directory, use eos_stage_in_directory
        # check if it is a directory properly
        if os.path.isdir(value):
            print(f"Staging in directory {value}")
            config[key] = eos_stage_in_directory(value, "./input_eos")
        else:
            print(f"Staging in file {value}")
            config[key] = eos_stage_in(value, "./input_eos")

    # write the new config file
    with open(args.yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f)

    print("Done staging in files from EOS.")
