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
from django.utils import simplejson
from datetime import datetime, timedelta, time



class MainPage(webapp.RequestHandler):
	def get(self):
		template_values = {}
		path = os.path.join(os.path.dirname(__file__), 'admin.html')
		self.response.out.write(template.render(path, template_values)) 
       
class Logout(webapp.RequestHandler):
    def get(self):
        self.redirect(users.create_logout_url('/'))

class faqs(db.Model):
    question = db.StringProperty(multiline=True)
    answer =  db.StringProperty(multiline=True)

class Devices(db.Model):
    user = db.UserProperty()
    token = db.StringProperty()
    deviceid = db.StringProperty()
    devicename = db.StringProperty()
    devicekey = db.StringProperty()
    devicetype = db.StringProperty()
    created = db.DateTimeProperty(auto_now_add=True)


class AddFaq(webapp.RequestHandler):
    def get(self):
        template_values = {}
	path = os.path.join(os.path.dirname(__file__), 'addfaq.html')
	self.response.out.write(template.render(path, template_values))
    def post(self):
	    faq = faqs()
	    faq.question = self.request.get('question')
	    faq.answer = self.request.get('answer')
	    faq.put()
	    template_values = {'result' : 'Added'}
	    path = os.path.join(os.path.dirname(__file__), 'addfaq.html')
	    self.response.out.write(template.render(path, template_values))

class CleanupDevices(webapp.RequestHandler):
	def get(self):
		count = 0
		hungdevices = db.GqlQuery("SELECT * FROM Devices")
		for device in hungdevices:
			if device.deviceid:
				if device.devicekey == None:
					if (datetime.now() - device.created) > timedelta(minutes=10):
						logging.info("Deleting: " + device.deviceid)
						device.delete()
						count += 1
		logging.info("Cleanup Complete, " + str(count) + " Devices Deleted")

        
	       
application = webapp.WSGIApplication([('/admin/', MainPage),
                                      ('/admin/addfaq', AddFaq),
				      ('/admin/cleanupdevices', CleanupDevices),
                                      ('/admin/logout', Logout)], 
				      debug=True)



def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
