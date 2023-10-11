# %%
import simanager as sim

# %%
study = sim.SimulationStudy.load_folder("./")

# %%
study.reset_simulations(
    reset_all=False,
    restore_original=True,
)
