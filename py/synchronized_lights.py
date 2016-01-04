#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Todd Giles (todd@lightshowpi.com)
# Author: Chris Usey (chris.usey@gmail.com)
# Author: Ryan Jennings
# Author: Paul Dunn (dunnsept@gmail.com)
# Author: Stephen Burning
"""Play any audio file and synchronize lights to the music

When executed, this script will play an audio file, as well as turn on and off N channels
of lights to the music (by default the first 8 GPIO channels on the Rasberry Pi), based upon
music it is playing. Many types of audio files are supported (see decoder.py below), but
it has only been tested with wav and mp3 at the time of this writing.

The timing of the lights turning on and off is based upon the frequency response of the music
being played.  A short segment of the music is analyzed via FFT to get the frequency response
across each defined channel in the audio range.  Each light channel is then faded in and out based
upon the amplitude of the frequency response in the corresponding audio channel.  Fading is 
accomplished with a software PWM output.  Each channel can also be configured to simply turn on
and off as the frequency response in the corresponding channel crosses a threshold.

FFT calculation can be CPU intensive and in some cases can adversely affect playback of songs
(especially if attempting to decode the song as well, as is the case for an mp3).  For this reason,
the FFT calculations are cached after the first time a new song is played.  The values are cached
in a gzip'd text file in the same location as the song itself.  Subsequent requests to play the
same song will use the cached information and not recompute the FFT, thus reducing CPU utilization
dramatically and allowing for clear music playback of all audio file types.

Recent optimizations have improved this dramatically and most users are no longer reporting
adverse playback of songs even on the first playback.

Third party dependencies:

alsaaudio: for audio input/output - http://pyalsaaudio.sourceforge.net/
decoder.py: decoding mp3, ogg, wma, ... - https://pypi.python.org/pypi/decoder.py/1.5XB
numpy: for FFT calculations - http://www.numpy.org/
"""

import csv
import fcntl
import gzip
import json
import logging
import os
import random
import subprocess
import sys
import wave
import glob
import alsaaudio as aa
import fft
import configuration_manager as cm
import decoder
import hardware_controller as hc
import numpy as np

from preshow import Preshow


