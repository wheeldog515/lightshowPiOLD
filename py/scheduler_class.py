import os
import ephem
import time
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from datetime import date
from datetime import time
from datetime import timedelta
import json


class Scheduler:
    def __init__(self, slcobject):
        # Make an observer
        self.slc = slcobject
        self.jobs = []
        self.jobcount = -1
        self.function_mappings = {'lightson': self.slc.lightson,
                                  'lightsoff': self.slc.lightsoff,
                                  'playlist': self.slc.playlist,
                                  'playAll': self.slc.play_all}
        self.myloc = ephem.Observer()
        self.sched = None
        self.configData = None
        self.get_config()
        self.load_config()
        self.start_scheduler()
        self.build_jobs()

    def save_config(self):
        with open(os.environ['SYNCHRONIZED_LIGHTS_HOME'] + '/config/scheduler.cfg', 'w') as outfile:
            json.dump(self.configData, outfile)

    def get_config(self):
        with open(os.environ['SYNCHRONIZED_LIGHTS_HOME'] + '/config/scheduler.cfg') as json_data:
            self.configData = json.load(json_data)

    def load_config(self):
        # Note that lon should be in string format
        self.myloc.lon = str(self.configData['locationData']['lng'])

        # Note that lat should be in string format
        self.myloc.lat = str(self.configData['locationData']['lat'])

        # in meters
        self.myloc.elev = self.configData['locationData']['elev']

        # To get U.S. Naval Astronomical Almanac values, use these settings
        self.myloc.pressure = 0

    def get_values(self, option):
        # set the date before doing any calculations
        ephem.Date(datetime.utcnow())
        self.myloc.date = datetime.utcnow()

        if option == "sunrise":
            self.myloc.horizon = '-0:34'
            return ephem.localtime(self.myloc.next_rising(ephem.Sun()))

        elif option == "noon":
            self.myloc.horizon = '-0:34'
            return ephem.localtime(self.myloc.next_transit(ephem.Sun(), start=sunrise))

        elif option == "sunset":
            self.myloc.horizon = '-0:34'
            return ephem.localtime(self.myloc.next_setting(ephem.Sun()))

        elif option == "light":
            self.myloc.horizon = '-6'  # -6=civil twilight, -12=nautical, -18=astronomical
            return ephem.localtime(self.myloc.next_rising(ephem.Sun(), use_center=True))

        elif option == "dark":
            self.myloc.horizon = '-6'  # -6=civil twilight, -12=nautical, -18=astronomical
            return ephem.localtime(self.myloc.next_setting(ephem.Sun(), use_center=True))

    def start_scheduler(self):
        self.sched = BackgroundScheduler()
        self.sched.start()

    def build_jobs(self):
        j = 0
        temp = {}
        for i in self.configData['schedule']:
            theid = j
            j += 1
            thetype = self.configData['schedule'][i][0]
            theif = self.configData['schedule'][i][1]
            thethen = self.configData['schedule'][i][2]
            theargs = self.configData['schedule'][i][3]
            temp[str(theid)] = [thetype, theif, thethen, theargs]

            if thetype == 'event':
                runtime = self.get_values(theif)
            else:
                test = theif.split(':')
                runtime = datetime.combine(date.today(), time(int(test[0]), int(test[1])))
                if runtime <= datetime.now():
                    runtime = runtime + timedelta(days=1)

            print self.sched.add_job(self.execute_event, 'date', run_date=runtime,
                                     args=[thetype, theid, theif, thethen, theargs], id=str(theid))

        self.configData['schedule'] = temp
        self.save_config()
        self.jobcount = j

    def stop_scheduler(self):
        self.sched.shutdown()

    def add_event(self, thetype, theif, thethen, theargs, theid=-1):
        if thetype == 'event':
            runtime = self.get_values(theif)
        else:
            test = theif.split(':')
            runtime = datetime.combine(date.today(), time(int(test[0]), int(test[1])))
            if runtime <= datetime.now():
                runtime = runtime + timedelta(days=1)
        if theid == -1:
            self.jobcount += 1
            theid = self.jobcount
        self.configData['schedule'][str(theid)] = [thetype, theif, thethen, theargs]
        self.save_config()
        # self.jobs[self.jobcount]=self.sched.add_job(self.executeEvent,'date',run_date=runtime,
        # args=[theid,theif,thethen],id=str(theid))
        print self.sched.add_job(self.execute_event, 'date', run_date=runtime,
                                 args=[thetype, theid, theif, thethen, theargs], id=str(theid))
        return theid

    def execute_event(self, thetype, event_index, theif, thethen, theargs):
        print 'executing ' + theif + ' ' + thethen
        if theargs == '':
            self.function_mappings[thethen]()
        else:
            self.function_mappings[thethen](theargs)
        self.add_event(thetype, theif, thethen, theargs, event_index)

    def remove_event(self, event_index):
        print 'removed '
        print self.configData['schedule']
        del self.configData['schedule'][event_index]
        self.save_config()
        print 'removed '
        print self.sched.remove_job(event_index)
