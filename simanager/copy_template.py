import os

import pkg_resources

from .tools import clone_folder_content


def copy_template(destination_dir=".", folder_name="sim_study"):
    """Copy the template files to the specified destination directory.

    Parameters
    ----------
    destination_dir : str
        The directory to copy the template files to. Defaults to the current
        working directory.
    """
    templates_dir = pkg_resources.resource_filename("simanager", "templates")
    destination_dir = os.path.abspath(destination_dir)

    os.makedirs(os.path.join(destination_dir, folder_name), exist_ok=True)

    # Copy the template files to the specified destination directory
    clone_folder_content(templates_dir, os.path.join(destination_dir, folder_name))
