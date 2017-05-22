# Udacity Conference Organizer README

An conference organizer app to help you schedule your conferences.
Deployed on Google Cloud Platform using and implemented by Python mostly.

![screenshot][screenshot]


This is a README of Udacity Nanodegree Project 4.
This file is response to [project problems.](https://www.udacity.com/course/viewer#!/c-nd004/l-3566359178/m-3636408594)

## Environment

  - OS: win7 x64
  - python 2.7
  - Google App Engine: SDK 1.9.32.

## Setup Instructions

  1. clone this project and replace some values with your own GAE app-id
      - 'application' of ```app.yaml```  -> your own GAE app-id
      - 'WEB_CLIENT_ID' of ```settings.py``` -> your client-id from developer_console.API_manager.Credentials
      - CLIENT_ID (line 89) of ```static/js/app.js``` -> your client-id from developer_console.API_manager.Credentials

  2. run the app in Google App Engine GUI

  3. deploy app

  4. test the app in API Explorer
      - url: ```http://<your-app-id>.appspot.com/_ah/api/explorer```
      - my deployment:  ```http://http://nd-conf-org.appspot.com/_ah/api/explorer```
      - I've prepared a brief test flow through Task_1 to Task_4, recording in [TEST_PLAN.md](TEST_PLAN.md)


## Task 1. Design Choice

  - In order to reuse the existing code of conference app Model, I added model ```Speaker``` as child kind of ```Profile```
      - ```Speaker``` entity is defined with name and websafe key
  - ```Session``` is added as a child kind of ```Conference```.
      - I use KeyProperty for indexing speakers in the session entity by storing speakers entity datastore key.
      - time-related properties, use DateProperty, TimeProperty, and IntegerProperty
      - Other property uses StringProperty
  - ```sessionKeysOnWishlist``` is a property of user profile kind, where it's a list of sessions.
  - five models update operation require transactional
      - update of conference
      - update of speaker
      - update of session
      - attending to a conference
      - add a session to wishlist

## Task 3. Additional Queries and Query Problem

  - indexes for querying are defined in `index.yaml`
  - Two Additional Queries
      1. getConferenceSessionsByHighlight()
          - supporting user to query session with highlight string
      2. getConferenceSessionsByLocation()
          - supporting user to query session with location string
  - Query Problem
      - Since the feature of datastore indexes, we cannot develop a query with two inequality filters on two different queries
      - We need to avoid second inequality filter

```python
# solution 1: using list comprehension
ans = [session for session in sessions.fetch()
      if session.typeOfSession != "WORKSHOP"]

# solution 2: using IN-operator
ans = sessions.filter(
    Session.typeOfSession.IN(
    ["NOT_SPECIFIED", "LECTURE", "KEYNOTE", "CODELAB"])```
```

  - since typeOfSession is not in fixed format, using solution 1 is better
      - this is implemented in `queryProblem()` in `conference.py`



[screenshot]: https://cloud.githubusercontent.com/assets/4994705/26309672/6fe3befe-3f30-11e7-9072-b222db382652.png "screenshot"
