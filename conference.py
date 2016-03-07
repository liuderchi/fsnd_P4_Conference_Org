#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'


from datetime import datetime

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import ConflictException
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import QueryForm
from models import QueryForms
from models import StringMessage
from models import SessionType
from models import Session
from models import SessionFormIn
from models import SessionFormOut
from models import SessionForms
from models import Speaker
from models import SpeakerFormIn
from models import SpeakerFormOut
from models import SpeakerForms

from utils import getUserId
from utils import get_current_user_id

from settings import WEB_CLIENT_ID

import logging

logging.getLogger().setLevel(logging.DEBUG)

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
MEMCACHE_FEATUREDSPEAKER_KEY = "FEATURED_SPEAKER"
FEATUREDSPEAKER_TPL = (
    'Speaker %s is our feature speaker, will appear in these sessions: %s')

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

DEFAULTS_CONF = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": [ "Default_Topic" ],
}

DEFAULTS_SESS = {
    "durationInMins": 60,
    "location": "Default Room",
    "highlight": [ "Default_Highlight" ],
}

OPERATORS = {
            'EQ':   '=',
            'GT':   '>',
            'GTEQ': '>=',
            'LT':   '<',
            'LTEQ': '<=',
            'NE':   '!='
            }

FIELDS_CONF =    {
            'CITY': 'city',
            'TOPIC': 'topics',
            'MONTH': 'month',
            'MAX_ATTENDEES': 'maxAttendees',
            }

FIELDS_SESS = {
    'START_TIME': 'startTime',
    'DURATION_IN_MINS': 'durationInMins',
    'TYPE_OF_SESSION': 'typeOfSession',
    'LOCATION': 'location',
}

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1),
)


SESS_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    sessionId=messages.StringField(2),
)

SESS_CREATE_REQUEST = endpoints.ResourceContainer(
    SessionFormIn,
    websafeConferenceKey=messages.StringField(1),
)

SESS_POST_REQUEST = endpoints.ResourceContainer(
    SessionFormIn,
    websafeConferenceKey=messages.StringField(1),
    sessionId=messages.StringField(2),
)

SESS_GET_BY_TYPE = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    typeOfSession=messages.StringField(2),
)

SESS_GET_ALL_BY_SPEAKER = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSpeakerKey=messages.StringField(1),
)

SESS_GET_BY_SPEAKER = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    websafeSpeakerKey=messages.StringField(2),
)

SESS_GET_BY_LOCATION = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    location=messages.StringField(2),
)

SESS_GET_BY_HIGHLIGHT = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    highlight=messages.StringField(2),
)

SESS_QUERY_FORMS = endpoints.ResourceContainer(
    QueryForms,
    websafeConferenceKey=messages.StringField(1),
)

SPEAKER_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSpeakerKey=messages.StringField(1),
)

SPEAKER_POST_REQUEST = endpoints.ResourceContainer(
    SpeakerFormIn,
    websafeSpeakerKey=messages.StringField(1),
)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@endpoints.api(name='conference', version='v1',
    allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID],
    scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

