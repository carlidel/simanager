# %%
import simanager as sim

# %%
study = sim.SimulationStudy.load_folder("./")

# %%
study.initialize_folders()

# %%
study.print_sim_status()
