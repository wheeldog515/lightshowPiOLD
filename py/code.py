#!/usr/bin/env python


import web
import glob
import os
import synchronized_lights as lights
import json
import scheduler_class as scheduler


template_dir = os.path.abspath(os.path.dirname(__file__)) + "/templates"
slc = lights.slc()
sch = scheduler.scheduler(slc)
env = os.environ['SYNCHRONIZED_LIGHTS_HOME']

urls = ('/', 'index',
        '/index.html', 'index',
        '/favicon.ico', 'favicon',
        '/app.manifest', 'hello',
        '/ajax', 'ajax',
        '/getvars', 'getVars',
        '/upload', 'upload',
        '/scheduler', 'sched',
        '/music', 'music',
        '/(js|css|img)/(.*)', 'static')

render = web.template.render(template_dir, cache=True, globals={'glob': glob, 'os': os, 'sch': sch})


class index:
    def GET(self):
        return render.index()


class hello:
    def GET(self):
        web.header('Content-Type', 'text/cache-manifest')
        rmod = "r"

        f = open(os.environ['SYNCHRONIZED_LIGHTS_HOME'] + '/py/static/app.manifest', rmod)

        try:
            stream = f.read()

            return stream
        except:
            f.close()

            return '404 Not Found'


class static:
    def GET(self, media, fn):
        rmod = "r"

        if fn.endswith(".png"):
            rmod = "rb"

        f = open(os.environ['SYNCHRONIZED_LIGHTS_HOME'] + '/py/static/' + media + '/' + fn, rmod)

        try:
            stream = f.read()

            return stream
        except:
            f.close()

            return '404 Not Found'


class favicon:
    def GET(self):
        f = open(os.environ['SYNCHRONIZED_LIGHTS_HOME'] + "/py/static/favicon.ico", 'rb')

        return f.read()


class music:
    def POST(self):
        web.header('Content-Type', 'application/json')

        return '{"sr":' + str(slc.sr) + ',"nc":' + str(slc.nc) + ',"fc":' + str(slc.fc) + '}'

    def GET(self):
        return slc.thedata


class ajax:
    def GET(self):
        var = web.input()

        if var.option == '0':
            web.header('Content-Type', 'application/json')

            return json.dumps(sch.configData['schedule'])

        elif var.option == '1':
            return slc.audioChunkNumber

    def POST(self):
        vars = web.input()

        if vars.option == '0':
            slc.playlist(vars.playlist)

        elif vars.option == '1':
            slc.playSingle(vars.song)

        elif vars.option == '3':
            slc.lightson()

        elif vars.option == '4':
            slc.lightsoff()

        elif vars.option == 'lightOn':
            # turn on a light
            slc.lighton(int(vars.port))

        elif vars.option == 'lightOff':
            # turn off a light
            slc.lightoff(int(vars.port))

        elif vars.option == '5':
            web.header('Content-Type', 'application/json')

            return slc.getConfig()

        elif vars.option == '6':
            slc.setConfig(vars.object)

        elif vars.option == '7':
            slc.playAll()

        elif vars.option == '8':
            web.header('Content-Type', 'application/json')
            str1 = '{"songs":['

            for file in glob.glob(env + "/music/*.mp3"):
                str1 = str1 + '["' + os.path.basename(file) + '","' + file + '"],'

            for file in glob.glob(env + "/music/*.wav"):
                str1 = str1 + '["' + os.path.basename(file) + '","' + file + '"],'

            str1 = str1[:-1]
            str1 = str1 + ']}'

            return str1

        elif vars.option == '9':
            web.header('Content-Type', 'application/json')

            file = open(env + "/music/playlists/" + vars.name + ".playlist", "w")
            file.write(vars.val)
            file.close()

            str1 = '{"playlists":['

            for file in glob.glob(env + "/music/playlists/*.playlist"):
                str1 = str1 + '["' + os.path.basename(file) + '","' + file + '"],'

            str1 = str1[:-1]
            str1 = str1 + ']}'

            return str1

        elif vars.option == '10':
            web.header('Content-Type', 'application/json')

            if hasattr(vars, 'playlist'):
                os.remove(vars.playlist)

            str1 = '{"playlists":['

            for file in glob.glob(env + "/music/playlists/*.playlist"):
                str1 = str1 + '["' + os.path.basename(file) + '","' + file + '"],'

            str1 = str1[:-1]
            str1 = str1 + ']}'

            return str1

        elif vars.option == '11':
            slc.set_config_default()

        elif vars.option == '12':
            app.stop()
            os.system("sudo shutdown -h now")

        elif vars.option == '13':
            app.stop()
            os.system("sudo shutdown -r now")

        elif vars.option == '14':
            return slc.audioChunk

        elif vars.option == '15':
            web.header('Content-Type', 'application/json')

            return json.dumps(sch.configData['schedule'])

        elif vars.option == '16':
            if slc.AudioIn == True:
                slc.AudioIn = False

            else:
                slc.AudioIn = True
                slc.audio_in()


class getVars:
    def POST(self):
        web.header('Content-Type', 'application/json')
        str1 = ''

        for temp in slc.current_playlist:
            str1 = str1 + '"' + temp[0] + '",'

        str1 = str1[:-1]

        return '{"currentsong":"' + slc.current_song_name + '","duration":"' + str(
            slc.duration) + '","currentpos":"' + str(
            slc.current_position) + '","playlist":[' + str1 + '],"playlistplaying":"' + \
               slc.playlistplaying + '"}'


class upload:
    def POST(self):
        filedir = env + "/music/"  # change this to the directory you want to store the file in.
        i = web.webapi.rawinput()
        files = i.myfile

        if not isinstance(files, list):
            files = [files]

        for x in files:
            filepath = x.filename.replace('\\',
                                          '/')  # replaces the windows-style slashes with linux
                                          # ones.
            filename = filepath.split('/')[
                -1]  # splits the and chooses the last part (the filename with extension)
            fout = open(filedir + '/' + filename,
                        'w')  # creates the file where the uploaded file should be stored
            fout.write(x.file.read())  # writes the uploaded file to the newly created file.
            fout.close()  # closes the file, upload complete.

        web.header('Content-Type', 'application/json')
        str1 = '{"songs":['

        for file in glob.glob(env + "/music/*.mp3"):
            str1 = str1 + '["' + os.path.basename(file) + '","' + file + '"],'

        for file in glob.glob(env + "/music/*.wav"):
            str1 = str1 + '["' + os.path.basename(file) + '","' + file + '"],'

        str1 = str1[:-1]
        str1 = str1 + ']}'

        return str1


class sched:
    def POST(self):
        vars = web.input()
        if vars.option == '0':
            id = sch.addEvent(vars.type, vars.theif, vars.thethen, vars.arg)

            return id

        elif vars.option == '1':
            sch.configData['locationData']['lat'] = vars.lat
            sch.configData['locationData']['lng'] = vars.lng
            sch.saveConfig()
            sch.loadConfig()

        elif vars.option == '2':
            sch.removeEvent(vars.id)


class Application(web.application):
    def run(self, port=8080, *middleware):
        func = self.wsgifunc(*middleware)

        return web.httpserver.runsimple(func, ('0.0.0.0', port))


if __name__ == "__main__":
    web.config.debug = False
    app = Application(urls, globals())
    app.run(port=slc.port)

    sch.stopScheduler()
    slc.lightsoff()    
