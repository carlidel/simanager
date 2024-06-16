import argparse
import datetime
import os
import pickle
import sys
import time

import h5py
import yaml

parser = argparse.ArgumentParser()
parser.add_argument("--yaml_path", type=str, required=True)

args = parser.parse_args()

# open the yaml file
with open(args.yaml_path, "r", encoding="utf-8") as f:
    yaml_dict = yaml.safe_load(f)

# MUST : SAVE ALL OUTPUT FILES IN A FOLDER CALLED "output_files"
os.makedirs("output_files", exist_ok=True)
OUTPATH = "./output_files/"

### START CUSTOM CODE ###

print("Hello world!")