# - - - Conference objects - - - - - - - - - - - - - - - - -
    def ____CONFERENCE_PART():
        pass # marked as a divider in function tree view

    def _copyConferenceToForm(self, conf, displayName):
        """Copy relevant fields from Conference to ConferenceForm."""
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if displayName:
            setattr(cf, 'organizerDisplayName', displayName)
        cf.check_initialized()
        return cf


    def _createConferenceObject(self, request):
        """Create or update Conference object, returning ConferenceForm/request."""
        """Add a task of sending confirmation email to task queue"""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException("Conference 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # add default values for those missing (both data model & outbound Message)
        for df in DEFAULTS_CONF:
            if data[df] in (None, []):
                data[df] = DEFAULTS_CONF[df]
                setattr(request, df, DEFAULTS_CONF[df])

        # convert dates from strings to Date objects; set month based on start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(data['startDate'][:10],
                                                  "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(data['endDate'][:10],
                                                "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
        # generate Profile Key based on user ID and Conference
        # ID based on Profile key get Conference key from ID
        p_key = ndb.Key(Profile, user_id)
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key
        data['organizerUserId'] = request.organizerUserId = user_id

        Conference(**data).put()
        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        # _TODO 2: add confirmation email sending task to queue
        taskqueue.add(params={'email': user.email(),
            'conferenceInfo': repr(request)},
            url='/tasks/send_confirmation_email'
        )

        return request


    @ndb.transactional()
    def _updateConferenceObject(self, request):
        user_id = get_current_user_id()

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}

        # update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # check that conference exists
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
            http_method='POST', name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)


    @endpoints.method(CONF_POST_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='PUT', name='updateConference')
    def updateConference(self, request):
        """Update conference with provided fields & return with updated info."""
        return self._updateConferenceObject(request)


    @endpoints.method(CONF_GET_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='GET', name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)
        prof = conf.key.parent().get()
        # return ConferenceForm
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='getConferencesCreated',
            http_method='POST', name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        # make sure user is authed
        user_id =  get_current_user_id()
        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, getattr(prof, 'displayName')) for conf in confs]
        )

