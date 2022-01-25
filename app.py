#!/usr/bin/env python
#  -*- coding: utf-8 -*-
"""
Copyright (c) 2021 Cisco and/or its affiliates.

This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at

               https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.

This sample script leverages the Flask web service micro-framework
(see http://flask.pocoo.org/).  By default the web server will be reachable at
port 5000 you can change this default if desired (see `app.run(...)`).

"""


from dotenv import load_dotenv

__author__ = "Gerardo Chaves"
__author_email__ = "gchaves@cisco.com"
__copyright__ = "Copyright (c) 2016-2022 Cisco and/or its affiliates."
__license__ = "Cisco"

from requests_oauthlib import OAuth2Session

from flask import Flask, request, redirect, session, url_for, render_template, make_response, jsonify
from flask_socketio import SocketIO, send, emit, join_room, leave_room

import requests
import os
import time
import json

from webexteamssdk import WebexTeamsAPI, Webhook, AccessToken, ApiError

# load all environment variables
load_dotenv()

AUTHORIZATION_BASE_URL = 'https://api.ciscospark.com/v1/authorize'
TOKEN_URL = 'https://api.ciscospark.com/v1/access_token'
SCOPE = ['spark:people_read','spark:calls_read','spark:calls_write']


AUTH_BASE_ADDRESS=os.getenv('AUTH_BASE_ADDRESS')
WEBHOOK_BASE_ADDRESS=os.getenv('WEBHOOK_BASE_ADDRESS')

#initialize variabes for URLs
REDIRECT_URI = AUTH_BASE_ADDRESS + '/callback'
WEBHOOK_ADDRESS=WEBHOOK_BASE_ADDRESS+'/callevent'

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
# Initialize the environment
# Create the web application instance
app = Flask(__name__)
socketio = SocketIO(app)

app.secret_key = '123456789012345678901234'
#api = WebexTeamsAPI(access_token=TEST_TEAMS_ACCESS_TOKEN)
api = None

@app.route("/")
def welcome():
    #grab the arguments to use when re-directing to the CRM, if any
    crmbase = request.args.get('crmbase', default='', type=str).replace('"', '').replace("'", '')
    crmargs = request.args.get('crmargs', default='', type=str).replace('"', '').replace("'", '')
    print(f"before rendering welcome: CRM Base={crmbase} , CRM Args={crmargs}")
    return render_template('welcome.html', hiddenLinks=False, crmbase=crmbase, crmargs=crmargs)

@app.route("/login")
def login():
    """Step 1: User Authorization.
    Redirect the user/resource owner to the OAuth provider (i.e. Webex Teams)
    using a URL with a few key OAuth parameters.
    """
    global REDIRECT_URI
    global AUTH_BASE_ADDRESS

    #grab the arguments to use when re-directing to the CRM, if any
    crmbase = request.args.get('crmbase', default='', type=str).replace('"', '').replace("'", '')
    crmargs = request.args.get('crmargs', default='', type=str).replace('"', '').replace("'", '')

    session['crmbase']=crmbase
    session['crmargs']=crmargs

    print(f"After going into login CRM Base={crmbase} , CRM Args={crmargs}")


    # trigger a full oAuth flow with user intervention
    print("Using AUTH_BASE_ADDRESS: ",AUTH_BASE_ADDRESS)
    print("Using redirect URI: ",REDIRECT_URI)
    teams = OAuth2Session(os.getenv('CLIENT_ID'), scope=SCOPE, redirect_uri=REDIRECT_URI)
    authorization_url, state = teams.authorization_url(AUTHORIZATION_BASE_URL)

    # State is used to prevent CSRF, keep this for later.
    print("Storing state: ",state)
    session['oauth_state'] = state
    print("root route is re-directing to ",authorization_url," and had sent redirect uri: ",REDIRECT_URI)
    return redirect(authorization_url)
    #resp = jsonify(success=True)
    #return resp

