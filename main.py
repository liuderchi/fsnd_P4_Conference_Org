#!/usr/bin/env python

"""
main.py -- Udacity conference server-side Python App Engine
    HTTP controller handlers for memcache & task queue access

$Id$

created by wesc on 2014 may 24

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

import webapp2
from google.appengine.api import app_identity
from google.appengine.api import mail
from conference import ConferenceApi

class SetAnnouncementHandler(webapp2.RequestHandler):
    def get(self):
        """Set Announcement in Memcache."""
        # _TODO 1
        ConferenceApi._cacheAnnouncement()

# _TODO 2
class SendConfirmationEmailHandler(webapp2.RequestHandler):
    # the handler of sending email is a POST request
    def post(self):
        """Send email confirming Conference creation."""
        mail.send_mail(
            'noreply@%s.appspotmail.com' % (
                app_identity.get_application_id()),     # from
            self.request.get('email'),                  # to
            'You created a new Conference!',            # subj
            'Hi, you have created a following '         # body
            'conference:\r\n\r\n%s' % self.request.get(
                'conferenceInfo')
        )


class SearchFeaturedSpeakers(webapp2.RequestHandler):
    def post(self):
        """Check if speakers in session are featured."""
        print "searching Featuring Speaker"
        ConferenceApi._cacheFeaturedSpeaker(
            self.request.get('websafeConferenceKey'),
            self.request.get('sessionId'))
        self.response.set_status(204)


app = webapp2.WSGIApplication([
    ('/crons/set_announcement', SetAnnouncementHandler),
    ('/tasks/send_confirmation_email', SendConfirmationEmailHandler),
    ('/tasks/search_featured_speakers', SearchFeaturedSpeakers),
], debug=True)
