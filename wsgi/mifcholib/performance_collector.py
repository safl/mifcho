#!/usr/bin/env python
import collections
import logging
import time
import os

from mifcholib.threadutils import Worker

class PerformanceCollector(Worker):
    """Collects performance measurements each 'sample_rate' seconds."""

    def __init__(self, sample_rate):

        def init_data(stamp, count):
            count -= 1
            if count == 0:
                return [(stamp, 0,0,0)]
            else:
                return [(stamp-count, 0,0,0)] + init_data(stamp, count)

        self.perf_log     = collections.deque(init_data(int(time.time()),300),300)
        self.sample_rate  = sample_rate

        Worker.__init__(self, name="PerformanceCollector")

    def work(self):

                                          # Sample CPU usage now
        (prev_u, prev_s, prev_cu, prev_cs, prev_e) = os.times()
        prev_clock = int(time.time())

        time.sleep(self.sample_rate)      # Wait 'sample_rate' seconds

        clock = int(time.time())          # Sample again to compute utilization
        (u, s, cu, cs, e) = os.times()

        user      = u - prev_u            # Compute CPU utilization
        system    = s - prev_s
        elapsed   = e - prev_e
        cpu_time  = user + system

        cpu_util        = (cpu_time / elapsed)  * 100
        cpu_util_user   = (user / elapsed)      * 100
        cpu_util_system = (system / elapsed)    * 100

        self.perf_log.append((            # Add to performance log
          clock,
          cpu_util,
          cpu_util_user,
          cpu_util_system
        ))

    def log(self):
        """Retrieve the collected data."""

        return self.perf_log
