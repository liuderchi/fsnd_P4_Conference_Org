# Test Plan of Conference Organizer

## prepare data

  - create a conference with name: __myconf__
      - ```conference.createConference()```
          - Request Body
              - name: "__myconf__"
  - get conference key
      - ```conference.getConferencesCreated()```
      - copy websafeKey as *confKey* in Response
          - e.g. ag1zfm5kLWNvbmYtb3JncjILEgdQcm9maWxlIhNsaXVkZXJjaGlAZ21haWwuY29tDAsSCkNvbmZlcmVuY2UYoZwBDA

  - create speaker
      - ```conference.getConferencesCreated()```
      - Request Body
          - name: "__myspeaker__"
      - copy websafeKey as *speakerKey* in Response
      - e.g. ag1zfm5kLWNvbmYtb3JncjQLEgdQcm9maWxlIhNsaXVkZXJjaGlAZ21haWwuY29tDAsSB1NwZWFrZXIYgICAgOCslAoM

## Task 1.1  createSession()

  - create session as *session_A*
      - websafeConferenceKey: *confKey* in previous step
      - Request Body
          - name: "session_A"
          - typeOfSession: "WORKSHOP"
          - location: "workshop location"
          - speaker_key: [ *speakerKey* ]
          - startTime: "11:00"
      - copy sessionId as *session_A_id* in Response
          - e.g. 5689792285114368

  - create session as *session_B*
      - websafeConferenceKey: *confKey* in previous step
      - Request Body
          - name: "session_B"
          - typeOfSession: "LECTURE"
          - highlight: [ "lecture highlight" ]
          - speaker_key: [ *speakerKey* ]
          - startTime: "11:00"
     - copy sessionId as *session_B_id* in Response
         - e.g. 5754903989321728

## Task 1.2  getConferenceSessions()

  - ```conference.getConferenceSessions()```
      - websafeConferenceKey: *confKey* in previous step
      - Request Body: None

## Task 1.3 conference.getConferenceSessionsByType()

  - ```conference.getConferenceSessionsByType()```
      - websafeConferenceKey: *confKey* in previous step
      - typeOfSession: "WORKSHOP"
      - Request Body: None

  - ```conference.getConferenceSessionsByType()```
      - websafeConferenceKey: *confKey* in previous step
      - typeOfSession: "LECTURE"
      - Request Body: None

## Task 1.4  conference.getSessionsBySpeaker()

  - ```conference.getSessionsBySpeaker()```
      - websafeSpeakerKey: *speakerKey* in previous step
      - Request Body: None

## Task 2 Wishlist

  - ```conference.addSessionToWishlist()```
      - websafeConferenceKey: *confKey* in previous step
      - sessionid: *session_A_id* in previous step
      - Request Body: None

  - ```conference.getSessionsInWishlist()```
      - Request Body: None

  - ```conference.deleteSessionInWishlist()```
      - websafeConferenceKey: *confKey* in previous step
      - sessionid: *session_A_id* in previous step
      - Request Body: None

  - ```conference.getSessionsInWishlist()```
      - Request Body: None

## Task 3.1 Two New Queries

  - ```conference.getConferenceSessionsByLocation()```
      - websafeConferenceKey: *confKey* in previous step
      - location: "workshop location"
      - Request Body: None

  - ```conference.getConferenceSessionsByHighlight()```
      - websafeConferenceKey: *confKey* in previous step
      - highlight: "lecture highlight"
      - Request Body: None

## Task 3.2 Query Problem

  - ```conference.queryProblem()```
      - websafeConferenceKey: *confKey* in previous step
      - Request Body: None
  - should only get *session_B*

# Task 4 feature speaker

  - ```conference.getFeaturedSpeaker()```
      - Request Body: None
  - expect response.data:
      - "Speaker __myspeaker__ is our feature speaker, will appear in these sessions: session_A, session_B",
