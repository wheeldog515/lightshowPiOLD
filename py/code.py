#!/usr/bin/env python


import web
import glob
import os
import synchronized_lights as lights
import json
import scheduler_class as scheduler


template_dir = os.path.abspath(os.path.dirname(__file__)) + "/templates"
slc = lights.SynchronizedLights()
sch = scheduler.Scheduler(slc)
env = os.environ['SYNCHRONIZED_LIGHTS_HOME']

urls = ('/', 'Index',
        '/index.html', 'Index',
        '/favicon.ico', 'favicon',
        '/app.manifest', 'Hello',
        '/ajax', 'Ajax',
        '/getvars', 'GetVars',
        '/upload', 'Upload',
        '/scheduler', 'Sched',
        '/music', 'Music',
        '/(js|css|img)/(.*)', 'Static')

render = web.template.render(template_dir, cache=True, globals={'glob': glob, 'os': os, 'sch': sch})


class Index(object):
    @staticmethod
    def GET():
        return render.index()


class Hello(object):
    @staticmethod
    def GET():
        web.header('Content-Type', 'text/cache-manifest')
        rmod = "r"

        f = open(os.environ['SYNCHRONIZED_LIGHTS_HOME'] + '/py/static/app.manifest', rmod)

        try:
            stream = f.read()

            return stream
        except IOError:
            f.close()

            return '404 Not Found'


class Static(object):
    @staticmethod
    def GET(media, fn):
        rmod = "r"

        if fn.endswith(".png"):
            rmod = "rb"

        f = open(os.environ['SYNCHRONIZED_LIGHTS_HOME'] + '/py/static/' + media + '/' + fn, rmod)

        try:
            stream = f.read()

            return stream
        except IOError:
            f.close()

            return '404 Not Found'


class Favicon(object):
    @staticmethod
    def GET():
        f = open(os.environ['SYNCHRONIZED_LIGHTS_HOME'] + "/py/static/favicon.ico", 'rb')

        return f.read()


class Music(object):
    @staticmethod
    def POST():
        web.header('Content-Type', 'application/json')

        return '{"sr":' + str(slc.sr) + ',"nc":' + str(slc.nc) + ',"fc":' + str(slc.fc) + '}'

    @staticmethod
    def GET():
        return slc.thedata


class Ajax(object):
    @staticmethod
    def GET():
        var = web.input()

        if var.option == '0':
            web.header('Content-Type', 'application/json')

            return json.dumps(sch.configData['schedule'])

        elif var.option == '1':
            return slc.audioChunkNumber

    @staticmethod
    def POST():
        variables = web.input()

        if variables.option == '0':
            slc.playlist(variables.playlist)

        elif variables.option == '1':
            slc.play_single(variables.song)

        elif variables.option == '3':
            slc.lightson()

        elif variables.option == '4':
            slc.lightsoff()

        elif variables.option == 'lightOn':
            # turn on a light
            slc.lighton(int(variables.port))

        elif variables.option == 'lightOff':
            # turn off a light
            slc.lightoff(int(variables.port))

        elif variables.option == '5':
            web.header('Content-Type', 'application/json')

            return slc.get_config()

        elif variables.option == '6':
            slc.set_config(variables.object)

        elif variables.option == '7':
            slc.play_all()

        elif variables.option == '8':
            web.header('Content-Type', 'application/json')
            str1 = '{"songs":['

            for mfile in glob.glob(env + "/music/*.mp3"):
                str1 = str1 + '["' + os.path.basename(mfile) + '","' + mfile + '"],'

            for mfile in glob.glob(env + "/music/*.wav"):
                str1 = str1 + '["' + os.path.basename(mfile) + '","' + mfile + '"],'

            str1 = str1[:-1]
            str1 += ']}'

            return str1

        elif variables.option == '9':
            web.header('Content-Type', 'application/json')

            mfile = open(env + "/music/playlists/" + variables.name + ".playlist", "w")
            mfile.write(variables.val)
            mfile.close()

            str1 = '{"playlists":['

            for mfile in glob.glob(env + "/music/playlists/*.playlist"):
                str1 = str1 + '["' + os.path.basename(mfile) + '","' + mfile + '"],'

            str1 = str1[:-1]
            str1 += ']}'

            return str1

        elif variables.option == '10':
            web.header('Content-Type', 'application/json')

            if hasattr(variables, 'playlist'):
                os.remove(variables.playlist)

            str1 = '{"playlists":['

            for mfile in glob.glob(env + "/music/playlists/*.playlist"):
                str1 = str1 + '["' + os.path.basename(mfile) + '","' + mfile + '"],'

            str1 = str1[:-1]
            str1 += ']}'

            return str1

        elif variables.option == '11':
            slc.set_config_default()

        elif variables.option == '12':
            app.stop()
            os.system("sudo shutdown -h now")

        elif variables.option == '13':
            app.stop()
            os.system("sudo shutdown -r now")

        elif variables.option == '14':
            return slc.audioChunk

        elif variables.option == '15':
            web.header('Content-Type', 'application/json')

            return json.dumps(sch.configData['schedule'])

        elif variables.option == '16':
            if slc.AudioIn:
                slc.AudioIn = False

            else:
                slc.AudioIn = True
                slc.audio_in()

        elif variables.option == '17':
            if slc.lights_active:
                slc.lights_active = False
                slc.lightsoff()
            else:
                slc.lights_active = True

