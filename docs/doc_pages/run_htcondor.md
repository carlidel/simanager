# Running on HTCondor

## Introduction

Launching stuff on HTCondor is always an adventure. A painful adventure. One of these kind of adventures that you would rather avoid, but you know that you will have to face sooner or later.

One would expect coherence, stability, and a certain degree of predictability from an HPC system, but HTCondor is not like that. HTCondor is a beast. A mighty and misterious beast that you have to tame, and that will bite you multiple times before you can even start to think that you are in control. And then set you on fire.

A bit like a cat. A cat that can set you on fire. And that can also fly. So, a dragon. HTCondor is like the Winged Dragon of Ra. Therefore, in order to tame it, we need to sing a song to it. A song that will make it happy, and that will make it want to help us. A song that will make it want to fly.

(Verse)  
Ra, the sun, our guiding light,  
In HPC's realm, we take flight.  
Python code, to you we send,  
With your blessing, may it ascend.  

(Chorus)  
Ra, Ra, radiant one,  
Guide our code till the work is done.  
In this HPC domain, your grace we seek,  
Speed our simulations, make them peak.  

(Verse)  
As we submit and scripts take form,  
Grant us favor, keep us warm.  
May our jobs, like sunbeams, shine,  
In your brilliance, may they align.  

(Chorus)  
Ra, Ra, radiant one,  
Guide our code till the work is done.  
In this HPC domain, your grace we seek,  
Speed our simulations, make them peak.  

(Verse)  
In the sacred space of computation's might,  
Watch over us, day and night.  
When the simulations reach their end,  
To you, Ra, our thanks we send.  

(Chorus)  
Ra, Ra, radiant one,  
Guide our code till the work is done.  
In this HPC domain, your grace we seek,  
Speed our simulations, make them peak.  

(~Made with ChatGPT 3.5)

## "Ideal" HTCondor setup (as of today)

The following is a summary of the things that I expect to have in place to have a "perfect" HTCondor setup. This is based on my experience with HTCondor, and it is not exhaustive. It is just a summary of the things and assumptions around which I based the development of the ```simanager``` package.

When I want to run a Python based simulation on HTCondor, I expect to have the following things well configured:

* **The usage of a CVMFS environment**, which will be used as base to run the simulation. For example, I now always construct my simulations around a LCG release, which contain, among various compilers and software amenities, a full-fledged scientific Python installation (N.B., it is the one that SWAN uses!).
  * **Consistency with the binary release**, every LCG release is built against a specific version of the OS, and it is expected to be run on that version of the OS. As of today, the entire CERN computing environment is slowly moving to AlmaLinux 9, therefore, that version should be used (and we will see how containers can help us with that).
  * **Carefulness with picking CUDA and non-CUDA flavours**, the LCG releases are built with and without CUDA support, and the two versions are not fully interchangeable, and the CUDA version can cause issues if run on a machine without CUDA support. Therefore, it is important to be careful when picking the right version.
  * **Example of a CVMFS environment**: 
``` bash
# Example of a good standard CVMFS environment for modern Python
source /cvmfs/sft.cern.ch/lcg/views/LCG_104a/x86_64-el9-gcc11-opt/setup.sh
# CUDA version for GPU simulations
source /cvmfs/sft.cern.ch/lcg/views/LCG_104a_cuda/x86_64-el9-gcc11-opt/setup.sh
```
* **A Python ```venv``` built from CVMFS in AFS**. In order to be able to install my own packages, while also benefitting from the standard scientific distribution available in the LCG view, and avoid clogging my AFS space, I use Python virtual environments with the ```--system-site-packages``` option on, while having sourced the LCG view I want to be based on. This way, I can compose my personal Python environment with libraries under development. The process to compose such environment looks like this:
    ```bash
    # WHILE ON lxplus9 IN ORDER TO USE AlmaLinux 9
    # source the LCG view
    source /cvmfs/sft.cern.ch/lcg/views/LCG_104a/x86_64-el9-gcc11-opt/setup.sh
    # cd into the project folder where you want to create the venv
    cd /afs/cern.ch/work/c/camontan/public/my_project
    # create the venv
    python3 -m venv --system-site-packages project_venv
    # activate the venv
    source project_venv/bin/activate
    # install the packages you need
    pip install xsuite
    # install the packages you are developing
    pip install -e /afs/cern.ch/work/c/camontan/public/fantasy_circular_collider
    ```
    It is necessary to execute this process on a machine with AlmaLinux 9, in order to avoid mismatching binaries shenanigans. This is why I always use lxplus9 for this!!!
    
    In 90% of cases, this environment will work also with the CUDA version of the LCG view, but it is not guaranteed... Be careful and make an offer to the mighty Ra before trying to run anything too fancy.

