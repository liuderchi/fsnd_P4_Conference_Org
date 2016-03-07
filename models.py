#!/usr/bin/env python

"""models.py

Udacity conference server-side Python App Engine data & ProtoRPC models

$Id: models.py,v 1.1 2014/05/24 22:01:10 wesc Exp $

created/forked from conferences.py by wesc on 2014 may 24

"""


import httplib
import endpoints
from protorpc import messages
from google.appengine.ext import ndb


class ConflictException(endpoints.ServiceException):
    """ConflictException -- exception mapped to HTTP 409 response"""
    http_status = httplib.CONFLICT


# define user profile, extends ndb
class Profile(ndb.Model):
    """Profile -- User profile object"""
    displayName = ndb.StringProperty()
    mainEmail = ndb.StringProperty()
    conferenceKeysToAttend = ndb.StringProperty(repeated=True)
    sessionKeysOnWishlist = ndb.StringProperty(repeated=True)

# contains only 2 forms for editable users
class ProfileMiniForm(messages.Message):
    """ProfileMiniForm -- update Profile form message"""
    displayName = messages.StringField(1)

# mirrors the fields of the Profile class
class ProfileForm(messages.Message):
    """ProfileForm -- Profile outbound form message"""
    displayName = messages.StringField(1)
    mainEmail = messages.StringField(2)
    conferenceKeysToAttend = messages.StringField(3, repeated=True)
    sessionKeysOnWishlist = messages.StringField(4, repeated=True)

# _TODO 1 anouncement response message
class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    data = messages.StringField(1, required=True)

class BooleanMessage(messages.Message):
    """BooleanMessage-- outbound Boolean value message"""
    data = messages.BooleanField(1)

class Conference(ndb.Model):
    """Conference -- Conference object"""
    name            = ndb.StringProperty(required=True)
    description     = ndb.StringProperty()
    organizerUserId = ndb.StringProperty()
    topics          = ndb.StringProperty(repeated=True)
    city            = ndb.StringProperty()
    startDate       = ndb.DateProperty()
    month           = ndb.IntegerProperty()
    endDate         = ndb.DateProperty()
    maxAttendees    = ndb.IntegerProperty()
    seatsAvailable  = ndb.IntegerProperty()

class ConferenceForm(messages.Message):
    """ConferenceForm -- Conference outbound form message"""
    name            = messages.StringField(1)
    description     = messages.StringField(2)
    organizerUserId = messages.StringField(3)
    topics          = messages.StringField(4, repeated=True)
    city            = messages.StringField(5)
    startDate       = messages.StringField(6)
    month           = messages.IntegerField(7, variant=messages.Variant.INT32)
    maxAttendees    = messages.IntegerField(8, variant=messages.Variant.INT32)
    seatsAvailable  = messages.IntegerField(9, variant=messages.Variant.INT32)
    endDate         = messages.StringField(10)
    websafeKey      = messages.StringField(11)
    organizerDisplayName = messages.StringField(12)

class ConferenceForms(messages.Message):
    """ConferenceForms -- multiple Conference outbound form message"""
    items = messages.MessageField(ConferenceForm, 1, repeated=True)


class Speaker(ndb.Model):
    """Speaker -- Speaker object as stored in Data Store."""
    name = ndb.StringProperty(required=True)


class SpeakerFormIn(messages.Message):
    """SpeakerFormIn -- inbound speaker form message"""
    name = messages.StringField(1)


class SpeakerFormOut(messages.Message):
    """SpeakerFormOut -- outbound speaker form message"""
    name = messages.StringField(1)
    websafeKey = messages.StringField(2)


class SpeakerForms(messages.Message):
    """SpeakerForms -- multiple Speaker outbound form message"""
    items = messages.MessageField(SpeakerFormOut, 1, repeated=True)


class Session(ndb.Model):
    """
    Session -- Session objects stored in Data Store.
    using a KeyProperty to hold the speakers of a session.
    """
    name = ndb.StringProperty(required=True)
    highlight = ndb.StringProperty(repeated=True)
    speaker = ndb.KeyProperty(repeated=True)
    date = ndb.DateProperty()
    startTime = ndb.TimeProperty()
    durationInMins = ndb.IntegerProperty()
    typeOfSession = ndb.StringProperty(default='NOT_SPECIFIED')
    location = ndb.StringProperty()

class SessionType(messages.Enum):
    """SessionType -- session type enumeration value"""
    NOT_SPECIFIED = 1
    WORKSHOP = 2
    LECTURE = 3
    KEYNOTE = 4
    CODELAB = 5

class SessionFormIn(messages.Message):
    """SessionFormIn -- Session inbound form message"""
    name = messages.StringField(1, required=True)
    highlight = messages.StringField(2, repeated=True)
    speaker_key = messages.StringField(3, repeated=True)
    date = messages.StringField(4)
    startTime = messages.StringField(5)
    durationInMins = messages.IntegerField(6)
    typeOfSession = messages.EnumField(SessionType, 7)
    location = messages.StringField(8)

class SessionFormOut(messages.Message):
    """SessionFormOut -- Session outbound form message"""
    name = messages.StringField(1, required=True)
    highlight = messages.StringField(2, repeated=True)
    speaker = messages.MessageField(SpeakerFormOut, 3, repeated=True)
    date = messages.StringField(4)
    startTime = messages.StringField(5)
    durationInMins = messages.IntegerField(6)
    typeOfSession = messages.StringField(7)
    location = messages.StringField(8)
    websafeConferenceKey = messages.StringField(9)
    sessionId = messages.StringField(10)

class SessionForms(messages.Message):
    """SessionForms -- multiple Session outbound form message"""
    items = messages.MessageField(SessionFormOut, 1, repeated=True)

class QueryForm(messages.Message):
    """QueryForm -- query inbound form message"""
    field = messages.StringField(1)
    operator = messages.StringField(2)
    value = messages.StringField(3)

class QueryForms(messages.Message):
    """QueryForms -- multiple QueryForm inbound form message"""
    filters = messages.MessageField(QueryForm, 1, repeated=True)
