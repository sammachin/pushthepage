#!/usr/bin/env python

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import urlfetch
import os
from google.appengine.ext.webapp import template
import random
import logging
import urbanairship
import sys
import md5
import string
import unicodedata, re
import urllib
from django.utils import simplejson
from google.appengine.ext.webapp import xmpp_handlers
from google.appengine.api import xmpp
import creds



def shorten(url):
    request = "http://api.bit.ly/v3/shorten?domain=bit.ly&login=sammachin&apiKey%s&format=txt&longUrl=" % cred.bitlykey
    request += urllib.quote(url)
    result = urlfetch.fetch(request)
    return result.content

class MainPage(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
           self.redirect('/welcome')
        else:
            template_values = {}
            path = os.path.join(os.path.dirname(__file__), 'index.html')
            self.response.out.write(template.render(path, template_values))

class ComingSoon(webapp.RequestHandler):
	def get(self):
            template_values = {}
            path = os.path.join(os.path.dirname(__file__), 'comingsoon.html')
            self.response.out.write(template.render(path, template_values))


class Hello(webapp.RequestHandler):
	def get(self):
            template_values = {}
            path = os.path.join(os.path.dirname(__file__), 'hello.html')
            self.response.out.write(template.render(path, template_values))

class Congrats(webapp.RequestHandler):
	def get(self):
            template_values = {}
            path = os.path.join(os.path.dirname(__file__), 'congrats.html')
            self.response.out.write(template.render(path, template_values))



class Welcome(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            template_values = { 'user':  user.nickname(), }
            path = os.path.join(os.path.dirname(__file__), 'welcome.html')
            self.response.out.write(template.render(path, template_values))
        else:
            self.redirect(users.create_login_url(self.request.uri))
            
    

class Logout(webapp.RequestHandler):
    def get(self):
        self.redirect(users.create_logout_url('/'))


class GetLink(webapp.RequestHandler):
    def get(self):
        query = Devices.all()
        query.filter("deviceid =", self.request.get('linkid'))
        query.filter("user =", users.get_current_user())
        r = query.get()
        try:
            r.devicename
        except Exception:
            template_values = {}
            path = os.path.join(os.path.dirname(__file__), 'nopairing.html')
            self.response.out.write(template.render(path, template_values))
        else:   
            devicename  = filter(lambda x: x in string.printable, r.devicename)
            logging.debug(devicename)
            devicekey = str(md5.new(self.request.get('linkid') + devicename).hexdigest())
            logging.debug(devicekey)
            r.devicekey = devicekey
            r.deviceid = ""
            db.put(r)
            template_values = { 'devicekey':  devicekey,
                                'devicename': r.devicename, }
            path = os.path.join(os.path.dirname(__file__), 'getlink.html')
            self.response.out.write(template.render(path, template_values))

class DeleteDevice(webapp.RequestHandler):
    def get(self):      
        query = Devices.all()
        query.filter("devicekey =", self.request.get('devicekey'))
        query.filter("user =", users.get_current_user())
        r = query.get()
        try:
            name = r.devicename
        except Exception:
            template_values = {}
            path = os.path.join(os.path.dirname(__file__), 'hungpairing.html')
            self.response.out.write(template.render(path, template_values))
        else:
            db.delete(r)
            template_values = { 'devicename':  name,
                                }
            path = os.path.join(os.path.dirname(__file__), 'devicedeleted.html')
            self.response.out.write(template.render(path, template_values))

class GetSenders(webapp.RequestHandler):
    def post(self):
        query = Devices.all().filter("token =", self.request.get('token'))
        r = query.fetch(10)
        data = []
        for result in r:
            sender = {}
            sender['user'] = result.user.nickname()
            sender['devicekey'] = result.devicekey
            sender['devicename'] = result.devicename
            data.append(sender)
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(simplejson.dumps(data))

class DeleteSender(webapp.RequestHandler):
    def post(self):
        query = Devices.all().filter("devicekey =", self.request.get('devicekey')).filter("token =", self.request.get('token'))
        r = query.get()
        if r:
            db.delete(r)
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.out.write('Deleted: ' + r.user.nickname())
        else:
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.out.write('Error')
            

class AddDevice(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            randnum = str(random.randint(10000000,99999999))
            memcache.set(randnum, user, time=600)
            template_values = { 'randnum':  randnum, }
            path = os.path.join(os.path.dirname(__file__), 'adddevice.html')
            self.response.out.write(template.render(path, template_values))
        else:
            self.redirect(users.create_login_url(self.request.uri))
            
class PairDevice(webapp.RequestHandler):
    def post(self):
        token = self.request.get('token')
        pairingid = self.request.get('pairingid')
        devicename = self.request.get('name')
        devicetype = self.request.get('devicetype')
        user = memcache.get(pairingid)
        if user:
            device = Devices()
            device.user = user
            device.token = token
            device.devicename = devicename
            device.deviceid = pairingid
            device.devicetype = devicetype
            device.put()
            if devicetype == "ios":
                application_key = creds.ua_application_key
				master_secret = creds.ua_master_secret
                alias = str(user.nickname()) + "_" + devicename
                logging.debug(alias)
                try:
                    airship = urbanairship.Airship(application_key, master_secret)
                    airship.register(token, alias=alias)
                    memcache.delete(pairingid)
                    self.response.headers['Content-Type'] = 'text/plain'
                    self.response.out.write('OK ' + user.nickname())
                except:
                    self.response.headers['Content-Type'] = 'text/plain'
                    self.response.out.write('Error')    
        else:
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.out.write('Error')
        
class CheckPairing(webapp.RequestHandler):
    def get(self):
        pairingid = self.request.get('pairingid')
        paired = memcache.get(pairingid)
        if paired:
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.out.write('Done')
        else:
            self.error(202)
            
            
class Devices(db.Model):
    user = db.UserProperty()
    token = db.StringProperty()
    deviceid = db.StringProperty()
    devicename = db.StringProperty()
    devicekey = db.StringProperty()
    devicetype = db.StringProperty()
    created = db.DateTimeProperty(auto_now_add=True)


class faqs(db.Model):
    question = db.StringProperty(multiline=True)
    answer =  db.StringProperty(multiline=True)

class Send(webapp.RequestHandler):
    def get(self):
        if users.get_current_user():
            devicekey = self.request.get('device')
            if len(self.request.get('url')) > 100:
                link = shorten(self.request.get('url'))                
            else:
                link = self.request.get('url') 
            query = Devices.all()
            query.filter("devicekey =", devicekey)
            query.filter("user =", users.get_current_user())
            r = query.get()
            try:
                r.token
            except Exception:
                template_values = {'user' : users.get_current_user()}
                path = os.path.join(os.path.dirname(__file__), 'nodevice.html')
                self.response.out.write(template.render(path, template_values))
            else:   
                if r.devicetype == "ios":
                    logging.debug("Sending UA Push to: " + r.token)
                    application_key = creds.ua_application_key
					master_secret = creds.ua_master_secret
                    try:
                        airship = urbanairship.Airship(application_key, master_secret)
                        airship.push({'aps': {'alert': link, 'sound': 'bing'}}, device_tokens=[r.token])
                        self.redirect(link)
                    except: 
                        template_values = {'errortext' : str(sys.exc_info()[1][1])}
                        path = os.path.join(os.path.dirname(__file__), 'uaerror.html')
                        self.response.out.write(template.render(path, template_values))
                elif r.devicetype == "xmpp":
                    logging.debug("Sending XMPP to: " + r.token)
                    xmpp.send_message(r.token, link)   
                    self.redirect(link)
        else:
            self.redirect(users.create_login_url(self.request.uri))


class Done(webapp.RequestHandler):
    def get(self):
        if users.get_current_user():
            devicekey = self.request.get('device')
            link = "http://www.pushthepage.com/Hello" 
            query = Devices.all()
            query.filter("devicekey =", devicekey)
            query.filter("user =", users.get_current_user())
            r = query.get()
            try:
                r.token
            except Exception:
                template_values = {'user' : users.get_current_user()}
                path = os.path.join(os.path.dirname(__file__), 'nodevice.html')
                self.response.out.write(template.render(path, template_values))
            else:   
                if r.devicetype == "ios":
                    logging.debug("Sending UA Push to: " + r.token)
                    application_key = creds.ua_application_key
					master_secret = creds.ua_master_secret
                    airship = urbanairship.Airship(application_key, master_secret)
                    airship.push({'aps': {'alert': link, 'sound': 'bing'}}, device_tokens=[r.token])
                elif r.devicetype == "xmpp":
                    logging.debug("Sending XMPP to: " + r.token)
                    xmpp.send_message(r.token, link)   
                self.redirect("http://www.pushthepage.com/congratulations")
        else:
            self.redirect(users.create_login_url(self.request.uri))

            
class ListDevices(webapp.RequestHandler):
    def get(self):
        devices_query = Devices.all().filter("user =", users.get_current_user())
        devices = devices_query.fetch(100)

        if users.get_current_user():
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        template_values = {
            'devices': devices,
            'url': url,
            'url_linktext': url_linktext,
            }

        path = os.path.join(os.path.dirname(__file__), 'ListDevices.html')
        self.response.out.write(template.render(path, template_values))

class Admin(webapp.RequestHandler):
    def get(self):
        self.redirect("/admin/")

class Faqs(webapp.RequestHandler):
    def get(self):
        faqs_query = faqs.all()
        questions = faqs_query.fetch(100)
        template_values = {'faqs': questions}
        user = users.get_current_user()
        if user:
           path = os.path.join(os.path.dirname(__file__), 'faqs.html')
           self.response.out.write(template.render(path, template_values))
        else:
           path = os.path.join(os.path.dirname(__file__), 'faqs_visitor.html')
           self.response.out.write(template.render(path, template_values))

class XmppHandler(xmpp_handlers.CommandHandler):
    def pair_command(self, Message=None):
        logging.debug(Message.sender)
        token = Message.sender
        #token = Message.sender.split("/")[0]
        pairingid = Message.arg[0:8]
        devicename = Message.arg[9:]
        devicetype = "xmpp"
        user = memcache.get(pairingid)
        if user:
            device = Devices()
            device.user = user
            device.token = token
            device.devicename = devicename
            device.deviceid = pairingid
            device.devicetype = devicetype
            device.put()
            xmpp.send_invite(token)
            memcache.delete(pairingid)
            Message.reply('OK ' + user.nickname())
        else:
            Message.reply('Error')
    def getsenders_command(self, Message=None):
        token = Message.sender.split("/")[0]
        query = Devices.all().filter("token =", token)
        r = query.fetch(10)
        data = []
        for result in r:
            sender = {}
            sender['user'] = result.user.nickname()
            sender['devicekey'] = result.devicekey
            sender['devicename'] = result.devicename
            data.append(sender)
        Message.reply(simplejson.dumps(data))
    def deletesender_command(self, Message=None):
        token = Message.sender.split("/")[0]
        devicekey = Message.arg[0:32]
        query = Devices.all().filter("devicekey =", devicekey).filter("token =", token)
        r = query.get()
        if r:
            db.delete(r)
            Message.reply('Deleted: ' + r.user.nickname())
        else:
            Message.reply('Error')
    def help_command(self, Message=None):
        Message.reply("http://www.pushthepage.com/faqs")
    def text_message(self, Message=None):
        Message.reply("Unknown Command")

            

application = webapp.WSGIApplication([('/', ComingSoon),
                                      ('/_ah/xmpp/message/chat/', XmppHandler),
				      				  ('/main', MainPage),
                                      ('/welcome', Welcome),
                                      ('/send', Send),
                                      ('/devices', ListDevices),
				      				  ('/add', AddDevice),
                                      ('/pair', PairDevice),
                                      ('/checkpairing', CheckPairing),
                                      ('/link', GetLink),
                                      ('/getsenders', GetSenders),
                                      ('/deletedevice', DeleteDevice),
                                      ('/deletesender', DeleteSender),
                                      ('/faqs', Faqs),
                                      ('/admin', Admin),
                                      ('/done', Done),
                                      ('/Hello', Hello),
                                      ('/congratulations', Congrats),
                                      ('/logout', Logout)], 
				      				debug=True)



def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
