# !/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Todd Giles (todd@lightshowpi.com)
# Author: Chris Usey (chris.usey@gmail.com)
# Author: Ryan Jennings
# Author: Paul Dunn (dunnsept@gmail.com)
# Author: Tom Enos
"""
Play any audio file and synchronize lights to the music

When executed, this script will play an audio file, as well as turn on
and off N channels of lights to the music (by default the first 8 GPIO
channels on the Raspberry Pi), based upon music it is playing. Many
types of audio files are supported (see decoder.py below), but it has
only been tested with wav, mp3, and flac at the time of this writing.

The timing of the lights turning on and off is based upon the frequency
response of the music being played.  A short segment of the music is
analyzed via FFT to get the frequency response across each defined
channel in the audio range.  Each light channel is then faded in and
out based upon the amplitude of the frequency response in the 
corresponding audio channel.  Fading is accomplished with a software 
PWM output.  Each channel can also be configured to simply turn on and
off as the frequency response in the corresponding channel crosses a 
threshold.

FFT calculation can be CPU intensive and in some cases can adversely
affect playback of songs (especially if attempting to decode the song
as well, as is the case for an mp3).  For this reason, the FFT 
calculations are cached after the first time a new song is played.
The values are cached in a npz archive file in the same location as the
song itself.  Subsequent requests to play the same song will use the
cached information and not recompute the FFT, thus reducing CPU
utilization dramatically and allowing for clear music playback of all
audio file types.

Recent optimizations have improved this dramatically and most users are
no longer reporting adverse playback of songs even on the first 
playback.

Sample usage:
To play an entire list -
sudo python synchronized_lights.py --playlist=/home/pi/music/.playlist

To play a specific song -
sudo python synchronized_lights.py --file=/home/pi/music/jingle_bells.mp3

Third party dependencies:

alsaaudio: for audio input/output 
    http://pyalsaaudio.sourceforge.net/

decoder.py: decoding mp3, ogg, wma, ... 
    https://pypi.python.org/pypi/decoder.py/1.5XB

numpy: for FFT calculation 
    http://www.numpy.org/
"""
import argparse
import atexit
import cPickle
import logging
import os
import psutil
import random
import socket
import subprocess
import sys
import wave

import alsaaudio
import decoder
import fft
import hardware_manager
import numpy

from prepostshow import PrePostShow

