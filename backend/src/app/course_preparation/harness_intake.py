"""Compatibility imports; the shared adapter now covers research and planning."""
from .harness_adapter import (HarnessPreparationAdapter as HarnessIntakeAdapter,
                              PreparationTools as IntakeTools,
                              preparation_patch as intake_patch)
