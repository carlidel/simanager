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