class Lightshow(hardware_manager.Hardware):
    """
    Lightshow class
    
    Play any audio file and synchronize lights to the music
    """

    def __init__(self):
        # inherit hardware_manager and configuration_manager
        super(Lightshow, self).__init__()

        self.mode = self.lightshow_config['mode']
        self.playlist_path = self.lightshow_config['playlist_path']
        self.randomize_playlist = self.lightshow_config['randomize_playlist']

        self.chunk_size = self.audio_config['chunk_size']

        self.networking = self.network_config['networking']
        self.port = self.network_config['port']
        
        self.not_pwm = [not pin if pin else not pin for pin in self.is_pin_pwm]
        
        self.usefm = self.audio_config['fm']

        self.song_filename = None
        self.audio_device = None
        self.fm_process = None
        self.stream = None
        self.stop_the_show = False
        self.__initialized = False
        
        self.sound_device()

    def sound_device(self):
        """
        Setup the sound device
        
        Setup the sound device for use in the show
        PiFm
        onboard sound
        or a usb sound card        
        """
        if self.usefm:
            self.fm_frequency = self.audio_config['frequency']
            self.music_pipe_r, self.music_pipe_w = os.pipe()
            logging.info("Sending output as fm transmission")

            with open(os.devnull, "w") as dev_null:
                # start pifm as a separate process 
                # play_stereo is always True as coded, Should it be changed to
                # an option in the config file?
                self.fm_process = subprocess.Popen(["sudo",
                                                    self.HOME_DIR + "/bin/pifm",
                                                    "-",
                                                    str(self.fm_frequency),
                                                    "44100",
                                                    "stereo"],
                                                   stdin=self.music_pipe_r,
                                                   stdout=dev_null)
        elif self.mode == 'audio-in':
            # Open the input stream from default input device
            self.audio_device = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, self.lightshow_config['audio_in_card'])
            self.audio_device.setformat(alsaaudio.PCM_FORMAT_S16_LE)
        else:
            self.audio_device = alsaaudio.PCM(alsaaudio.PCM_PLAYBACK, alsaaudio.PCM_NORMAL)
            self.audio_device.setformat(alsaaudio.PCM_FORMAT_S16_LE)
         
    def update_lights(self, matrix, mean, std):
        """
        Update the state of all the lights

        Update the state of all the lights based upon the current
        frequency response matrix
        :param std: numpy.std()
        :param mean: numpy.mean()
        :param matrix: list of floats
        """
        # broadcast to clients if in server mode
        if self.networking == "server":
            self.broadcast(matrix, mean, std)

        for pin in range(self.gpiolen):
            # Calculate output pwm, where off is at some portion of the std below
            # the mean and full on is at some portion of the std above the mean.
            brightness = (matrix[pin] - mean[pin] + 0.5 * std[pin]) / 1.25 * std[pin]
            brightness = max(0.0, min(1.0, brightness))
            if self.not_pwm[pin]:
                # If pin is on / off mode we'll turn on at 1/2 brightness
                self.turn_on_light(pin, True, float(brightness > 0.5))
            else:
                self.turn_on_light(pin, True, brightness)

    def calculate_channel_frequency(self):
        """
        Calculate frequency values

        Calculate frequency values for each channel,
        taking into account custom settings.
        """
        min_frequency = self.audio_config['min_frequency']
        max_frequency = self.audio_config['max_frequency']
        custom_channel_mapping = self.audio_config['custom_channel_mapping']
        custom_channel_frequencies = self.audio_config['custom_channel_frequencies']

        # How many channels do we need to calculate the frequency for
        if custom_channel_mapping != 0 and len(custom_channel_mapping) == self.gpiolen:
            logging.debug("Custom Channel Mapping is being used: %s", str(custom_channel_mapping))
            channel_length = max(custom_channel_mapping)
        else:
            logging.debug("Normal Channel Mapping is being used.")
            channel_length = self.gpiolen

        logging.debug("Calculating frequencies for %d channels.", channel_length)
        octaves = (numpy.log(max_frequency / min_frequency)) / numpy.log(2)
        logging.debug("octaves in selected frequency range ... %s", octaves)
        octaves_per_channel = octaves / channel_length
        frequency_limits = []
        frequency_store = []

        frequency_limits.append(min_frequency)

        if custom_channel_frequencies != 0 and (len(custom_channel_frequencies) >= channel_length + 1):
            logging.debug("Custom channel frequencies are being used")
            frequency_limits = custom_channel_frequencies
        else:
            logging.debug("Custom channel frequencies are not being used")
            for pin in range(1, self.gpiolen + 1):
                #frequency_limits.append(
                    #frequency_limits[-1] * 2 ** octaves_per_channel)
                frequency_limits.append(frequency_limits[-1]
                                        * 10 ** (3 / (10 * (1 / octaves_per_channel))))
        for pin in range(0, channel_length):
            frequency_store.append((frequency_limits[pin], frequency_limits[pin + 1]))
            logging.debug("channel %d is %6.2f to %6.2f ", pin, frequency_limits[pin],
                        frequency_limits[pin + 1])

        # we have the frequencies now lets map them if custom mapping is defined
        if custom_channel_mapping != 0 and len(custom_channel_mapping) == self.gpiolen:
            frequency_map = []
            for pin in range(0, self.gpiolen):
                mapped_channel = custom_channel_mapping[pin] - 1
                mapped_frequency_set = frequency_store[mapped_channel]
                mapped_frequency_set_low = mapped_frequency_set[0]
                mapped_frequency_set_high = mapped_frequency_set[1]
                logging.debug("mapped channel: " + str(mapped_channel) + " will hold LOW: "
                            + str(mapped_frequency_set_low) + " HIGH: "
                            + str(mapped_frequency_set_high))
                frequency_map.append(mapped_frequency_set)
            return frequency_map
        else:
            return frequency_store
            
    def audio_in(self):
        """Control the lightshow from audio coming in from a USB audio card"""
        sample_rate = self.lightshow_config['audio_in_sample_rate']
        input_channels = self.lightshow_config['audio_in_channels']
        
        half_gpiolen = self.gpiolen / 2
        
        self.audio_device.setchannels(input_channels)
        self.audio_device.setrate(sample_rate)
        self.audio_device.setperiodsize(chunk_size)
        
        if not self.__initialized:
            self.initialize()
            self.__initialized = True

        frequency_limits = calculate_channel_frequency()

        # Start with these as our initial guesses - will calculate a rolling mean / std 
        # as we get input data.
        mean = [12.0 for _ in range(self.gpiolen)]
        std = [0.5 for _ in range(self.gpiolen)]
        recent_samples = numpy.empty((250, self.gpiolen))
        num_samples = 0
        
        logging.debug("Running in audio-in mode - will run until Ctrl+C is pressed")
        print "Running in audio-in mode, use Ctrl+C to stop"
        
        # Listen on the audio input device until CTRL-C is pressed
        try:
            while True:
                length, data = self.audio_device.read()

                if length:
                    try:
                        matrix = fft.calculate_levels(data,
                                                    chunk_size,
                                                    sample_rate,
                                                    frequency_limits,
                                                    self.gpiolen,
                                                    input_channels)
                        if not numpy.isfinite(numpy.sum(matrix)):
                            # Bad data --- skip it
                            continue
                    except ValueError as error:
                        # TODO(todd): This is most likely occuring due to extra time in calculating
                        # mean/std every 250 samples which causes more to be read than expected the
                        # next time around.  Would be good to update mean/std in separate thread to
                        # avoid this --- but for now, skip it when we run into this error is good 
                        # enough ;)
                        logging.debug("skipping update: " + str(error))
                        continue

                    self.update_lights(matrix, mean, std)

                    # Keep track of the last N samples to compute a running std / mean
                    #
                    # TODO(todd): Look into using this algorithm to compute this on a per sample basis:
                    # http://www.johndcook.com/blog/standard_deviation/                
                    if num_samples >= 250:
                        for i in range(0, self.gpiolen):
                            mean[i] = numpy.mean([item for item in recent_samples[:, i] if item > 0])
                            std[i] = numpy.std([item for item in recent_samples[:, i] if item > 0])

                        # Count how many channels are below 10, 
                        # if more than 1/2, assume noise (no connection)
                        # If more than 1/2 of the channels appear to be not connected, turn all off
                        if sum(not_connected < 10.0 for not_connected in mean) > half_gpiolen:
                            logging.debug("no input detected, turning all lights off")
                            mean = [20 for _ in range(self.gpiolen)]
                        else:
                            logging.debug("std: " + str(std) + ", mean: " + str(mean))
                        num_samples = 0
                    else:
                        for i in range(0, self.gpiolen):
                            recent_samples[num_samples][i] = matrix[i]
                        num_samples += 1

        except KeyboardInterrupt:
            pass
        finally:
            print "\nStopping"
            self.clean_up()

    def network_client(self):
        """
        Network client support
        
        If in client mode, ignore everything else and just
        read data from the network and blink the lights
        """
        logging.info("Network client mode starting")
        print "Network client mode starting..."
        try:
            channels = self.network_config['channels']
            self.stream = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.stream.bind(('', self.port))
            
            print "listening on port: " + str(self.port)
            
            logging.info("client channels mapped as\n" + str(channels))
            logging.info("listening on port: " + str(self.port))
        except socket.error, msg:
            logging.error('Failed create socket or bind. Error code: ' + 
                          str(msg[0]) + ' : ' + msg[1])
            self.stream.close()
            sys.exit(0)
            
        print "press CTRL<C> to end"
        self.initialize()
        print
        song = "Waiting for data"
        try:
            while True:
                temp = False
                data = None
                
                try:
                    sys.stdout.write("\rReceiving data for: %s" % (song))
                    sys.stdout.flush()
                    data, address = self.stream.recvfrom(4096)
                    data = cPickle.loads(data)

                    if len(data) == 1:
                        song = data[0].split("/")[-1]
                        logging.info("playing " + data[0])
                        continue
                    elif len(data) == 2:
                        pins = [data[0]]
                        brightness = float(data[1])
                        temp = True
                    elif len(data) == 3:
                            matrix = data[0]
                            mean = data[1]
                            std = data[2]
                            pins = [_ for _ in range(self.gpiolen)]
                    else:
                        continue
                except (IndexError, cPickle.PickleError):
                    matrix = std = mean = [0 for _ in range(self.gpiolen)]
                
                if not isinstance(pins, list):
                    pins = [_ for _ in range(self.gpiolen)]
                    matrix = std = mean = [0 for _ in range(self.gpiolen)]
                
                for pin in pins:
                    if not temp:
                        brightness = (matrix[pin] - mean[pin] + 0.5 * std[pin]) / 1.25 * std[pin]
                        brightness = max(0.0, min(1.0, brightness))
                        
                    if pin in channels.keys():
                        if channels[pin] < 0:
                            continue
                        for channel in channels[pin]:
                            if self.not_pwm[channel]:
                                self.turn_on_light(channel,True, float(brightness > 0.5))
                            else:
                                self.turn_on_light(channel, True, brightness)
        except KeyboardInterrupt:
            logging.info("CTRL<C> pressed, stopping")
            print "stopping"
            self.stream.close()

    def next_song(self):
        """
        Get the next song to play from the playlist
        """
        song_to_play = int(self.get_state('song_to_play', 0))
        play_now = int(self.get_state('play_now', 0))
        self.song_filename = args.file

        if args.playlist is not None and args.file is None:
            most_votes = [None, None, []]

            # read playlist from file
            playlist = self.songs(args.playlist)
            songs = []
            for song in playlist:
                if len(song) == 2:
                    song.append(set())
                else:
                    song[2] = set(song[2].split(','))
                    if len(song) == 3 and len(song[2]) >= len(most_votes[2]):
                        most_votes = song
                songs.append(song)

            if most_votes[0] is not None:
                logging.info("Most Votes: " + str(most_votes))
                current_song = most_votes

                for song in songs:
                    if current_song == song and len(song) == 3:
                        song.append("playing!")
                    if len(song[2]) > 0:
                        song[2] = ",".join(song[2])
                    else:
                        del song[2]
                self.update_songs(args.playlist, songs)
            else:
                # Get a "play now" requested song
                if 0 < play_now <= len(songs):
                    current_song = songs[play_now - 1]

                # Get random song
                elif self.randomize_playlist:
                    # Use python's random.randrange() to get a random song
                    current_song = songs[random.randrange(len(songs))]

                # Play next song in the lineup
                else:
                    if song_to_play <= len(songs) - 1:
                        song_to_play = song_to_play
                    else:
                        song_to_play = 0

                    current_song = songs[song_to_play]

                    if (song_to_play + 1) <= len(songs) - 1:
                        next_song_to_play = (song_to_play + 1)
                    else:
                        next_song_to_play = 0

                    self.update_state('song_to_play', next_song_to_play)

            # Get filename to play and store the current song playing in state cfg
            self.song_filename = current_song[1]
            self.update_state('current_song', songs.index(current_song))

        self.song_filename.replace("$SYNCHRONIZED_LIGHTS_HOME", self.HOME_DIR)

    def set_up_audio(self):
        """
        Set up the audio output device(s)
        """
        if self.song_filename.endswith('.wav'):
            self.music_file = wave.open(self.song_filename, 'r')
        else:
            self.music_file = decoder.open(self.song_filename)

        self.sample_rate = self.music_file.getframerate()
        self.num_channels = self.music_file.getnchannels()

        # set audio playback device
        if isinstance(self.audio_device, alsaaudio.PCM):
            self.audio_device.setchannels(self.num_channels)
            self.audio_device.setrate(self.sample_rate)
            self.audio_device.setperiodsize(self.chunk_size)

        # Output a bit about what we're about to play to the logs
        self.song_filename = os.path.abspath(self.song_filename)
        logging.info(
            "Playing: " + self.song_filename + " (" + str(self.music_file.getnframes() / self.sample_rate) + " sec)")

    def per_song(self):
        """
        Load the configuration for the audio file if it exists
        set variables for playback hear and in the hardware_manager
        """
        # Get configuration for song playback
        per_song_config_filename = self.song_filename + ".cfg"
        if os.path.isfile(per_song_config_filename):
            logging.info("loading custom configuration for " + per_song_config_filename)
            
            self.per_song_config(per_song_config_filename)
            self.load_config()

    def read_cache(self):
        """
        Read sync file and validate cached data matches the loaded
        configuration
        """
        # Cached data filename
        self.cache_found = False
        self.cache_filename = os.path.dirname(self.song_filename) + "/." + os.path.basename(
                                            self.song_filename) + ".sync.npz"
        # create empty array for the cache_matrix
        self.cache_matrix = list()
        
        # The values 12 and 1.5 are good estimates for first time playing back 
        # (i.e. before we have the actual mean and standard deviations 
        # calculated for each channel).
        self.mean = [12.0 for _ in range(self.gpiolen)]
        self.std = [1.5 for _ in range(self.gpiolen)]

        try:
            # load cache from file
            cache_arrays = numpy.load(self.cache_filename)

            # get the current configuration to compare to
            # what is stored in the cached array
            show_configuration = numpy.array([[self.gpiolen],
                                        [self.sample_rate],
                                        [self.audio_config['min_frequency']],
                                        [self.audio_config['max_frequency']],
                                        [self.audio_config['custom_channel_mapping']],
                                        [self.audio_config['custom_channel_frequencies']],
                                        [self.chunk_size],
                                        [self.num_channels]], dtype=object)

            # cached hardware configuration from sync file
            cached_configuration = cache_arrays["cached_configuration"]

            # Compare current config to cached config
            if (show_configuration == cached_configuration).all():
                self.cache_found = True
                self.std = cache_arrays["std"].tolist()
                self.mean = cache_arrays["mean"].tolist()
                self.cache_matrix = cache_arrays["cache_matrix"].tolist()

            if self.cache_found:
                logging.debug("std: " + str(self.std) + ", mean: " + str(self.mean))
            else:
                logging.warn('Cached configuration does not match current configuration.  '
                            'Generating new cache file with current show configuration')
        except IOError:
            logging.warn("Cached sync data song_filename not found: '"
                         + self.cache_filename + "'.  One will be generated.")

    def playback(self, song=None):
        """
        Playback the audio and trigger the lights
        
        Process audio song_filename
        """
        play_now = int(self.get_state('play_now', 0))

        row = 0
        counter = 0
        percentage = 0
        frequency_limits = self.calculate_channel_frequency()
        total_frames = self.music_file.getnframes() / 100
        cache_len = len(self.cache_matrix)

        data = self.music_file.readframes(self.chunk_size)
        
        while data != '' and not play_now:
            if self.fm_process and not args.createcache:
                os.write(self.music_pipe_w, data)
            if self.audio_device and not args.createcache:
                self.audio_device.write(data)

            # Control lights with cached timing values if they exist
            matrix = None
            if self.cache_found and args.readcache:
                if row < cache_len:
                    matrix = self.cache_matrix[row]
                else:
                    logging.warning("Ran out of cached FFT values, will update the cache.")
                    self.cache_found = False

            if matrix is None:
                # No cache - Compute FFT in this chunk, and cache results
                matrix = fft.calculate_levels(data, self.chunk_size, self.sample_rate, frequency_limits, self.gpiolen)

                # Add the matrix to the end of the cache 
                self.cache_matrix.append(matrix)
                
            # Load new application state in case we've been interrupted and
            # update the lights
            if not args.createcache:
                if self.networking == "server":
                    self.broadcast(matrix, self.mean, self.std)

                for pin in range(self.gpiolen):
                    # Calculate output pwm, where off is at some portion of the std below
                    # the mean and full on is at some portion of the std above the mean.
                    brightness = (matrix[pin] - self.mean[pin] + 0.5 * self.std[pin]) / 1.25 * self.std[pin]
                    brightness = max(0.0, min(1.0, brightness))
                    if self.not_pwm[pin]:
                        # If pin is on / off mode we'll turn on at 1/2 brightness
                        self.turn_on_light(pin, True, float(brightness > 0.5))
                    else:
                        self.turn_on_light(pin, True, brightness)
                
                self.load_state()
                play_now = int(self.get_state('play_now', 0))
            else:
                if counter > total_frames:
                    percentage += 1
                    counter = 0
        
                counter += self.chunk_size
                sys.stdout.write("\rGenerating sync file for :%s %d%%" % (song, percentage))
                sys.stdout.flush()
                
            # Read next chunk of data from music song_filename
            data = self.music_file.readframes(self.chunk_size)
            row += 1
            
        # make sure lame ends
        for proc in psutil.process_iter():
            if proc.name() == "lame":
                proc.kill()
        
    def save_matrix(self):
        """
        Save the data necessary for playback so that it will not need to
        be calculated again
        """
        cache_matrix = numpy.array(self.cache_matrix)
        
        show_configuration = numpy.array([[self.gpiolen],
                                    [self.sample_rate],
                                    [self.audio_config['min_frequency']],
                                    [self.audio_config['max_frequency']],
                                    [self.audio_config['custom_channel_mapping']],
                                    [self.audio_config['custom_channel_frequencies']],
                                    [self.chunk_size],
                                    [self.num_channels]], dtype=object)

        # Compute the standard deviation and mean values for the cache
        mean = [0 for _ in range(self.gpiolen)]
        std = [0 for _ in range(self.gpiolen)]
        for i in range(self.gpiolen):
            std[i] = numpy.std([item for item in cache_matrix[:, i] if item > 0])
            mean[i] = numpy.mean([item for item in cache_matrix[:, i] if item > 0])

        # Save the cache
        numpy.savez(self.cache_filename,
                cache_matrix=cache_matrix,
                mean=mean,
                std=std,
                cached_configuration=show_configuration)
        
        logging.info("Cached sync data written to '." + self.cache_filename
                    + "' [" + str(len(cache_matrix)) + " rows]")

    def create_cache(self, items):
        """
        Create sync file(s) for a single file or a playlist

        :param items: string or list of strings, a playlist or filename
        """
        self.cache_found = False
        a_types = [".mp3", ".mp4", ".m4a", ".m4b", ".aac", ".ogg", ".flac", ".wma", ".wav"]

        if os.path.splitext(os.path.basename(items))[1] in a_types:
            playlist = [items]
        else:
            playlist = list()
            with open(items, 'r') as playlist_items:
                for line in playlist_items:
                    try:
                        temp = line.strip().split('\t')[1]
                        if os.path.isfile(temp):
                            playlist.append(temp)
                    except IOError:
                        pass

        for song in playlist:
            self.cache_matrix = list()
            self.mean = [12.0 for _ in range(self.gpiolen)]
            self.std = [1.5 for _ in range(self.gpiolen)]
            
            logging.info("Generating sync file for :" + song)
            
            self.song_filename = song
            self.per_song()

            if song.endswith('.wav'):
                self.music_file = wave.open(song, 'r')
            else:
                self.music_file = decoder.open(song)

            self.sample_rate = self.music_file.getframerate()
            self.num_channels = self.music_file.getnchannels()
            
            self.cache_filename = os.path.dirname(song) + "/." + os.path.basename(song) + ".sync.npz"
            self.playback(song)

            self.save_matrix()
            
            sys.stdout.write("\rSync file generated for  :%s %d%%" % (song, 100))
            sys.stdout.write("\n")
            sys.stdout.flush()

            logging.info("Sync file generated for :" + song)

    def stop(self):
        """
        Stop the show
        
        Not implemented yet
        """
        self.stop = True

    def play_song(self):
        """
        Play the next song from the play list (or --file argument).
        """
        # Initialize Lights
        if not self.__initialized:
            self.initialize()
            self.__initialized = True

        play_now = int(self.get_state('play_now', 0))

        self.cache_found = False
        self.cache_matrix = list()
        self.std = [12.0 for _ in range(self.gpiolen)]
        self.mean = [1.5 for _ in range(self.gpiolen)]

        # Handle the pre/post show
        self.unset_playing()
        if not play_now:
            result = PrePostShow('preshow', self).execute()
            if result == PrePostShow.play_now_interrupt:
                play_now = int(self.get_state('play_now', 0))
        self.set_playing()

        # Determine the next file to play
        self.next_song()

        # Ensure play_now is reset before beginning playback
        if play_now:
            self.update_state('play_now', 0)

        # Set up audio from file
        self.set_up_audio()

        # Get configuration for song playback
        self.per_song()

        # Read in cached fft data if it exists
        if args.readcache:
            self.read_cache()

        # send song file name to clients for logging
        if self.networking == 'server':        
            self.broadcast(self.song_filename)

        # Process audio song_filename and playback
        self.playback()

        # save the sync file if needed
        if not self.cache_found:
            # Save the cache matrix, std, mean and the show_configuration variables
            # that matter in the fft calculation to a sync file for future playback
            self.save_matrix()

        # check for postshow
        self.unset_playing()
        PrePostShow('postshow', self).execute()


