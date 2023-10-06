# %%
import simanager as sim

# %%
study = sim.SimulationStudy.load_folder("./")

# %%
study.initialize_folders()

# %%
study.print_sim_status()

# %%
sim.job_run_slurm(study, time_limit="00:10:00", request_gpus=False)

# %%
study.print_sim_status()
