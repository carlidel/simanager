import os
import shutil


def clone_folder_content(source_folder, destination_folder):
    """
    Clones the content of a folder to another folder.
    """
    for item in os.listdir(source_folder):
        source_path = os.path.join(source_folder, item)
        destination_path = os.path.join(destination_folder, item)
        if os.path.isdir(source_path):
            shutil.copytree(source_path, destination_path)
        else:
            shutil.copy2(source_path, destination_path)


def float_filename_fomratter(float_number, alternative_idx=0, truncate=3):
    """Formats a float number to a string with a maximum number of digits."""
    try:
        string = "{:.{prec}}".format(float(float_number), prec=truncate)
    # if the float_number is not a float, use the alternative_idx
    except TypeError:
        string = str(alternative_idx)
    except ValueError:
        string = str(alternative_idx)
    string = string.replace(".", "d")
    return string


def update_nested_dict(nested_dict, key_chain, value):
    """
    Updates a nested dictionary with a value given a chain of keys.

    Parameters
    ----------
    nested_dict
        The nested dictionary to update.
    key_chain : str
        The chain of keys to access the value to update.
    value
        The value to update.

    Raises
    ------
    KeyError
        If the key is not found in the dictionary.
    """
    keys = key_chain.split("/")
    current_dict = nested_dict
    for key in keys[:-1]:
        if key not in current_dict:
            raise KeyError(f"Key '{key}' not found in dictionary")
        current_dict = current_dict[key]
        if not isinstance(current_dict, dict):
            raise ValueError(f"Key '{key}' is not a dictionary")
    current_dict[keys[-1]] = value


# Define a custom representer for integers
def int_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:int", str(data))


# Define a custom representer for floats
def float_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:float", format(data))


# Define a custom representer for NumPy numerical types
def numpy_scalar_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:float", format(float(data)))
