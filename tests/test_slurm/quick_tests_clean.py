# %%
import simanager as sim

# %%
study = sim.SimulationStudy.load_folder("./")
# %%
study.print_sim_status()

# %%

study.reset_simulations(
    reset_all=True,
    restore_original=True,
    clear_out_folder=True,
    clear_err_folder=True,
    clear_log_folder=True,
)

# %%
study.print_sim_status()