class GetVars(object):
    @staticmethod
    def POST():
        web.header('Content-Type', 'application/json')
        str1 = ''

        for temp in slc.current_playlist:
            str1 = str1 + '"' + temp[0] + '",'

        str1 = str1[:-1]

        return '{"currentsong":"' + slc.current_song_name + '","duration":"' + str(
            slc.duration) + '","currentpos":"' + str(
            slc.current_position) + '","playlist":[' + str1 + '],"playlistplaying":"' + \
            slc.playlistplaying + '"}'


class Upload(object):
    @staticmethod
    def POST():
        filedir = env + "/music/"  # change this to the directory you want to store the file in.
        i = web.webapi.rawinput()
        files = i.myfile

        if not isinstance(files, list):
            files = [files]

        for x in files:
            # replaces the windows-style slashes with linux ones.
            filepath = x.filename.replace('\\', '/')

            # splits the and chooses the last part (the filename with extension)
            filename = filepath.split('/')[-1]

            # creates the file where the uploaded file should be stored
            fout = open(filedir + '/' + filename, 'w')

            # writes the uploaded file to the newly created file.
            fout.write(x.file.read())

            # closes the file, upload complete.
            fout.close()

        web.header('Content-Type', 'application/json')
        str1 = '{"songs":['

        for mfile in glob.glob(env + "/music/*.mp3"):
            str1 = str1 + '["' + os.path.basename(mfile) + '","' + mfile + '"],'

        for mfile in glob.glob(env + "/music/*.wav"):
            str1 = str1 + '["' + os.path.basename(mfile) + '","' + mfile + '"],'

        str1 = str1[:-1]
        str1 += ']}'

        return str1


class Sched(object):
    @staticmethod
    def POST():
        variables = web.input()
        if variables.option == '0':
            event_id = sch.add_event(variables.type, variables.theif, variables.thethen,
                                     variables.arg)

            return event_id

        elif variables.option == '1':
            sch.configData['locationData']['lat'] = variables.lat
            sch.configData['locationData']['lng'] = variables.lng
            sch.save_config()
            sch.load_config()

        elif variables.option == '2':
            sch.remove_event(variables.id)


class Application(web.application):
    def run(self, port=8080, *middleware):
        func = self.wsgifunc(*middleware)

        return web.httpserver.runsimple(func, ('0.0.0.0', port))


if __name__ == "__main__":
    web.config.debug = False
    app = Application(urls, globals())
    app.run(port=slc.port)

    sch.stop_scheduler()
    slc.lightsoff()    