#@atexit.register
def on_exit(lightshow):
    """
    Preform these actions on exit
    """    
    lightshow.unset_playing()
    lightshow.clean_up()
    
    if lightshow.stream:
        lightshow.stream.close()
    
    # Cleanup the pifm process
    if lightshow.usefm:
        lightshow.fm_process.kill()


if __name__ == "__main__":
    # logging levels
    levels = {'DEBUG': logging.DEBUG,
              'INFO': logging.INFO,
              'WARNING': logging.WARNING,
              'ERROR': logging.ERROR,
              'CRITICAL': logging.CRITICAL}
    
    level = logging.INFO
    for item in sys.argv:
        if "log" in item.lower():
            idx = sys.argv.index(item)
            if sys.argv[idx].lower().endswith("log"):
                level = levels[sys.argv[idx + 1].upper()]
            elif "log" in sys.argv[idx]:
                level = levels[sys.argv[idx].split('=')[-1].upper()]
                
    # create default logger, level = INFO
    logging.basicConfig(filename=hardware_manager.configuration_manager.LOG_DIR + '/music_and_lights.play.dbg',
                        format='[%(asctime)s] %(levelname)s {%(pathname)s:%(lineno)d}'
                               ' - %(message)s',
                        level='INFO')
    # parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--log', default='INFO',
                        help='Set the logging level. levels:INFO, DEBUG, WARNING, ERROR, CRITICAL')
    cachegroup = parser.add_mutually_exclusive_group()
    cachegroup.add_argument('--readcache', type=bool, default=True,
                            help='read light timing from cache if available. Default: true')
    cachegroup.add_argument('--createcache', action="store_true",
                            help='create light timing cache without audio playback or lightshow.')
    filegroup = parser.add_mutually_exclusive_group()
    filegroup.add_argument('--playlist', default='playlist_path',
                           help='Playlist to choose song from.')
    filegroup.add_argument('--file', help='path to the song to play (required if no'
                                          'playlist is designated)')

    if parser.parse_args().createcache:
        parser.set_defaults(readcache=False)

     # Log to our log file at the specified level
    level = levels.get(parser.parse_args().log.upper())
    logging.getLogger().setLevel(level)

    # lightshow instance
    lightshow = Lightshow()
    if parser.parse_args().playlist == 'playlist_path':
        parser.set_defaults(playlist=lightshow.playlist_path)

    args = parser.parse_args()
    atexit.register(on_exit, lightshow)

    if lightshow.mode == 'audio-in':
        audio_in()
    elif lightshow.networking == "client":
        lightshow.network_client()
    else:
        # Check if we are generating sync file(s) or playing a show
        if args.createcache:
            lightshow.create_cache(args.file or args.playlist)
            sys.exit(0)
        else:
            try:
                lightshow.play_song()
            except KeyboardInterrupt:
                pass
            
    on_exit(lightshow)
