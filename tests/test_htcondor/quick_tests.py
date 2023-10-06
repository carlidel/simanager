# %%
import simanager as sim

# %%
study = sim.SimulationStudy.load_folder("./")

# %%
study.initialize_folders()

# %%
study.print_sim_status()

# %%
sim.job_run_htcondor(study, time_limit="espresso", request_gpus=False)

# %%
study.print_sim_status()
