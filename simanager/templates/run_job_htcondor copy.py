# %%
import simanager as sim

# %%
study = sim.SimulationStudy.load_folder("./")

# %%

sim.job_run_slurm(study, time_limit="02:00:00")

# %%

study.print_sim_status()