@app.route("/callback", methods=["GET"])
def callback():
    """
    Step 3: Retrieving an access token.
    The user has been redirected back from the provider to your registered
    callback URL. With this redirection comes an authorization code included
    in the redirect URL. We will use that to obtain an access token.
    """
    global REDIRECT_URI

    print("Came back to the redirect URI, trying to fetch token....")
    print("redirect URI should still be: ",REDIRECT_URI)
    print("Calling OAuth2SEssion with CLIENT_ID ",os.getenv('CLIENT_ID')," state ",session['oauth_state']," and REDIRECT_URI as above...")
    auth_code = OAuth2Session(os.getenv('CLIENT_ID'), state=session['oauth_state'], redirect_uri=REDIRECT_URI)
    print("Obtained auth_code: ",auth_code)
    print("fetching token with TOKEN_URL ",TOKEN_URL," and client secret ",os.getenv('CLIENT_SECRET')," and auth response ",request.url)
    token = auth_code.fetch_token(token_url=TOKEN_URL, client_secret=os.getenv('CLIENT_SECRET'),
                                  authorization_response=request.url)

    print("Token: ",token)
    print("should have grabbed the token by now!")
    session['oauth_token'] = token
    return redirect(url_for('.userconnect'))

@app.route("/callevent", methods=["GET", "POST"])
def callevent():

    # Use returned token to make Teams API calls for information on user, list of spaces and list of messages in spaces
    print("Webhook was invoked! ")
    global api


    request_data = request.get_json()
    request_headers=request.headers
    #print("Request headers: ",request_headers)
    #print("Request data: ", request_data)
    #Request data:  {'id': 'Y2lzY29zcGFyazovL3VybjpURUFNOnVzLXdlc3QtMl9yL1dFQkhPT0svYWQxZDI5NTAtYWQ2OS00ZDIzLThlOTMtNjJiOGMzMDJiYTg0', 'name': 'WbxCallCRM', 'targetUrl': 'https://df63-179-50-245-41.ngrok.io/callevent', 'resource': 'telephony_calls', 'event': 'created', 'orgId': 'Y2lzY29zcGFyazovL3VzL09SR0FOSVpBVElPTi85YjVjYmJmNi1mOWJjLTQyZWYtYTIwYy0xNDAyOGIyNTM3MmI', 'createdBy': 'Y2lzY29zcGFyazovL3VzL1BFT1BMRS8xNzM3NDg2Ny0xYmUyLTQwODAtYTIzOC0yYjU2ZDg5MGExYzk', 'appId': 'Y2lzY29zcGFyazovL3VzL0FQUExJQ0FUSU9OL0MwMDU4YmVjNjQyOWRjZWFjYTUxMDU3ZDQ3OGJlYjJmZTNmZDUxZmNiZjIyNjg2NmNiMWI4NWVlZGU1Mzc0NzZl', 'ownedBy': 'creator', 'status': 'active', 'created': '2021-12-09T00:15:15.491Z', 'actorId': 'Y2lzY29zcGFyazovL3VzL1BFT1BMRS8xNzM3NDg2Ny0xYmUyLTQwODAtYTIzOC0yYjU2ZDg5MGExYzk', 'data': {'eventType': 'received', 'eventTimestamp': '2021-12-09T00:20:58.929Z', 'callId': 'Y2lzY29zcGFyazovL3VybjpURUFNOnVzLXdlc3QtMl9yL0NBTEwvY2FsbGhhbGYtMzM3MjE3MDA5OjA', 'callSessionId': 'ZDRiNDA4ODctOWY5OS00M2Y0LWI1NWUtYmFkMjJmMTdhMmNj', 'personality': 'terminator', 'state': 'alerting', 'remoteParty': {'name': '+50622013643', 'number': '+50622013643', 'privacyEnabled': False, 'callType': 'external'}, 'appearance': 1, 'created': '2021-12-09T00:20:58.928Z'}}
    if 'state' in request_data['data'] and request_data['data']['state']=='alerting':
        callerName=request_data['data']['remoteParty']['name']
        callerNumber=request_data['data']['remoteParty']['number']
        print("Caller ID Name: ",callerName," and number: ",callerNumber)
        calledPersonID=request_data['actorId']
        # send the event to the apropriate web page which is via the websocket "room" named after the UserID
        print(f"Trying to send caller number {callerNumber} and caller name {callerName} to {calledPersonID}")
        send("calloffering,"+callerNumber+","+callerName, to=calledPersonID, namespace="")

    resp = jsonify(success=True)
    return resp

@app.route("/crmtest")
def crmtest():
    theNumber = request.args.get('calleridnumber', default='', type=str)
    theName = request.args.get('calleridname', default='', type=str)
    return render_template('crmtest.html', hiddenLinks=False,number=theNumber, name=theName)