class SynchronizedLights:

    def __init__(self):
        print 'init started'
        self.CUSTOM_CHANNEL_MAPPING = 0
        self.CUSTOM_CHANNEL_FREQUENCIES = 0
        self.currentlyplaying = None
        self.playlistplaying = None
        self.musicfile = None
        self.sr = 0
        self.nc = 0
        self.fc = 0
        self.duration = 0
        self.current_position = 0
        self.fm_process = None
        self.CONFIG = None
        self.MODE = None
        self.MIN_FREQUENCY = None
        self.MAX_FREQUENCY = None
        self.RANDOMIZE_PLAYLIST = None
        self.frequency = None
        self.usefm = False
        self.play_stereo = True
        self.music_pipe_r, self.music_pipe_w = os.pipe()
        self.PLAYLIST_PATH = None

        self.CHUNK_SIZE = 2048  # Use a multiple of 8 (move this to config)
        self.fm_process = None
        self.port = None

        self.load_config()
        self.current_playlist = []
        self.current_song_name = 'none'
        self.audioChunk = 0
        self.AudioIn = False
        self.set_inits()
        hc.initialize()
        if self.usefm and not self.fm_process:
            self.run_pifm()
        print 'init done'

    # Configurations - Move more of this into configuration manager
    def load_config(self):
        print 'load config started'
        self.CONFIG = cm.CONFIG
        self.MODE = cm.lightshow()['mode']
        self.MIN_FREQUENCY = self.CONFIG.getfloat('audio_processing', 'min_frequency')
        self.MAX_FREQUENCY = self.CONFIG.getfloat('audio_processing', 'max_frequency')
        self.RANDOMIZE_PLAYLIST = self.CONFIG.getboolean('lightshow', 'randomize_playlist')

        if self.CONFIG.get('audio_processing', 'custom_channel_mapping') != "-1":
            self.CUSTOM_CHANNEL_MAPPING = [int(channel) for channel in
                                           self.CONFIG.get('audio_processing',
                                                           'custom_channel_mapping').split(',')]

        if self.CONFIG.get('audio_processing', 'custom_channel_frequencies') != "-1":
            self.CUSTOM_CHANNEL_FREQUENCIES = [int(channel) for channel in
                                               self.CONFIG.get('audio_processing',
                                                               'custom_channel_frequencies').split(
                                                   ',')]

        self.PLAYLIST_PATH = cm.lightshow()['playlist_path'].replace(
            '$SYNCHRONIZED_LIGHTS_HOME', cm.HOME_DIR)

        self.frequency = self.CONFIG.get('audio_processing', 'frequency')
        self.usefm = self.CONFIG.getboolean('audio_processing', 'fm')
        self.play_stereo = True
        self.music_pipe_r, self.music_pipe_w = os.pipe()

        self.CHUNK_SIZE = 2048  # Use a multiple of 8 (move this to config)
        self.fm_process = None
        self.port = self.CONFIG.getint('webui', 'webui_port')
        print 'load config done'

    def set_config(self, val):
        # decode the json from the web form into a python dict
        obj = json.loads(val)

        # iterate over that structure entering each option into the config
        for section in obj:
            for keys in obj[section]:
                self.CONFIG.set(section, keys, obj[section][keys])

        # write changes to the config file to ~/.lights.cfg
        with open(os.path.expanduser('~/.lights.cfg'), 'wb') as configfile:
            self.CONFIG.write(configfile)
            print configfile

    @staticmethod
    def set_config_default():
        # delete the ~/.lights.cfg file so that default configuration is not overidden
        # If using the webui manually changes tothe configutation should be made in oerride.cfg
        # leave ~/.lights.cfg for use by the webui; this way
        # this function will delete all changes made by the webui
        os.remove(os.path.expanduser('~/.lights.cfg'))

    def lightson(self):
        hc.turn_on_lights()
        self.current_song_name = 'none / lights on'
        self.set_inits()

    def lighton(self, i):
        hc.turn_on_light(i)
        self.current_song_name = 'none / light(s) on'
        self.set_inits()

    def cleanup(self):
        hc.clean_up()
        self.current_song_name = 'none / lights off'
        self.set_inits()

    def lightsoff(self):
        hc.turn_off_lights()
        self.current_song_name = 'none / lights off'
        self.set_inits()

    def lightoff(self, i):
        hc.turn_off_light(i)
        self.current_song_name = 'none / light(s) off'
        self.set_inits()

    def get_config(self):
        results = '{'
        sections = self.get_sections()

        for i in sections:
            results = results + '"' + i + '":{'
            options = self.get_options(i)

            for j in options:
                if j == 'preshow_configuration':
                    results = results + '"' + j + '":' + self.get(i, j) + ','
                else:
                    results = results + '"' + j + '":"' + self.get(i, j) + '",'

            results = results[:-1] + '},'

        results = results[:-1] + '}'

        return results

    def get_sections(self):
        return self.CONFIG.sections()

    def get_items(self, section):
        return json.dumps(self.CONFIG.items(section))

    def get(self, section, option):
        return self.CONFIG.get(section, option)

    def get_options(self, section):
        return self.CONFIG.options(section)

    @staticmethod
    def calculate_channel_frequency(min_frequency, max_frequency, custom_channel_mapping,
                                    custom_channel_frequencies):
        """Calculate frequency values for each channel, taking into account custom settings."""
        logging.debug("Normal Channel Mapping is being used.")
        channel_length = hc.GPIOLEN

        logging.debug("Calculating frequencies for %d channels.", channel_length)
        octaves = (np.log(max_frequency / min_frequency)) / np.log(2)
        logging.debug("octaves in selected frequency range ... %s", octaves)
        octaves_per_channel = octaves / channel_length
        frequency_limits = []
        frequency_store = []

        frequency_limits.append(min_frequency)
        logging.debug("Custom channel frequencies are not being used")
        for i in range(1, hc.GPIOLEN + 1):
            frequency_limits.append(frequency_limits[-1] * 10 ** (3 / (10 * (1 / octaves_per_channel))))
        
        for i in range(0, channel_length):
            frequency_store.append((frequency_limits[i], frequency_limits[i + 1]))
            logging.debug("channel %d is %6.2f to %6.2f ", i, frequency_limits[i], frequency_limits[i + 1])

        return frequency_store

    @staticmethod
    def update_lights(matrix, mean, std, peaks):
        """Update the state of all the lights based upon the current frequency response matrix"""
        brightness = matrix - mean + (std * 0.5)
        brightness = brightness / (std * 1.25)

        # ensure that the brightness levels are in the correct range
        brightness = np.clip(brightness, 0.0, 1.0)
        brightness = np.round(brightness, decimals=3)
       
        bass = False
        if brightness[0] > 0.5:
            bass = True
        if brightness[1] > 0.8:
            bass = True
 
        hc.set_levels(brightness, peaks, bass)

    def audio_in(self):
        """Control the lightshow from audio coming in from a USB audio card"""

        self.current_song_name = 'none / Audio In Mode'
        sample_rate = cm.lightshow()['audio_in_sample_rate']
        input_channels = cm.lightshow()['audio_in_channels']

        # Open the input stream from default input device
        stream = aa.PCM(aa.PCM_CAPTURE, aa.PCM_NORMAL, cm.lightshow()['audio_in_card'])
        stream.setchannels(input_channels)
        stream.setformat(aa.PCM_FORMAT_S16_LE)  # Expose in config if needed
        stream.setrate(sample_rate)
        stream.setperiodsize(CHUNK_SIZE)

        # logging.debug("Running in audio-in mode - will run until Ctrl+C is pressed")
        # print "Running in audio-in mode, use Ctrl+C to stop"
        #        try:
        # hc.initialize()
        frequency_limits = calculate_channel_frequency(MIN_FREQUENCY,
                                                       MAX_FREQUENCY,
                                                       CUSTOM_CHANNEL_MAPPING,
                                                       CUSTOM_CHANNEL_FREQUENCIES)

        # Start with these as our initial guesses - will calculate a rolling mean / std
        # as we get input data.
        mean = [12.0 for _ in range(hc.GPIOLEN)]
        std = [0.5 for _ in range(hc.GPIOLEN)]
        recent_samples = np.empty((250, hc.GPIOLEN))
        num_samples = 0

        # Listen on the audio input device until CTRL-C is pressed

        while self.AudioIn:
            l, data = stream.read()

            if l:
                try:
                    matrix, peaks = fft.calculate_levels(data,
                                                  CHUNK_SIZE,
                                                  sample_rate,
                                                  frequency_limits,
                                                  input_channels)
                    if not np.isfinite(np.sum(matrix)):
                        # Bad data --- skip it
                        continue
                except ValueError as e:
                    # This is most likely occuring due to extra time in calculating
                    # mean/std every 250 samples which causes more to be read than expected the
                    # next time around.  Would be good to update mean/std in separate thread to
                    # avoid this --- but for now, skip it when we run into this error is good 
                    # enough ;)
                    logging.debug("skipping update: " + str(e))
                    continue

                update_lights(matrix, mean, std, peaks)

                # Keep track of the last N samples to compute a running std / mean
                #
                # Look into using this algorithm to compute this on a per sample basis:
                # http://www.johndcook.com/blog/standard_deviation/                
                if num_samples >= 250:
                    no_connection_ct = 0
                    for i in range(0, hc.GPIOLEN):
                        mean[i] = np.mean([item for item in recent_samples[:, i] if item > 0])
                        std[i] = np.std([item for item in recent_samples[:, i] if item > 0])

                        # Count how many channels are below 10, 
                        # if more than 1/2, assume noise (no connection)
                        if mean[i] < 10.0:
                            no_connection_ct += 1

                    # If more than 1/2 of the channels appear to be not connected, turn all off
                    if no_connection_ct > hc.GPIOLEN / 2:
                        logging.debug("no input detected, turning all lights off")
                        mean = [20 for _ in range(hc.GPIOLEN)]
                    else:
                        logging.debug("std: " + str(std) + ", mean: " + str(mean))
                    num_samples = 0
                else:
                    for i in range(0, hc.GPIOLEN):
                        recent_samples[num_samples][i] = matrix[i]
                    num_samples += 1

        self.lightsoff()

    def play_all(self):
        types = ('/home/pi/lightshowpi/music/*.wav',
                 '/home/pi/lightshowpi/music/*.mp3')  # the tuple of file types

        self.current_playlist = []

        for files in types:
            for mfile in glob.glob(files):
                self.current_playlist.append([os.path.splitext(os.path.basename(mfile))[0], mfile])

        for song in self.current_playlist:
            # Get random song
            if self.RANDOMIZE_PLAYLIST:
                self.currentlyplaying = \
                    self.current_playlist[random.randint(0, len(self.current_playlist) - 1)][1]
            # Play next song in the lineup
            else:
                self.currentlyplaying = song[1]

            self.playlistplaying = song[0]
            self.play(self.currentlyplaying)

        self.current_playlist = []

    def playlist(self, playlist):
        with open(playlist, 'rb') as playlist_fp:
            fcntl.lockf(playlist_fp, fcntl.LOCK_SH)
            playlist = csv.reader(playlist_fp, delimiter='\t')

            for song in playlist:
                if len(song) < 2 or len(song) > 4:
                    logging.error('Invalid playlist.  Each line should be in the form: '
                                  '<song name><tab><path to song>')
                elif len(song) == 2:
                    song.append(set())

                self.current_playlist.append(song)

            fcntl.lockf(playlist_fp, fcntl.LOCK_UN)

        for song in self.current_playlist:
            # Get random song
            if self.RANDOMIZE_PLAYLIST:
                self.currentlyplaying = \
                    self.current_playlist[random.randint(0, len(self.current_playlist) - 1)][1]
            # Play next song in the lineup
            else:
                self.currentlyplaying = song[1]

            self.playlistplaying = song[0]
            self.play(self.currentlyplaying)

        self.current_playlist = []

    def play_single(self, song):
        self.current_playlist = []
        self.current_playlist.append([os.path.splitext(os.path.basename(song))[0], song])
        self.currentlyplaying = self.current_playlist[0][1]
        self.playlistplaying = self.current_playlist[0][0]
        self.play(self.currentlyplaying)
        self.current_playlist = []

    def play(self, mfile):
        self.current_song_name = 'none'
        self.current_position = 0
        self.duration = 0

        logging.basicConfig(filename=cm.LOG_DIR + '/music_and_lights.play.dbg',
                            format='[%(asctime)s] %(levelname)s {%(pathname)s:%(lineno)d}'
                                   ' - %(message)s',
                            level=logging.DEBUG)

        # Make sure file was specified
        if mfile is None:
            print "File must be specified"

        # Execute preshow
