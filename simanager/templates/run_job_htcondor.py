# %%
import simanager as sim

# %%
study = sim.SimulationStudy.load_folder("./")

# %%

sim.job_run_htcondor(study, time_limit="espresso", request_gpus=False)

# %%

study.print_sim_status()
