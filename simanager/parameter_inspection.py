from dataclasses import dataclass

import numpy as np
import yaml


@dataclass
class ParameterInspection:
    """ParameterInspection class defines a parameter or a combination of
    parameters to be varied in a simulation study.

    Parameters
    ----------
    parameter_name : str
        Name of the parameter to be varied. Must be a parameter name contained
        in the YAML master file. The naming convention for nested parameters is
        `parent_parameter/child_parameter`.
    inspection_method : str
        Method to be used for parameter inspection. Must be one of the following:
        - range: Inspect the parameter by means of np.arange.
        - linspace: Inspect the parameter by means of np.linspace.
        - logspace: Inspect the parameter by means of np.logspace.
        - custom: Inspect the parameter by means of a custom list of values.
    min_value : float, optional
        Minimum value of the parameter to be inspected. Must be specified if
        inspection_method is range, linspace, or logspace.
    max_value : float, optional
        Maximum value of the parameter to be inspected. Must be specified if
        inspection_method is range, linspace, or logspace.
    n_samples : int, optional
        Number of samples to be inspected. Must be specified if inspection_method
        is linspace or logspace.
    values : list, optional
        List of values to be inspected. Must be specified if inspection_method
        is custom.
    combination_idx : int, optional
        Index of the parameter if one wants to combine it with other parameter
        scans. If combination_idx is -1, the parameter is not combined with
        other parameter scans.
    combination_method : str, optional
        Method to be used for parameter combination. Must be one of the following:
        - meshgrid: Combine the parameter with other parameter scans by means of
            np.meshgrid.
        - individual: Combine the parameter with other parameter scans as if they
            were combined with a zip function.
    parameter_file_name : str, optional
        Name of the parameter to be used when composing the folder name of the
        simulation. If None, the parameter_name is used.
    force_type : str, optional
        Force the type of the parameter to be inspected. Must be one of the
        following:
        - int: Force the parameter to be an integer.
        - float: Force the parameter to be a float.
        - bool: Force the parameter to be a boolean.
        - str: Force the parameter to be a string.
        If None, the type of the parameter is not forced. By default None.
    """

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
    force_type: str = None

    @classmethod
    def from_dict(cls, dictionary):
        return cls(**dictionary)

    @classmethod
    def from_yaml(cls, yaml_path: str):
        with open(yaml_path, "r", encoding="utf-8") as f:
            dictionary = yaml.safe_load(f)
        return cls.from_dict(dictionary)

    def __post_init__(self):
        if self.inspection_method == "range":
            if not (self.min_value is not None and self.max_value is not None):
                raise ValueError(
                    "If inspection_method is range, min_value and max_value must be specified."
                )
            self.values = list(np.arange(self.min_value, self.max_value))
            self.values = [self._force_type(v, int) for v in self.values]
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
            self.values = [self._force_type(v, float) for v in self.values]
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
            self.values = [self._force_type(v, float) for v in self.values]
        elif self.inspection_method == "custom":
            if not self.values is not None:
                raise ValueError(
                    "If inspection_method is custom, values must be specified."
                )

        if self.parameter_file_name is None:
            self.parameter_file_name = self.parameter_name

    def _force_type(self, value, default):
        if self.force_type == "int":
            return int(value)
        elif self.force_type == "float":
            return float(value)
        elif self.force_type == "bool":
            return bool(value)
        elif self.force_type == "str":
            return str(value)
        else:
            return default(value)
