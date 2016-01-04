#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Todd Giles (todd@lightshowpi.com)
"""FFT methods for computing / analyzing frequency response of audio.

These are simply wrappers around FFT support of numpy.

Third party dependencies:

numpy: for FFT calculation - http://www.numpy.org/
"""

import hardware_controller as hc
import numpy as np
from numpy import array

piff_array = None
window = list()


def calculate_levels(data, chunk_size, sample_rate, frequency_limits, channels=2):
    """Calculate frequency response for each channel defined in frequency_limits

    Initial FFT code inspired from the code posted here:
    http://www.raspberrypi.org/phpBB3/viewtopic.php?t=35838&p=454041

    Optimizations from work by Scott Driscoll:
    http://www.instructables.com/id/Raspberry-Pi-Spectrum-Analyzer-with-RGB-LED-Strip-/
    """
    peakMax = 16384.0
    peaks = array([0, 0])

    global piff_array, window

    if piff_array is None:
        fl = np.array(frequency_limits)
        piff_array = ((fl * chunk_size) / sample_rate).astype(int)

        for a in range(len(piff_array)):
            if piff_array[a][0] == piff_array[a][1]:
                piff_array[a][1] += 1

    # create a numpy array, taking just the left channel if stereo
    data_stereo = np.frombuffer(data, dtype=np.int16)
    if channels == 2:
        data = array(data_stereo[::2])  # pull out the even values, just using left channel
        right = array(data_stereo[1::2])
        peaks[0] = abs(max(data)-1)/4 + abs(min(data)+1)/4
        peaks[1] = abs(max(right)-1)/4 + abs(min(right)+1)/4
    elif channels == 1:
        data = data_stereo
        peaks[0] = abs(max(data)-1)/4 +abs(min(data)+1)/4
        peaks[1] = peaks[0]

    peaks = peaks / peakMax 

    # if you take an FFT of a chunk of audio, the edges will look like
    # super high frequency cutoffs. Applying a window tapers the edges
    # of each end of the chunk down to zero.
    if len(data) != len(window):
        window = np.hanning(len(data))

    data = data * window

    # Apply FFT - real data
    fourier = np.fft.rfft(data)

    # Remove last element in array to make it the same size as chunk_size
    fourier = np.delete(fourier, len(fourier) - 1)

    # Calculate the power spectrum
    power = np.abs(fourier) ** 2

    cache_matrix = np.empty(hc.GPIOLEN, dtype='float32')

    for pin in range(hc.GPIOLEN):
        # Get the sum of the power array index corresponding to a
        # particular frequency.
        cache_matrix[pin] = np.sum(power[piff_array[pin][0]:piff_array[pin][1]])

    # take the log10 of the resulting sum to approximate how human ears
    # perceive sound levels
    if all(cache_matrix == 0.0):
        return cache_matrix, peaks

    with np.errstate(divide='ignore'):
        cache_matrix = np.where(cache_matrix > 0.0, np.log10(cache_matrix), 0)

    return cache_matrix, peaks
