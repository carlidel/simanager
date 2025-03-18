import os
import shutil
import pandas as pd

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


def number_filename_formatter(number, alternative_idx=0, truncate=5):
    """Formats a number to a string with a maximum number of digits."""
    # if the number is an integer, just return it as a string
    if isinstance(number, int):
        return str(number)
    # if instead is a float or something that can be converted to a float...    
    try:
        number = float(number)
        string = "{:.{prec}f}".format(number, prec=truncate)
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


def clean_script_from_templates(data):
    # remove everything above the tag "#___END_INITIAL_INSTRUCTIONS___"
    try:
        data = data.split("#___END_INITIAL_INSTRUCTIONS___")[1]
    except IndexError:
        pass
    # remove everything below the tag "#___BEGIN_FINAL_INSTRUCTIONS___"
    try:
        data = data.split("#___BEGIN_FINAL_INSTRUCTIONS___")[0]
    except IndexError:
        pass
    return data


def flatten_dict(d, parent_key="", sep="/"):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def insert_nested_dict_in_dataframe(df, nested_dict, extra_dict):
    """
    Inserts a flattened nested dictionary and additional key-value pairs into a DataFrame as a new row.
    """
    # Flatten the nested dictionary and merge it with the extra dictionary
    to_write_dict = {**flatten_dict(nested_dict), **extra_dict}

    # Convert the dictionary to a DataFrame with a single row and concatenate
    df_new_row = pd.DataFrame([to_write_dict])
    final_df = pd.concat([df, df_new_row], ignore_index=True)
    return final_df