* **Render unto EOS what is EOS's. Render unto AFS what is AFS's.** As of today, a standard HTCondor job is only able to "freely" access AFS directories (as long as AFS is not kicking the bucket with too warm sectors in the shared filesystem), while EOS can not be accessed directly, but it requires instead a stage-in/stage-out approach. A "robust" should therefore follow these good/must practices:
  * Ideally, transfer everything immediately on the scratch disk by means of the submit file;
  * Perform only read operations on AFS directories, never write directly on AFS;
  * Have a well-defined list of files to be read from EOS, and transfer them to the scratch disk by means of a standard method such as ```eos cp``` or ```xrdcp```;
  * At the end of the job, transfer the output files from the scratch disk to EOS by means of a standard method such as ```eos cp```, ```xrdcp```, or well-defined instructions in the submit file;


With all of these "simple" rules and guidelines in place, you will easily understand the crooked structure and logic of the ```job_run_htcondor``` function, as well as the various arguments that it can take.

Right now, the structure of the function **forces** you to follow these guidelines... I would have loved to make it more flexible, but the second I tried, I started to have very intense nightmares of never-ending queues of jobs that would crash over and over and over and **over again**. And while it is true that one must imagine Sisyphus happy, I would rather not be Sisyphus in the first place.

## The ```job_run_htcondor``` function

The ```job_run_htcondor``` function runs a given ```SimulationStudy``` on HTCondor. It can be easily run by means of the CLI command ```simanager run_htcondor```, or by importing it in a Python script and calling it directly. If the CLI command is used, a ```run_config.yaml``` can be used to store easily the arguments of the function, and avoid having to type them every time. Refer to the ```study_template``` folder for a simple example of a ```run_config.yaml``` file.

When launched with default specialization instructions, the function will undergo the following steps:

* Specialize all main scripts in the parameter scan folders with default initial and final instructions specialized for a HTCondror flavoured job (inspect ```simanager/job_run_htcondor.py``` for more details);
* Compose the submit file for the job, the list of folders to queue, and a EOS stage in support script in a ```htcondor_support``` folder. The submit file will make use of the ```MY.WantOS``` flag and ensure that the job will **always** run on AlmaLinux 9, either by means of bare metal installation or by means of containers (100% resource usage with this method!!);
* Launch the jobs;
* The jobs will then be executed on HTCondor! 
  * The desired CVMFS environment and venv will be loaded;
  * The automatic stage in script will detect the presence of EOS based paths in the various configuration files, and will stage in the necessary files from EOS to the scratch disk; 
  * The main script will then be executed;
  * The output, expected to be either a .pkl or a .hdf5 file (Want more? Feel free to extend the final instruction default!), will be automatically transferred to the desired EOS path, with the simulation case name appended to the file name.
  * A symbolic link to the output file on EOS will be created in the folder of the simulation case on AFS.

For more details on the various arguments of the function, refer to the docstring of the ```job_run_htcondor``` function in ```simanager/job_run_htcondor.py```.

## Extra CLI feature: easily cat the out and err files

From within the directory of the ```simulation_study.yaml```, you can run the command ```simanager cat-out``` and ```simanager cat-err``` to have automatically printed on terminal the content of the out and err files of the various jobs, which by default are placed into... an ```out``` and ```err``` folder!

This is extremely useful to quickly check the status of your jobs that just died, and to see on the fly how the almighty Ra is blessing your simulations by setting them on fire in yet another creative way that you would have never imagined.