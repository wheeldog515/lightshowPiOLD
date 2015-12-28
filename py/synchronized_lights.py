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
the FFT cacluations are cached after the first time a new song is played.  The values are cached
in a gzip'd text file in the same location as the song itself.  Subsequent requests to play the
same song will use the cached information and not recompute the FFT, thus reducing CPU utilization
dramatically and allowing for clear music playback of all audio file types.

Recent optimizations have improved this dramatically and most users are no longer reporting
adverse playback of songs even on the first playback.

Sample usage:
To play an entire list -
sudo python synchronized_lights.py --playlist=/home/pi/music/.playlist

To play a specific song -
sudo python synchronized_lights.py --file=/home/pi/music/jingle_bells.mp3

Third party dependencies:

alsaaudio: for audio input/output - http://pyalsaaudio.sourceforge.net/
decoder.py: decoding mp3, ogg, wma, ... - https://pypi.python.org/pypi/decoder.py/1.5XB
numpy: for FFT calcuation - http://www.numpy.org/
"""

#import argparse
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

class slc:
# Configurations - TODO(todd): Move more of this into configuration manager
    def loadConfig(self):
        slc._CONFIG = cm.CONFIG
        slc._MODE = cm.lightshow()['mode']
        slc._MIN_FREQUENCY = slc._CONFIG.getfloat('audio_processing', 'min_frequency')
        slc._MAX_FREQUENCY = slc._CONFIG.getfloat('audio_processing', 'max_frequency')
        slc._RANDOMIZE_PLAYLIST = slc._CONFIG.getboolean('lightshow', 'randomize_playlist')
        try:
            slc._CUSTOM_CHANNEL_MAPPING = [int(channel) for channel in
                                   slc_CONFIG.get('audio_processing', 'custom_channel_mapping').split(',')]
        except:
            slc._CUSTOM_CHANNEL_MAPPING = 0
        try:
            slc._CUSTOM_CHANNEL_FREQUENCIES = [int(channel) for channel in
                                       slc._CONFIG.get('audio_processing',
                                                   'custom_channel_frequencies').split(',')]
        except:
            slc._CUSTOM_CHANNEL_FREQUENCIES = 0
        try:
            slc._PLAYLIST_PATH = cm.lightshow()['playlist_path'].replace('$SYNCHRONIZED_LIGHTS_HOME', cm.HOME_DIR)
        except: 
            slc._PLAYLIST_PATH = "/home/pi/music/.playlist"
        try:
            slc.frequency =slc._CONFIG.get('audio_processing','frequency')
            slc._usefm=slc._CONFIG.get('audio_processing','fm')
            slc.play_stereo = True
            slc.music_pipe_r,slc.music_pipe_w = os.pipe()
        except:
            slc._usefm='false'
        slc.CHUNK_SIZE = 2048  # Use a multiple of 8 (move this to config)
        slc.fm_process=0
        slc.port = slc._CONFIG.getint('webui', 'webui_port')

    def setConfig(self,val):
        #decode the json from the web form into a python dict
        obj = json.loads(val)
        
        #iterate over that structure entering each option into the config
        for section in obj:
            for keys in obj[section]:
                slc._CONFIG.set(section,keys,obj[section][keys])
        
        #write changes to the config file to ~/.lights.cfg
        with open(os.path.expanduser('~/.lights.cfg'), 'wb') as configfile:
            slc._CONFIG.write(configfile)
            print configfile  
        
    def set_config_default():
        #delete the ~/.lights.cfg file so that default configuration is not overidden
        #If using the webui manually changes tothe configutation should be made in oerride.cfg
        #leave ~/.lights.cfg for use by the webui; this way
        #this function will delete all changes made by the webui
        os.remove(os.path.expanduser('~/.lights.cfg'))

    def lightson(self):
        hc.turn_on_lights()
        self.current_song_name='none / lights on'
        self.setInits()
		
    def lighton(self,i):
        hc.turn_on_light(i)
        self.current_song_name='none / light(s) on'
        self.setInits()

    def cleanup(self):
        hc.clean_up()
        self.current_song_name='none / lights off'
        self.setInits()

    def lightsoff(self):
        hc.turn_off_lights()
        self.current_song_name='none / lights off'
        self.setInits()
		
    def lightoff(self,i):
        hc.turn_off_light(i)
        self.current_song_name='none / light(s) off'
        self.setInits()

    def getConfig(self):
        results='{'
        sections=self.getSections()
        for i in sections:
            results=results+'"'+i+'":{'
            options=self.getOptions(i)
            for j in options:
                if j == 'preshow_configuration':
                    results=results+'"'+j+'":'+self.get(i,j)+','
                else:
                    results=results+'"'+j+'":"'+self.get(i,j)+'",'
            results=results[:-1]+'},'
        results=results[:-1]+'}'
        return results
		
    def set_config_default(self):
        #delete the ~/.lights.cfg file so that default configuration is not overidden
        #If using the webui manually changes tothe configutation should be made in oerride.cfg
        #leave ~/.lights.cfg for use by the webui; this way
        #this function will delete all changes made by the webui
        os.remove(os.path.expanduser('~/.lights.cfg'))
		
    def getSections(self):
        return slc._CONFIG.sections()

    def getItems(self,section):
        return json.dumps(slc._CONFIG.items(section))

    def get(self,section,option):
        return slc._CONFIG.get(section,option)

    def getOptions(self,section):
        return slc._CONFIG.options(section)

    def calculate_channel_frequency(self,min_frequency, max_frequency, custom_channel_mapping,
                                    custom_channel_frequencies):
        '''Calculate frequency values for each channel, taking into account custom settings.'''
    
        # How many channels do we need to calculate the frequency for
        if custom_channel_mapping != 0 and len(custom_channel_mapping) == hc.GPIOLEN:
            logging.debug("Custom Channel Mapping is being used: %s", str(custom_channel_mapping))
            channel_length = max(custom_channel_mapping)
        else:
            logging.debug("Normal Channel Mapping is being used.")
            channel_length = hc.GPIOLEN
    
        logging.debug("Calculating frequencies for %d channels.", channel_length)
        octaves = (np.log(max_frequency / min_frequency)) / np.log(2)
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
            for i in range(1, hc.GPIOLEN + 1):
                frequency_limits.append(frequency_limits[-1]
                                        * 10 ** (3 / (10 * (1 / octaves_per_channel))))
        for i in range(0, channel_length):
            frequency_store.append((frequency_limits[i], frequency_limits[i + 1]))
            logging.debug("channel %d is %6.2f to %6.2f ", i, frequency_limits[i],
                          frequency_limits[i + 1])
    
        # we have the frequencies now lets map them if custom mapping is defined
        if custom_channel_mapping != 0 and len(custom_channel_mapping) == hc.GPIOLEN:
            frequency_map = []
            for i in range(0, hc.GPIOLEN):
                mapped_channel = custom_channel_mapping[i] - 1
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
    
    def update_lights(self,matrix, mean, std):
        '''Update the state of all the lights based upon the current frequency response matrix'''
        for i in range(0, hc.GPIOLEN):
            # Calculate output pwm, where off is at some portion of the std below
            # the mean and full on is at some portion of the std above the mean.
            brightness = matrix[i] - mean[i] + 0.5 * std[i]
            brightness = brightness / (1.25 * std[i])
            if brightness > 1.0:
                brightness = 1.0
            if brightness < 0:
                brightness = 0
            if not hc.is_pin_pwm(i):
                # If pin is on / off mode we'll turn on at 1/2 brightness
                if (brightness > 0.5):
                    hc.turn_on_light(i, True)
                else:
                    hc.turn_off_light(i, True)
            else:
                hc.turn_on_light(i, True, brightness)

    def audio_in(self):
        """Control the lightshow from audio coming in from a USB audio card"""
		
        self.current_song_name='none / Audio In Mode'
        sample_rate = cm.lightshow()['audio_in_sample_rate']
        input_channels = cm.lightshow()['audio_in_channels']
    
        # Open the input stream from default input device
        stream = aa.PCM(aa.PCM_CAPTURE, aa.PCM_NORMAL, cm.lightshow()['audio_in_card'])
        stream.setchannels(input_channels)
        stream.setformat(aa.PCM_FORMAT_S16_LE) # Expose in config if needed
        stream.setrate(sample_rate)
        stream.setperiodsize(CHUNK_SIZE)
             
        #logging.debug("Running in audio-in mode - will run until Ctrl+C is pressed")
        #print "Running in audio-in mode, use Ctrl+C to stop"
#        try:
        #hc.initialize()
        frequency_limits = calculate_channel_frequency(_MIN_FREQUENCY,
                                                        _MAX_FREQUENCY,
                                                        _CUSTOM_CHANNEL_MAPPING,
                                                        _CUSTOM_CHANNEL_FREQUENCIES)
     
         # Start with these as our initial guesses - will calculate a rolling mean / std 
         # as we get input data.
        mean = [12.0 for _ in range(hc.GPIOLEN)]
        std = [0.5 for _ in range(hc.GPIOLEN)]
        recent_samples = np.empty((250, hc.GPIOLEN))
        num_samples = 0
     
        # Listen on the audio input device until CTRL-C is pressed
        print str(self.AudioIn)
        while self.AudioIn == True:
            test=1		
            print 'in loop'		
            l, data = stream.read()
             
            if l:
                try:
                    matrix = fft.calculate_levels(data,
                                                  CHUNK_SIZE,
                                                  sample_rate,
                                                  frequency_limits,
                                                  hc.GPIOLEN,
                                                  input_channels)
                    if not np.isfinite(np.sum(matrix)):
                        # Bad data --- skip it
                        continue
                except ValueError as e:
                    # TODO(todd): This is most likely occuring due to extra time in calculating
                    # mean/std every 250 samples which causes more to be read than expected the
                    # next time around.  Would be good to update mean/std in separate thread to
                    # avoid this --- but for now, skip it when we run into this error is good 
                    # enough ;)
                    logging.debug("skipping update: " + str(e))
                    continue
     
                update_lights(matrix, mean, std)
     
                # Keep track of the last N samples to compute a running std / mean
                #
                # TODO(todd): Look into using this algorithm to compute this on a per sample basis:
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
 
        hc.turn_on_lights()
        self.setInits()
        self.current_song_name='none / lights on'

    def playAll(self):
        types = ('/home/pi/lightshowpi/music/*.wav', '/home/pi/lightshowpi/music/*.mp3') # the tuple of file types
        self.current_playlist=[]
        for files in types:
            #self.current_playlist.extend(glob.glob(files))
            for file in glob.glob(files):
                self.current_playlist.append([os.path.splitext(os.path.basename(file))[0],file])
        for song in self.current_playlist:        
            # Get random song
            if slc._RANDOMIZE_PLAYLIST:
                self.currentlyplaying=self.current_playlist[random.randint(0, len(self.current_playlist) - 1)][1]
            # Play next song in the lineup
            else:
                self.currentlyplaying=song[1]
            self.playlistplaying=song[0]
            self.play(self.currentlyplaying)
        self.current_playlist=[]

    def playlist(self,playlist):
        with open(playlist, 'rb') as playlist_fp:
            fcntl.lockf(playlist_fp, fcntl.LOCK_SH)
            playlist = csv.reader(playlist_fp, delimiter='\t')

            for song in playlist:
                if len(song) < 2 or len(song) > 4:
                    logging.error('Invalid playlist.  Each line should be in the form: '
                                     '<song name><tab><path to song>')
                elif len(song) == 2:
                    song.append(set())
                else:
                    song[2] = set(song[2].split(','))
                    if len(song) == 3 and len(song[2]) >= len(most_votes[2]):
                        most_votes = song
                self.current_playlist.append(song)
            fcntl.lockf(playlist_fp, fcntl.LOCK_UN)

        for song in self.current_playlist:        
            # Get random song
            if slc._RANDOMIZE_PLAYLIST:
                self.currentlyplaying=self.current_playlist[random.randint(0, len(self.current_playlist) - 1)][1]
            # Play next song in the lineup
            else:
                self.currentlyplaying=song[1]
            self.playlistplaying=song[0]
            self.play(self.currentlyplaying)
        self.current_playlist=[]

    def playSingle(self,song):
        self.current_playlist=[]
        self.current_playlist.append([os.path.splitext(os.path.basename(song))[0],song])
        self.currentlyplaying=self.current_playlist[0][1]
        self.playlistplaying=self.current_playlist[0][0]
        self.play(self.currentlyplaying)
        self.current_playlist=[]

    def play(self,file):
        self.current_song_name='none'
        self.current_position= 0
        self.duration= 0
        song_to_play = int(cm.get_state('song_to_play', 0))
        play_now = int(cm.get_state('play_now', 0))
        readcache='true'

        logging.basicConfig(filename=cm.LOG_DIR + '/music_and_lights.play.dbg',
                            format='[%(asctime)s] %(levelname)s {%(pathname)s:%(lineno)d}'
                            ' - %(message)s',
                            level=logging.DEBUG)
    
        # Make sure one of --playlist or --file was specified
        if file == None:
            print "One of --playlist or --file must be specified"
    
        # Only execute preshow if no specific song has been requested to be played right now
        if not play_now:
            #Preshow.execute_preshow(cm.lightshow()['preshow'])
            Preshow().execute()

        # Get filename to play and store the current song playing in state cfg
        song_filename = file
        self.current_song_name=os.path.splitext(os.path.basename(song_filename))[0]
        song_filename = song_filename.replace("$SYNCHRONIZED_LIGHTS_HOME", cm.HOME_DIR)
    
        # Ensure play_now is reset before beginning playback
        if play_now:
            cm.update_state('play_now', 0)
            play_now = 0
    
        # Initialize FFT stats
        matrix = [0 for _ in range(hc.GPIOLEN)]
    
        # Set up audio
        if song_filename.endswith('.wav'):
            self.musicfile = wave.open(song_filename, 'r')
        else:
            self.musicfile = decoder.open(song_filename)
    
        sample_rate = self.musicfile.getframerate()
        num_channels = self.musicfile.getnchannels()
        self.sr=sample_rate
        self.nc=num_channels
        self.fc=self.musicfile.getnframes()
        self.duration=self.musicfile.getnframes()/self.musicfile.getframerate()

        output = aa.PCM(aa.PCM_PLAYBACK, aa.PCM_NORMAL)
        output.setchannels(num_channels)
        output.setrate(sample_rate)
        output.setformat(aa.PCM_FORMAT_S16_LE)
        output.setperiodsize(slc.CHUNK_SIZE)
        
        logging.info("Playing: " + song_filename + " (" + str(self.musicfile.getnframes() / sample_rate)
                     + " sec)")
        # Output a bit about what we're about to play to the logs
        song_filename = os.path.abspath(song_filename)
        
    
        cache = []
        cache_found = False
        cache_filename = os.path.dirname(song_filename) + "/." + os.path.basename(song_filename) \
            + ".sync.gz"
        # The values 12 and 1.5 are good estimates for first time playing back (i.e. before we have
        # the actual mean and standard deviations calculated for each channel).
        mean = [12.0 for _ in range(hc.GPIOLEN)]
        std = [1.5 for _ in range(hc.GPIOLEN)]
        if readcache:
            # Read in cached fft
            try:
                with gzip.open(cache_filename, 'rb') as playlist_fp:
                    cachefile = csv.reader(playlist_fp, delimiter=',')
                    for row in cachefile:
                        cache.append([0.0 if np.isinf(float(item)) else float(item) for item in row])
                    cache_found = True
                    # TODO(todd): Optimize this and / or cache it to avoid delay here
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
        data = self.musicfile.readframes(slc.CHUNK_SIZE)
        frequency_limits = self.calculate_channel_frequency(slc._MIN_FREQUENCY,
                                                       slc._MAX_FREQUENCY,
                                                       slc._CUSTOM_CHANNEL_MAPPING,
                                                       slc._CUSTOM_CHANNEL_FREQUENCIES)
    
        while data != '' and not play_now:
            if slc._usefm=='true':
                os.write(slc.music_pipe_w, data)
            #else:
            self.audioChunk=data
            output.write(data)
            self.current_position=self.musicfile.tell()/self.musicfile.getframerate()
            # Control lights with cached timing values if they exist
            matrix = None
            if cache_found and readcache:
                if row < len(cache):
                    matrix = cache[row]
                else:
                    logging.warning("Ran out of cached FFT values, will update the cache.")
                    cache_found = False
    
            if matrix == None:
                # No cache - Compute FFT in this chunk, and cache results
                matrix = fft.calculate_levels(data, slc.CHUNK_SIZE, sample_rate, frequency_limits)
                cache.append(matrix)
                
            self.update_lights(matrix, mean, std)
    
            # Read next chunk of data from music song_filename
            data = self.musicfile.readframes(slc.CHUNK_SIZE)
            row = row + 1
    
            # Load new application state in case we've been interrupted
            cm.load_state()
            play_now = int(cm.get_state('play_now', 0))
    
        if not cache_found:
            with gzip.open(cache_filename, 'wb') as playlist_fp:
                writer = csv.writer(playlist_fp, delimiter=',')
                writer.writerows(cache)
                logging.info("Cached sync data written to '." + cache_filename
                             + "' [" + str(len(cache)) + " rows]")

        hc.turn_on_lights()
        self.setInits()
        self.current_song_name='none / lights on'
		
    def setInits(self):
        self.musicfile = 0
        self.duration=0
        self.current_position=0
        self.playlistplaying=''
		
    def run_pifm(self,use_audio_in=False):
	    with open(os.devnull, "w") as dev_null:
		    slc.fm_process = subprocess.Popen(["sudo",cm.HOME_DIR + "/bin/pifm","-",str(slc.frequency),"44100", "stereo" if slc.play_stereo else "mono"], stdin=slc.music_pipe_r, stdout=dev_null)

    def __init__(self):
        self.loadConfig()
        self.current_playlist=[]
        self.current_song_name='none'
        self.audioChunk=0
        self.AudioIn = False
        self.setInits()
        hc.initialize()
        if slc._usefm!='false' and slc.fm_process==0:
            self.run_pifm()
