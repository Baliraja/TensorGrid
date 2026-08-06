export DESIGN_NICKNAME = integration_final
export DESIGN_NAME = integration_final
export PLATFORM = gf180

export VERILOG_FILES = $(DESIGN_HOME)/gf180/integration_final/integration_final_synth.v

export SDC_FILE = $(DESIGN_HOME)/$(PLATFORM)/$(DESIGN_NICKNAME)/constraint.sdc

export CORE_UTILIZATION = 45
export PLACE_DENSITY_LB_ADDON = 0.1