# - - - - - - - - - - Conference Query functions
    def ____CONF_QUERY_PART():
        pass # marked as a divider in function tree view

    def _getConferenceQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Conference.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)

        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q


    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name) for field in f.all_fields()}

            try:
                filtr["field"] = FIELDS_CONF[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException("Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous filters
                # disallow the filter if inequality was performed on a different field before
                # track the field on which the inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException("Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)


    @endpoints.method(QueryForms, ConferenceForms,
            path='queryConferences',
            http_method='POST',
            name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        conferences = self._getConferenceQuery(request)

        # 1. fetch organiser displayName from profiles
        # get all keys and use get_multi
        organisers = [(ndb.Key(Profile, conf.organizerUserId)) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # parse display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # 2. return individual ConferenceForm object per Conference
        return ConferenceForms(
                items=[self._copyConferenceToForm(conf, names[conf.organizerUserId]) for conf in \
                conferences]
        )

# - - - Speaker objects - - - - - - - - - - - - - - - - -
    def ____SPEAKER_PART():
        pass # marked as a divider in function tree view

    def _copySpeakerToForm(self, speaker):
        """Copy relevant fields from Speaker to SpeakerFormOut."""
        sf = SpeakerFormOut()
        for field in sf.all_fields():
            if hasattr(speaker, field.name):
                setattr(sf, field.name, getattr(speaker, field.name))
            elif field.name == "websafeKey":
                setattr(sf, field.name, speaker.key.urlsafe())
        sf.check_initialized()
        return sf

    def _createSpeakerObject(self, request):
        """Create Speaker object, returning SpeakerFormOut."""
        # preload necessary data items
        user_id = get_current_user_id()

        if not request.name:
            raise endpoints.BadRequestException(
                "Speaker 'name' field required")

        # copy SpeakerFormIn/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}

        # generate Profile Key based on user ID, used as parent
        p_key = ndb.Key(Profile, user_id)
        data['parent'] = p_key

        # create Speaker & return (new) SpeakerFormOut
        speaker = Speaker(**data).put()
        return self._copySpeakerToForm(speaker.get())

    @ndb.transactional()
    def _updateSpeakerObject(self, request):
        user_id = get_current_user_id()

        # update existing speaker
        speaker = ndb.Key(urlsafe=request.websafeSpeakerKey).get()
        # check that speaker exists
        if not speaker:
            raise endpoints.NotFoundException(
                'No speaker found with key: %s' % request.websafeSpeakerKey)

        # check that user is owner:
        # speaker parent (=profile) has user_id as id
        if user_id != speaker.key.parent().string_id():
            raise endpoints.ForbiddenException(
                'Only the owner can update the speaker.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from SpeakerFormIn to Speaker object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # write to Speaker object
                setattr(speaker, field.name, data)
        speaker.put()
        return self._copySpeakerToForm(speaker)

    @endpoints.method(
            SpeakerFormIn, SpeakerFormOut, path='speaker',
            http_method='POST', name='createSpeaker')
    def createSpeaker(self, request):
        """Create new speaker."""
        return self._createSpeakerObject(request)

    @endpoints.method(
            SPEAKER_POST_REQUEST, SpeakerFormOut,
            path='speaker/{websafeSpeakerKey}',
            http_method='PUT', name='updateSpeaker')
    def updateSpeaker(self, request):
        """Update speaker with provided fields & return with updated info."""
        return self._updateSpeakerObject(request)

    @endpoints.method(
            SPEAKER_GET_REQUEST, SpeakerFormOut,
            path='speaker/{websafeSpeakerKey}',
            http_method='GET', name='getSpeaker')
    def getSpeaker(self, request):
        """Return requested speaker (by websafeSpeakerKey)."""
        # get Speaker object from request; bail if not found
        speaker = ndb.Key(urlsafe=request.websafeSpeakerKey).get()
        if not speaker:
            raise endpoints.NotFoundException(
                'No speaker found with key: %s' % request.websafeSpeakerKey)
        if speaker.key.kind() != "Speaker":
            raise endpoints.NotFoundException(
                'Key does not belong to speaker: %s'% request.websafeSpeakerKey)
        # return SpeakerFormOut
        return self._copySpeakerToForm(speaker)

    @endpoints.method(message_types.VoidMessage, SpeakerForms,
            path='getAllSpeakers',
            http_method='GET', name='getAllSpeakers')
    def getAllSpeakers(self, request):
        """Get all Speakers"""
        user_id = get_current_user_id()
        speakers = Speaker.query()  # get all speakers
        return SpeakerForms(
            items=[self._copySpeakerToForm(speaker) for speaker in speakers]
        )

# - - - Session objects - - - - - - - - - - - - - - - - -
    def ____SESS_PART():
        pass # marked as a divider in function tree view

    def _copySessionToForm(self, sess):
        """Copy relevant fields from Session to SessionFormOut."""
        sf = SessionFormOut()
        for field in sf.all_fields():
            if hasattr(sess, field.name):
                # convert Date to date string and Time to time string;
                # copy speakers into forms;
                # just copy all the others
                if field.name in ("startTime", "date"):
                    setattr(sf, field.name, str(getattr(sess, field.name)))
                elif field.name == "speaker":
                    speakers = []
                    for speaker_key in getattr(sess, "speaker"):
                        speaker = speaker_key.get()
                        speakers.append(self._copySpeakerToForm(speaker))
                    setattr(sf, "speaker", speakers)
                else:
                    setattr(sf, field.name, getattr(sess, field.name))
            elif field.name == "sessionId":
                setattr(sf, field.name, str(sess.key.id()))
            elif field.name == "websafeConferenceKey":
                setattr(sf, field.name, sess.key.parent().urlsafe())
        sf.check_initialized()
        return sf

    def _createSessionObject(self, request):
        """
        Create Session object, returning SessionFormOut.
        """
        # preload necessary data items
        user_id = get_current_user_id()

        # load conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey)
        if conf.kind() != "Conference":
            raise endpoints.BadRequestException(
                "Conference key expected")

        # check if the conference has the right owner
        if conf.get().organizerUserId != user_id:
            raise endpoints.BadRequestException(
                "Only the conference owner can add sessions")

        if not request.name:
            raise endpoints.BadRequestException(
                "Session 'name' field required")

        # copy SessionFormIn/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}
        # The speaker field will be dealt with specially
        del data['speaker_key']
        # delete websafeConferenceKey
        del data['websafeConferenceKey']
        # we have to adjust the typeOfSession
        if data['typeOfSession']:
            data['typeOfSession'] = (
                str(getattr(request, 'typeOfSession')))

        # add default values for those missing
        # (both data model & outbound Message)
        for df in DEFAULTS_SESS:
            if data[df] in (None, []):
                data[df] = DEFAULTS_SESS[df]
                setattr(request, df, DEFAULTS_SESS[df])

        # add speakers
        speaker_keys = []
        for speakerform in getattr(request, 'speaker_key'):
            speaker_key = ndb.Key(urlsafe=speakerform)
            if speaker_key.kind() != "Speaker":
                raise endpoints.BadRequestException(
                    "Speaker key expected")
                # we try to get the data - is the speaker existing?
            speaker = speaker_key.get()
            if speaker is None:
                raise endpoints.BadRequestException("Speaker not found")
            speaker_keys.append(speaker_key)
        data['speaker'] = speaker_keys

        # convert dates from strings to Date objects,
        # times from strings to Time objects
        if data['date']:
            data['date'] = datetime.strptime(data['date'][:10],
                                             "%Y-%m-%d").date()
        if data['startTime']:
            data['startTime'] = datetime.strptime(data['startTime'][:5],
                                                  "%H:%M").time()

        # set session parent to conference
        data['parent'] = conf

        # create Session, search for featured speaker in a task
        session = Session(**data).put()
        taskqueue.add(
            params=
                {
                    'sessionId': str(session.id()),
                    'websafeConferenceKey': session.parent().urlsafe()
                },
            url='/tasks/search_featured_speakers'
            )

        return self._copySessionToForm(session.get())

    @ndb.transactional()
    def _updateSessionObject(self, request):
        """Update the session object."""
        user_id = get_current_user_id()

        # get the conference object
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if conf.kind() != 'Conference':
            raise endpoints.BadRequestException(
                'Provided conference key is invalid')

        # check that user is organizer
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        # get the existing session
        sess = Session.get_by_id(int(request.sessionId), parent=conf)
        # check that session exists
        if not sess:
            raise endpoints.NotFoundException(
                'No session found with id: %s' % request.sessionId)

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from SessionFormIn to Session object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('date', 'startTime'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                # special handling for speaker: convert to key
                if field.name == 'speaker':
                    data2 = []
                    for speakerform in data:
                        speaker_key = ndb.Key(urlsafe=speakerform.websafeKey)
                        if speaker_key.kind() != 'Speaker':
                            raise endpoints.BadRequestException('Expected Speaker key')
                        # check if the speaker exists
                        if speaker_key.get() is None:
                            raise endpoints.BadRequestException('Could not find speaker')
                        # set speaker key
                        data2.append(speaker_key)
                    # replace speaker forms with speaker key list
                    data = data2
                # special handling for session type
                if field.name == 'typeOfSession':
                    data = getattr(SessionType, data)
                # write to Conference object
                setattr(conf, field.name, data)
        sess.put()
        return self._copySessionToForm(sess)

    @endpoints.method(
        SESS_CREATE_REQUEST, SessionFormOut,
        path='conference/{websafeConferenceKey}/session',
        http_method='POST', name='createSession')
    def createSession(self, request):
        """Create new session in a conference."""
        return self._createSessionObject(request)

    @endpoints.method(
        SESS_POST_REQUEST, SessionFormOut,
        path='conference/{websafeConferenceKey}/session/{sessionId}',
        http_method='PUT', name='updateSession')
    def updateSession(self, request):
        """Update session with provided fields & return with updated info."""
        return self._updateSessionObject(request)

    @endpoints.method(
        SESS_GET_REQUEST, SessionFormOut,
        path='conference/{websafeConferenceKey}/session/{sessionId}',
        http_method='GET', name='getSession')
    def getSession(self, request):
        """Return requested session (by websafeConferenceKey and
            sessionId)."""
        # get the conference key
        conf = ndb.Key(urlsafe=request.websafeConferenceKey)
        if conf.kind() != 'Conference':
            raise endpoints.BadRequestException(
                'Provided conference key is invalid')
        # get Session object from request; bail if not found
        # dumpclean(request)
        sess = Session.get_by_id(int(request.sessionId), parent=conf)
        if not sess:
            raise endpoints.NotFoundException(
                'No session found with id %s' % request.sessionId)
        # return SessionFormOut
        return self._copySessionToForm(sess)

# - - - - - - - - - Session Query Methods
    def ____SESS_QUERY_PART():
        pass # marked as a divider in function tree view

    def _getSessionQuery(self, request):
        """Return formatted query from the submitted filters."""
        # check for the provided conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey)
        if conf.kind() != 'Conference':
            raise endpoints.BadRequestException(
                'Conference specified not valid')
        q = Session.query(ancestor=conf)
        inequality_filter, filters = self._formatFilters(
            request.filters, FIELDS_SESS)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Session.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Session.name)

        for filtr in filters:
            if filtr["field"] == "durationInMins":
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(
                filtr["field"],
                filtr["operator"],
                filtr["value"])
            q = q.filter(formatted_query)
        return q

    @endpoints.method(
            SESS_QUERY_FORMS, SessionForms,
            path='conference/{websafeConferenceKey}/session/query',
            http_method='POST',
            name='querySessions')
    def querySessions(self, request):
        """Query for sessions."""
        sessions = self._getSessionQuery(request)

        # return individual SessionFormOut object per Session
        return SessionForms(
                items=[self._copySessionToForm(sess)
                       for sess in sessions]
        )

    @endpoints.method(
        CONF_GET_REQUEST, SessionForms,
        path='conference/{websafeConferenceKey}/session',
        http_method='GET',
        name='getConferenceSessions')
    def getConferenceSessions(self, request):
        """Get all sessions in a conference"""
        # get the conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey)
        # is it really a conference key?
        if conf.kind() != 'Conference':
            raise endpoints.BadRequestException(
                'Provided key is not a conference key')
        # is the conference existing?
        if conf.get() is None:
            raise endpoints.NotFoundException('Conference not found')
        # get all sessions in the conference
        sessions = Session.query(ancestor=conf)
        # return individual SessionFormOut object per Session
        return SessionForms(
                items=[self._copySessionToForm(sess)
                       for sess in sessions]
        )

    @endpoints.method(
        SESS_GET_BY_TYPE, SessionForms,
        path='conference/{websafeConferenceKey}/sessionByType/{typeOfSession}',
        http_method='GET',
        name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """Get all sessions in a conference of a specific type"""
        # get the conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey)
        # is it really a conference key?
        if conf.kind() != 'Conference':
            raise endpoints.BadRequestException(
                'Provided key is not a conference key')
        # is the conference existing?
        if conf.get() is None:
            raise endpoints.NotFoundException('Conference not found')
        # get all sessions in the conference
        sessions = Session.query(ancestor=conf)
        # and filter by session type
        sessions = sessions.filter(Session.typeOfSession == request.typeOfSession)
        # return individual SessionFormOut object per Session
        return SessionForms(
                items=[self._copySessionToForm(sess)
                       for sess in sessions]
        )

    @endpoints.method(
        SESS_GET_ALL_BY_SPEAKER, SessionForms,
        path='speaker/{websafeSpeakerKey}/session',
        http_method='GET',
        name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        """Get all sessions with a specified speaker"""
        # get the speaker
        speaker = ndb.Key(urlsafe=request.websafeSpeakerKey)
        # is it really a speaker key?
        if speaker.kind() != 'Speaker':
            raise endpoints.BadRequestException(
                'Provided key is not a speaker key')
        # is the speaker existing?
        if speaker.get() is None:
            raise endpoints.NotFoundException('Speaker not found')
        # get all sessions with this speaker
        sessions = Session.query(Session.speaker == speaker)
        # return individual SessionFormOut object per Session
        return SessionForms(
                items=[self._copySessionToForm(sess)
                       for sess in sessions]
        )

    def ____TWO_ADDITIONAL_QUERY():
        pass # marked as a divider in function tree view

    @endpoints.method(
        SESS_GET_BY_HIGHLIGHT, SessionForms,
        path='conference/{websafeConferenceKey}/byHighlight/{highlight}',
        http_method='GET',
        name='getConferenceSessionsByHighlight')
    def getConferenceSessionsByHighlight(self, request):
        """Get all conference sessions with a specified highlight"""
        # get the conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey)
        # is it really a conference key?
        if conf.kind() != 'Conference':
            raise endpoints.BadRequestException(
                'Provided key is not a conference key')
        # is the conference existing?
        if conf.get() is None:
            raise endpoints.NotFoundException('Conference not found')
        # get all sessions in the conference
        sessions = Session.query(ancestor=conf)
        # and filter by highlight
        sessions = sessions.filter(Session.highlight == request.highlight)
        # return individual SessionFormOut object per Session
        return SessionForms(
                items=[self._copySessionToForm(sess)
                       for sess in sessions]
        )

    @endpoints.method(
        SESS_GET_BY_LOCATION, SessionForms,
        path='conference/{websafeConferenceKey}/byLocation/{location}',
        http_method='GET',
        name='getConferenceSessionsByLocation')
    def getConferenceSessionsByLocation(self, request):
        """Get all conference sessions with a specified location"""
        # get the conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey)
        # is it really a conference key?
        if conf.kind() != 'Conference':
            raise endpoints.BadRequestException(
                'Provided key is not a conference key')
        # is the conference existing?
        if conf.get() is None:
            raise endpoints.NotFoundException('Conference not found')
        # get all sessions in the conference
        sessions = Session.query(ancestor=conf)
        # and filter by highlight
        sessions = sessions.filter(Session.location == request.location)
        # return individual SessionFormOut object per Session
        return SessionForms(
                items=[self._copySessionToForm(sess)
                       for sess in sessions]
        )

# - - - Profile objects - - - - - - - - - - - - - - - - - - -
    def ____PROFILE_PART():
        pass # marked as a divider in function tree view

    def _copyProfileToForm(self, prof):
        """Copy relevant fields from Profile to ProfileForm."""
        # copy relevant fields from Profile to ProfileForm
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name, getattr(TeeShirtSize, getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf


    def _getProfileFromUser(self):
        """Return user Profile from datastore, creating new one if non-existent."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Profile from datastore
        user_id = getUserId(user)
        p_key = ndb.Key(Profile, user_id)
        profile = p_key.get()
        # create new Profile if not there
        if not profile:
            profile = Profile(
                key = p_key,
                displayName = user.nickname(),
                mainEmail= user.email(),
            )
            profile.put()

        return profile      # return Profile


    def _doProfile(self, save_request=None):
        """Get user Profile and return to user, possibly updating it first."""
        # get user Profile
        prof = self._getProfileFromUser()

        # if saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
                        #if field == 'teeShirtSize':
                        #    setattr(prof, field, str(val).upper())
                        #else:
                        #    setattr(prof, field, val)
            prof.put()

        # return ProfileForm
        return self._copyProfileToForm(prof)

    @endpoints.method(message_types.VoidMessage, ProfileForm,
            path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return self._doProfile()

    @endpoints.method(ProfileMiniForm, ProfileForm,
            path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        """Update & return user profile."""
        return self._doProfile(request)


# - - - Registration - - - - - - - - - - - - - - - - - - - -
    def ____CONF_REGISTRATION_PART():
        pass # marked as a divider in function tree view

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        retval = None
        prof = self._getProfileFromUser() # get user Profile

        # check if conf exists given websafeConfKey
        # get conference; check that it exists
        wsck = request.websafeConferenceKey
        conf = ndb.Key(urlsafe=wsck).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)

        # register
        if reg:
            # check if user already registered otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")

            # register user, take away one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            retval = True

        # unregister
        else:
            # check if user already registered
            if wsck in prof.conferenceKeysToAttend:

                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='conferences/attending',
            http_method='GET', name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""
        prof = self._getProfileFromUser() # get user Profile
        conf_keys = [ndb.Key(urlsafe=wsck) for wsck in prof.conferenceKeysToAttend]
        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[self._copyConferenceToForm(conf, names[conf.organizerUserId])\
         for conf in conferences]
        )


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='POST', name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='DELETE', name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference."""
        return self._conferenceRegistration(request, reg=False)


# - - - Wishlist - - - - - - - - - - - - - - - - - - - -
    def ____WISH_LIST_PART():
        pass # marked as a divider in function tree view

    @ndb.transactional()
    def _sessionWishlist(self, request, reg=True):
        """Add a session to the wishlist."""
        retval = None
        prof = self._getProfileFromUser()  # get user Profile
        # get the conference key
        conf = ndb.Key(urlsafe=request.websafeConferenceKey)
        if conf.kind() != 'Conference':
            raise endpoints.BadRequestException(
                'Provided conference key is invalid')
        # check if session exists given sessionId
        session = Session.get_by_id(int(request.sessionId), parent=conf)
        # get session; check that it exists
        if not session:
            raise endpoints.NotFoundException(
                'No session found with id %s' % request.sessionId)
        # get web safe session key
        wssk = session.key.urlsafe()

        # add to wishlist
        if reg:
            # check if user already has session otherwise add
            if wssk in prof.sessionKeysOnWishlist:
                raise ConflictException(
                    "You have already this session in your wishlist")

            # add to wishist
            prof.sessionKeysOnWishlist.append(wssk)
            retval = True

        # remove from wishlist
        else:
            # check if user has entry in wishlist
            if wssk in prof.sessionKeysOnWishlist:

                # remove session from wishlist
                prof.sessionKeysOnWishlist.remove(wssk)
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        return BooleanMessage(data=retval)

    @endpoints.method(
            message_types.VoidMessage, SessionForms,
            path='wishlist',
            http_method='GET', name='getSessionsInWishlist')
    def getSessionsInWishlist(self, request):
        """Get list of sessions that user has on their wishlist."""
        prof = self._getProfileFromUser()  # get user Profile
        sess_keys = [ndb.Key(urlsafe=wssk)
                     for wssk in prof.sessionKeysOnWishlist]
        sessions = ndb.get_multi(sess_keys)

        # return set of SessionFormOut objects per Session
        return SessionForms(items=[
            self._copySessionToForm(sess)
            for sess in sessions]
        )

    @endpoints.method(
            SESS_GET_REQUEST, BooleanMessage,
            path='wishlist/{websafeConferenceKey}/session/{sessionId}',
            http_method='POST', name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        """Add session to user's wishlist."""
        return self._sessionWishlist(request)

    @endpoints.method(
            SESS_GET_REQUEST, BooleanMessage,
            path='wishlist/{websafeConferenceKey}/session/{sessionId}',
            http_method='DELETE', name='deleteSessionInWishlist')
    def deleteSessionInWishlist(self, request):
        """Remove session from user's wishlist."""
        return self._sessionWishlist(request, reg=False)

    def ___QUERY_PROBLEM():
        pass # marked as a divider in function tree view

    @endpoints.method(CONF_GET_REQUEST,
                      SessionForms,
                      path='conference/{websafeConferenceKey}/queryproblem',
                      http_method='GET',
                      name='queryProblem')
    def queryProblem(self, request):
        """query sessions for all non-workshop sessions before 7 pm"""
        # get the conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey)
        # is it really a conference key?
        if conf.kind() != 'Conference':
            raise endpoints.BadRequestException(
                'Invalid conference key')
        # is the conference existing?
        if conf.get() is None:
            raise endpoints.NotFoundException('Conference not found')
        # get all sessions in the conference
        sessions = Session.query(ancestor=conf)
        # filter by start time
        sessions = sessions.filter(
            Session.startTime < datetime.strptime("19:00", "%H:%M").time())
        # get the sessions and filter in python
        filtered_sessions = [
            session for session in sessions.fetch()
            if session.typeOfSession != "WORKSHOP"]
        # filter by start time not None
        filtered_sessions = [
            session for session in filtered_sessions if session.startTime]
        # return individual SessionFormOut object per Session
        return SessionForms(
            items=[self._copySessionToForm(session)
                   for session in filtered_sessions])

# - - - Announcements - - - - - - - - - - - - - - - - - - - -
    def ____ANNOUNCE_PART():
        pass # marked as a divider in function tree view

    # _TODO 1 static method to set cache; used by main.SetAnnouncementHandler
    @staticmethod
    def _cacheAnnouncement():
        """Create Announcement & assign to memcache; used by
        memcache cron job & putAnnouncement().
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])

        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = '%s %s' % (
                'Last chance to attend! The following conferences '
                'are nearly sold out:',
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

        return announcement

    @endpoints.method(message_types.VoidMessage,
                      StringMessage,
                      path='conference/announcement/get',
                      http_method='GET',
                      name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        # _TODO 1
        # return an existing announcement from Memcache or an empty string.
        announcement = memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY)
        if not announcement:
            announcement = ""
        return StringMessage(data=announcement)

#  - - - - - - Feature Speaker - - - - - -
    def ____FEATURE_SPEAKER():
        pass # marked as a divider in function tree view

    @staticmethod
    def _cacheFeaturedSpeaker(websafeConferenceKey, sessionId):
        """Search for featured speaker & assign to memcache; used by
        main.SearchFeaturedSpeakers
        """
        logging.info("_cacheFeaturedSpeaker: Checking for featured speakers in %s %s\n"
            % (websafeConferenceKey, sessionId))
        # get the conference
        conf = ndb.Key(urlsafe=websafeConferenceKey)
        if conf.kind() != 'Conference':
            # raising an exception causes another attempt at calling the task
            logging.error("_cacheFeaturedSpeaker: provided conference key %s invalid"
                % websafeConferenceKey)
            return
        # get the session; check if it exists
        session = Session.get_by_id(int(sessionId), parent=conf)
        if not session:
            # raise endpoints.NotFoundException('Provided session not found')
            # raising an exception causes another attempt at calling the task
            logging.error("_cacheFeaturedSpeaker: provided session id not found %d"
                % sessionId)
            return
        # Now check the speakers in the session
        for speaker in session.speaker:
            logging.info("_cacheFeaturedSpeaker: speaker %s in check"
                % speaker.urlsafe())
            sessions = Session.query(Session.speaker == speaker) \
                              .fetch(projection=[Session.name])
            logging.info("_cacheFeaturedSpeaker: %s sessions found" % len(sessions))
            if len(sessions) > 1:
                speaker = speaker.get()
                # good - let's feature the speaker!
                feature = FEATUREDSPEAKER_TPL % (
                    speaker.name,
                    ', '.join(sess.name for sess in sessions))
                # set into memcache
                memcache.set(MEMCACHE_FEATUREDSPEAKER_KEY, feature)
                # we are done and return already
                logging.info("_cacheFeaturedSpeaker: we found something\n%s" % feature)
                return feature


    @endpoints.method(
            message_types.VoidMessage, StringMessage,
            path='featured_speaker',
            http_method='GET', name='getFeaturedSpeaker')
    def getFeaturedSpeaker(self, request):
        """Return featured speaker from memcache."""
        return StringMessage(
            data=memcache.get(MEMCACHE_FEATUREDSPEAKER_KEY) or "")


api = endpoints.api_server([ConferenceApi]) # register API
