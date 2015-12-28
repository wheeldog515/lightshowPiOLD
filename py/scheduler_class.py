import os
import ephem
import time
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from datetime import date
from datetime import time
from datetime import timedelta
import json


class scheduler:
    def saveConfig(self):
        with open(os.environ['SYNCHRONIZED_LIGHTS_HOME']+'/config/scheduler.cfg', 'w') as outfile:
            json.dump(self.configData, outfile)

    def getConfig(self):
        with open(os.environ['SYNCHRONIZED_LIGHTS_HOME']+'/config/scheduler.cfg') as json_data_file:
            self.configData = json.load(json_data_file)

    def loadConfig(self):
        #myloc.lon  = str(-66.666667) #Note that lon should be in string format
        self.myloc.lon  = str(self.configData['locationData']['lng']) #Note that lon should be in string format
        #myloc.lat  = str(45.95)      #Note that lat should be in string format
        self.myloc.lat  = str(self.configData['locationData']['lat'])      #Note that lat should be in string format
        
        self.myloc.elev = self.configData['locationData']['elev']  #in meters
        
        #To get U.S. Naval Astronomical Almanac values, use these settings
        self.myloc.pressure= 0
        #self.myloc.horizon = '-0:34'

    def getValues(self,option):
        ephem.Date(datetime.utcnow())  #set the date before doing any calculations
        #self.myloc.date=datetime.now()
        self.myloc.date=datetime.utcnow()
        if option=="sunrise":
            self.myloc.horizon = '-0:34'
            return ephem.localtime(self.myloc.next_rising(ephem.Sun()))
        elif option=="noon":
            self.myloc.horizon = '-0:34'
            return ephem.localtime(self.myloc.next_transit(ephem.Sun(), start=sunrise))
        elif option=="sunset":
            self.myloc.horizon = '-0:34'
            #return str(ephem.localtime(self.myloc.next_setting(ephem.Sun())))
            return ephem.localtime(self.myloc.next_setting(ephem.Sun()))
        elif option=="light":
            self.myloc.horizon = '-6' #-6=civil twilight, -12=nautical, -18=astronomical
            return ephem.localtime(self.myloc.next_rising(ephem.Sun(), use_center=True))
        elif option=="dark":
            self.myloc.horizon = '-6' #-6=civil twilight, -12=nautical, -18=astronomical
            #return str(ephem.localtime(self.myloc.next_setting(ephem.Sun(), use_center=True)))
            return ephem.localtime(self.myloc.next_setting(ephem.Sun(), use_center=True))

    def getvaluetest(self):
        print self.getValues('sunrise');
        return self.getValues('sunrise');
        
		
    def startScheduler(self):
        self.sched=BackgroundScheduler()
        self.sched.start()
		
    def buildJobs(self):
        j=0
        temp={}
        for i in self.configData['schedule']:
            #theid=self.configData['schedule'][i][2]
            theid=j
            j=j+1
            thetype=self.configData['schedule'][i][0]
            theif=self.configData['schedule'][i][1]
            thethen=self.configData['schedule'][i][2]
            theargs=self.configData['schedule'][i][3]
            temp[str(theid)]= [thetype,theif,thethen,theargs]
            #print thetype
            #print theif
            #print thethen
            if thetype=='event':
                runtime=self.getValues(theif)
            else:
                test=theif.split(':');
                runtime=datetime.combine(date.today(), time(int(test[0]),int(test[1])))
                if runtime <=datetime.now():
                    runtime=runtime + timedelta(days=1)

            print self.sched.add_job(self.executeEvent,'date',run_date=runtime,args=[thetype,theid,theif,thethen,theargs],id=str(theid))

        self.configData['schedule']=temp
        self.saveConfig()
        self.jobcount=j
		
    def stopScheduler(self):
        self.sched.shutdown()
		
    def addEvent(self,thetype,theif,thethen,theargs,theid=-1):
        if thetype=='event':
            runtime=self.getValues(theif)
        else:
            test=theif.split(':');
            runtime=datetime.combine(date.today(), time(int(test[0]),int(test[1])))
            if runtime <=datetime.now():
                runtime=runtime + timedelta(days=1)
        if theid==-1:
            self.jobcount=self.jobcount+1
            theid=self.jobcount
        self.configData['schedule'][str(theid)]= [thetype,theif,thethen,theargs]
        self.saveConfig()
        #self.jobs[self.jobcount]=self.sched.add_job(self.executeEvent,'date',run_date=runtime,args=[theid,theif,thethen],id=str(theid))
        print self.sched.add_job(self.executeEvent,'date',run_date=runtime,args=[thetype,theid,theif,thethen,theargs],id=str(theid))
        return theid
		
    def executeEvent(self,thetype,eventIndex,theif,thethen,theargs):
        print 'executing '+theif+ ' ' + thethen
        if theargs =='':
            self.function_mappings[thethen]()
        else:
            self.function_mappings[thethen](theargs)
        self.addEvent(thetype,theif,thethen,theargs,eventIndex)
		
    def removeEvent(self,eventIndex):
        print 'removed '
        print self.configData['schedule']
        del self.configData['schedule'][eventIndex]
        self.saveConfig()
        print 'removed '
        print self.sched.remove_job(eventIndex)
		
    def __init__(self,slcobject):
        #Make an observer
        self.slc=slcobject
        self.jobs=[]
        self.jobcount=-1
        self.function_mappings = {
        'lightson': self.slc.lightson,
		'lightsoff':self.slc.lightsoff,
		'playlist':self.slc.playlist,
		'playAll':self.slc.playAll}
        self.myloc = ephem.Observer()
        self.getConfig()
        self.loadConfig()
        self.startScheduler()
        self.buildJobs()	

		
#x=scheduler()
#for i in range(0,1):
#    print x.getValues("sunrise")	
#    print x.getValues("sunset")	
#    print x.getValues("light")	
#    print x.getValues("dark")	
#    print x.getValues("sunrise")	
#    print x.getValues("sunset")	
#    time.sleep(1)