@app.route("/userconnect")
def userconnect():
    # Use returned token to make Teams API calls for information on user, list of spaces and list of messages in spaces
    global api

    teams_token = session['oauth_token']
    crmbase = session['crmbase']
    crmargs = session['crmargs']
    print(f"After going into /userconnect CRM Base={crmbase} , CRM Args={crmargs}")

    api = WebexTeamsAPI(access_token=teams_token['access_token'])

    # first retrieve information about who is logged in
    theResult = api.people.me()
    print("TheResult calling api.people.me(): ", theResult)
    session['wbxuserid'] = theResult.id

    userName=theResult.displayName
    phoneNums=theResult.phoneNumbers()
    for n in phoneNums:
        theNumber=n['value']
    print(theNumber)
    # first check to see if we have a webhook for that user, if so, they are already "connected" so we just
    # need to create/refresh the DB entry with the new connection object we just created above.
    connected = False

    # now pass the webhook connection state and base and args to the template
    return render_template('userconnect.html', hiddenLinks=False, crmbase=crmbase, crmargs=crmargs, connected=connected, name=userName, phonenumber=theNumber )



@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')
    # delete webhook for this user, if they had created it already
    global api
    teams_token = session['oauth_token']
    api = WebexTeamsAPI(access_token=teams_token['access_token'])
    try:
        theWebhooks = api.webhooks.list()
        theWHID = ''
        for wh in theWebhooks:
            if wh.name == "WbxCallCRM":
                theWHID = wh.id
        if theWHID != '':
            api.webhooks.delete(theWHID)
            print("webhook deleted!")
        else:
            print("No CRM WebHook found for this user to delete upon closing connection")
    except ApiError as e:
        print("some other error trying to manipulate webhook...")
        print(e)

@socketio.on('message')
def handle_message(message):
    print('received message: ' + message)
    if message=='connect' or message=='disconnect':
        theResponse="Received command: "+message
        if message=='connect':
            join_room(session['wbxuserid'], namespace="")

            # create or update webhook for this user
            global api
            teams_token = session['oauth_token']
            api = WebexTeamsAPI(access_token=teams_token['access_token'])
            try:
                # register webhook to recieve Webex Calling events for new calls
                theWebhooks = api.webhooks.list()
                theWHID = ''
                for wh in theWebhooks:
                    if wh.name == "WbxCallCRM":
                        theWHID = wh.id

                # if we find a webhook called "WbxCallCRM" for this user, then update it with the latest destination URL
                if theWHID != '':
                    api.webhooks.update(theWHID, name="WbxCallCRM", targetUrl=WEBHOOK_ADDRESS)
                    print("webhook updated!")
                    theSuccessMessage = "CMR WebHook has been updated, they are now received here: " + WEBHOOK_ADDRESS
                else:
                    # if a webhook called "WbxCallCRM" is not found, create it!
                    api.webhooks.create("WbxCallCRM", WEBHOOK_ADDRESS, resource='telephony_calls', event='created')
                    print("webhook created!")
                    theSuccessMessage = "CMR WebHook has been created, they are received here: " + WEBHOOK_ADDRESS
                send(theSuccessMessage, broadcast=False)
            except ApiError as e:
                print("some other error trying to manipulate webhook...")
                print(e)



        else:
            #Erase webhook when "disconnect" message is received
            try:
                theWebhooks = api.webhooks.list()
                theWHID = ''
                for wh in theWebhooks:
                    if wh.name == "WbxCallCRM":
                        theWHID = wh.id
                if theWHID!='':
                    api.webhooks.delete(theWHID)
                    print("webhook deleted!")
                    theSuccessMessage = "CMR WebHook has been deleted."
                else:
                    theSuccessMessage = "No CRM WebHook found for this user to delete."
                send(theSuccessMessage, broadcast=False)
            except ApiError as e:
                print("some other error trying to delete webhook...")
                print(e)

            leave_room(session['wbxuserid'], namespace="")



# Start the Flask web server
if __name__ == '__main__':

    print("Using AUTH_BASE_ADDRESS: ",AUTH_BASE_ADDRESS)
    print("Using redirect URI: ",REDIRECT_URI)
    #app.run(host='0.0.0.0', port=5000, debug=True)
    socketio.run(app,host='0.0.0.0', port=5000)