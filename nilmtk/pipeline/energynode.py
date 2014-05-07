from __future__ import print_function, division
from node import Node
from energyresults import EnergyResults
import numpy as np
from nilmtk.utils import timedelta64_to_secs
from nilmtk.consts import JOULES_PER_KWH
from nilmtk.measurement import AC_TYPES
from nilmtk import TimeFrame
from nilmtk.measurement import Power, Energy


class EnergyNode(Node):

    requirements = {'preprocessing': {'good_sections_located': True}}
    postconditions =  {'preprocessing': {'energy_computed': True}}

    def __init__(self, name='energy'):
        super(EnergyNode, self).__init__(name)

    def process(self, df, metadata):
        """
        Preference: Energy(cumulative) > Energy > Power
        """
        energy = {}
        for timeframe in df.results['good_sections'].last_results:
            energy_for_timeframe = _energy_for_chunk(timeframe.slice(df))
            for ac_type, e_for_ac_type in energy_for_timeframe.iteritems():
                energy[ac_type] = energy.get(ac_type, 0) + e_for_ac_type

        energy_results = EnergyResults()
        energy_results.append(df.timeframe, energy)
        df.results = getattr(df, 'results', {})
        df.results[self.name] = energy_results
        return df

    def required_measurements(self, state):
        """EnergyNode needs all power and energy measurements."""
        available_measurements = state['device']['measurements']
        return [measurement for measurement in available_measurements 
                if isinstance(measurement, (Power, Energy))]


def _energy_for_chunk(df):
    """
    Returns
    -------
    energy : dict
        with a key for each AC type (reactive, apparent, active) in the data.
    """

    energy = {}
    data_source_rank = {} # overwrite Power with Energy with Energy(cumulative)
    for measurement, series in df.iteritems():
        if isinstance(measurement, Power):
            # Preference is to calculate energy from 
            # native Energy data rather than Power data
            # so don't overwrite with Power data.
            if not energy.has_key(measurement.ac_type):
                energy[measurement.ac_type] = _energy_for_power_series(series)
                data_source_rank[measurement.ac_type] = 3 # least favourite
        elif isinstance(measurement, Energy):
            if measurement.cumulative:
                energy[measurement.ac_type] = series.iloc[-1] - series.iloc[0]
                data_source_rank[measurement.ac_type] = 1 # favourite
            elif data_source_rank.get(measurement.ac_type, 3) > 2:
                energy[measurement.ac_type] = series.sum()
                data_source_rank[measurement.ac_type] = 2
    return energy


def _energy_for_power_series(series):
    series = series.dropna()
    timedelta = np.diff(series.index.values)
    timedelta_secs = timedelta64_to_secs(timedelta)
    joules = (timedelta_secs * series.values[:-1]).sum()
    kwh = joules / JOULES_PER_KWH
    return kwh
