# %%
import simanager as sim

# %%
study = sim.SimulationStudy.load_folder("./")

# %%

# sim.job_run_local(study, gpu_available_list=[0,1])
sim.job_run_local(study)

# %%

study.print_sim_status()
