# %%
import simanager as sim

# %%
study = sim.SimulationStudy.load_folder("./")
# %%
study.print_sim_status()