#        Preshow().execute()

        # Get filename to play and store the current song playing in state cfg
        song_filename = mfile
        self.current_song_name = os.path.splitext(os.path.basename(song_filename))[0]
        song_filename = song_filename.replace("$SYNCHRONIZED_LIGHTS_HOME", cm.HOME_DIR)

        # Set up audio
        if song_filename.endswith('.wav'):
            self.musicfile = wave.open(song_filename, 'r')
        else:
            self.musicfile = decoder.open(song_filename)

        sample_rate = self.musicfile.getframerate()
        num_channels = self.musicfile.getnchannels()
        self.sr = sample_rate
        self.nc = num_channels
        self.fc = self.musicfile.getnframes()
        self.duration = self.musicfile.getnframes() / self.musicfile.getframerate()

        output = aa.PCM(aa.PCM_PLAYBACK, aa.PCM_NORMAL)
        output.setchannels(num_channels)
        output.setrate(sample_rate)
        output.setformat(aa.PCM_FORMAT_S16_LE)
        output.setperiodsize(self.CHUNK_SIZE)

        logging.info(
            "Playing: " + song_filename + " (" + str(self.musicfile.getnframes() / sample_rate)
            + " sec)")
        # Output a bit about what we're about to play to the logs
        song_filename = os.path.abspath(song_filename)

        cache = []
        cache_found = False
        cache_filename = os.path.dirname(song_filename) + "/." + os.path.basename(song_filename) \
            + ".sync.gz"
        # The values 12 and 1.5 are good estimates for first time playing back (i.e. before we have
        # the actual mean and standard deviations calculated for each channel).
        mean = np.array([12.0 for _ in range(hc.GPIOLEN)])
        std = np.array([1.5 for _ in range(hc.GPIOLEN)])
        try:
            with gzip.open(cache_filename, 'rb') as playlist_fp:
                cachefile = csv.reader(playlist_fp, delimiter=',')
                for row in cachefile:
                    cache.append(
                        [0.0 if np.isinf(float(item)) else float(item) for item in row])
                cache_found = True
                # Optimize this and / or cache it to avoid delay here
                cache_matrix = np.array(cache)
                for i in range(0, hc.GPIOLEN):
                    std[i] = np.std([item for item in cache_matrix[:, i] if item > 0])
                    mean[i] = np.mean([item for item in cache_matrix[:, i] if item > 0])
                logging.debug("std: " + str(std) + ", mean: " + str(mean))
        except IOError:
            logging.warn("Cached sync data song_filename not found: '" + cache_filename
                         + ".  One will be generated.")

        # Process audio song_filename
        row = 0
        data = self.musicfile.readframes(self.CHUNK_SIZE)
        frequency_limits = self.calculate_channel_frequency(self.MIN_FREQUENCY,
                                                            self.MAX_FREQUENCY,
                                                            self.CUSTOM_CHANNEL_MAPPING,
                                                            self.CUSTOM_CHANNEL_FREQUENCIES)

        while data != '':
            if self.usefm:
                os.write(self.music_pipe_w, data)
            else:
                output.write(data)

            self.audioChunk = data
            self.current_position = self.musicfile.tell() / self.musicfile.getframerate()

            # Control lights with cached timing values if they exist
            matrix = None
            if cache_found:
                if row < len(cache):
                    matrix = cache[row]
                else:
                    logging.warning("Ran out of cached FFT values, will update the cache.")
                    cache_found = False

            if matrix is None:
                # No cache - Compute FFT in this chunk, and cache results
                matrix, peaks = fft.calculate_levels(data, self.CHUNK_SIZE, sample_rate, frequency_limits)
                cache.append(matrix)

            self.update_lights(matrix, mean, std, peaks)

            # Read next chunk of data from music song_filename
            data = self.musicfile.readframes(self.CHUNK_SIZE)
            row += 1

        if not cache_found:
            with gzip.open(cache_filename, 'wb') as playlist_fp:
                writer = csv.writer(playlist_fp, delimiter=',')
                writer.writerows(cache)
                logging.info("Cached sync data written to '.%s' [%s rows]" % (cache_filename,
                                                                              str(len(cache))))

        self.lightsoff()

    def set_inits(self):
        self.musicfile = 0
        self.duration = 0
        self.current_position = 0
        self.playlistplaying = ''

    def run_pifm(self):
        with open(os.devnull, "w") as dev_null:
            self.fm_process = subprocess.Popen(
                ["sudo",
                 cm.HOME_DIR + "/bin/pifm",
                 "-",
                 str(self.frequency),
                 "44100",
                 "stereo" if self.play_stereo else "mono"],
                stdin=self.music_pipe_r,
                stdout=dev_null)
