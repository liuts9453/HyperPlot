"""
Compatibility entry point for the HyperPlot backend.

Existing scripts can keep using:

    import HyperPlot
    hp = HyperPlot.HyperPlot()

The implementation lives in the ``hyperplot`` package.
"""

from hyperplot import *  # noqa: F401,F403
