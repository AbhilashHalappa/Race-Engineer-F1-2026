"""Race Engineer package."""
__version__ = "2.0.0"

# ACC is an independent telemetry/engineering adapter. Installing this bootstrap
# here keeps the protected F1 runtime files unchanged while allowing the ACC reader
# to feed the existing SpeechOutput channel when ACC is selected.
from . import acc_bootstrap as _acc_bootstrap
