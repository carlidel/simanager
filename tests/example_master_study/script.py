import argparse
import datetime
import os
import pickle
import sys
import time

import h5py
import yaml


def print_yaml_dict(yaml_dict, indent=1):
    for key, value in yaml_dict.items():
        print("    " * indent + str(key))
        if isinstance(value, dict):
            print_yaml_dict(value, indent + 1)
        else:
            print("    " * (indent + 1) + str(value))


print(f"Starting at {datetime.datetime.now()}", file=sys.stderr)

parser = argparse.ArgumentParser()
parser.add_argument("--yaml_path", type=str, required=True)

args = parser.parse_args()

# open the yaml file
with open(args.yaml_path, "r", encoding="utf-8") as f:
    yaml_dict = yaml.safe_load(f)

# print the yaml file on standard output
print_yaml_dict(yaml_dict)

# print a message on standard error
print("This is a message on standard error", file=sys.stderr)

# save the yaml file in a pickle
with open("yaml_dict.pickle", "wb") as f:
    pickle.dump(yaml_dict, f)

# save the yaml file in an hdf5
with h5py.File("yaml_dict.hdf5", "w") as f:
    for key, value in yaml_dict.items():
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                f.create_dataset(f"{key}/{subkey}", data=subvalue)
        else:
            f.create_dataset(key, data=value)

# check if a gpu is available
try:
    import numba.cuda

    if numba.cuda.is_available():
        print("A GPU is available")
        # echo CUDA_VISIBLE_DEVICES
        print(f"CUDA_VISIBLE_DEVICES: {os.environ['CUDA_VISIBLE_DEVICES']}")
    else:
        print("A GPU is not available")
except ModuleNotFoundError:
    print("Numba is not installed")

# print python path
print(f"Python path: {sys.executable}")

# sleep for 1 second
time.sleep(1)

print(f"Finishing at {datetime.datetime.now()}", file=sys.stderr)
