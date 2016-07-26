from flask import Flask, jsonify, abort, make_response, request
import json
from firebase import firebase
import sys
from soupTest import SoupTest

app = Flask(__name__)

# Firebase information - LETS REFACTOR ALL THE FIREBASE STUFF LATER (possibly do it all while accessing the information the first time)
firebaseSecret = "mEFDPnrvKMXMV5gecJYGIfabRROmInyQxx1pKb64"
firebaseRoot = "https://project-2848401830613063315.firebaseio.com/"

# Connect to the Firebase database so that we can push the data to create the initial info needed for the races
authentication = firebase.FirebaseAuthentication(firebaseSecret, "WHATRDOOOOSE")
db = firebase.FirebaseApplication(firebaseRoot, authentication)

# Create a souptest which will be used to scrape multiGP as necessary
scraper = SoupTest()

@app.route("/")
def index():
    return "Hello, World!"

@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({"error": "Not found"}), 404)

# For veryifing if this is a real MultiGP user and figuring out their username
@app.route("/verify", methods=["POST"])
def verify_information():
    if not request.form or not "email" in request.form or not "password" in request.form:
        abort(400)
    result = scraper.verifyLogin(request.form["email"], request.form["password"])
    if result != None:
        return jsonify({"result": "success", "username": result})
    else:
        return jsonify({"result": "failed", "username": "failed"})

# Returns all the events this user has been added to or chosen to follow
@app.route("/users/<username>/events", methods=["GET"])
def get_user_events(username):
    userEventsIds = db.get("/users/{}/events".format(username), None)
    userEvents = {}
    if (userEventsIds != None):
        for eventId in userEventsIds:
            event = db.get("/events/{}".format(eventId), None)
            userEvents[eventId] = event
    return jsonify(userEvents)

# Creates a new guest ID and returns it to use in place of unique username
@app.route("/newguest", methods=["GET"])
def create_guest():
    result = db.post("/guests", {"filler": "filler"})
    return jsonify(result)

# Returns all the events this guest is trying to follow
@app.route("/guests/<username>/events", methods=["GET"])
def get_guest_events(username):
    userEventsIds = db.get("/guests/{}/events".format(username), None)
    userEvents = {}
    if (userEventsIds != None):
        for eventId in userEventsIds:
            event = db.get("/events/{}".format(eventId), None)
            userEvents[eventId] = event
    return jsonify(userEvents)
    
# Returns the entire race
@app.route("/events/<eventId>", methods=["GET"])
def get_event(eventId):
    event = db.get("/events/{}".format(eventId), None)
    if (event == None):
        abort(404)
    return jsonify(event)

# Scrapes the MultiGP site to create a brand new race
@app.route("/add/event", methods=["POST"])
def add_event():
    if request.json:
        url = request.json["url"]
        username = request.json["username"]
        usertype = request.json["usertype"]
        eventId = check_event_exists(url)
    elif request.form:
        url = request.form["url"]
        username = request.form["username"]
        usertype = request.form["usertype"]
        eventId = check_event_exists(url)
    else:
        abort(400)

    if eventId:
        if usertype == "multigp":
            db.patch("/users/{}/events".format(username), {eventId: "true"})
        elif usertype == "guest":
            db.patch("/guests/{}/events".format(username), {eventId: "true"})
        else:
            abort(400)
        return get_event(eventId)
    else:
        data = scraper.scrapeMultiGPURL(url)
        eventId = scraper.createRaceFromScrapedData(data)
        if usertype == "multigp":
            db.patch("/users/{}/events".format(username), {eventId: "true"})
        elif usertype == "guest":
            db.patch("/guests/{}/events".format(username), {eventId: "true"})
        else:
            abort(400)
        return get_event(eventId), 201

# Checks Firebase to see if an event already exists or not to figure out if we need to scrape it
def check_event_exists(url):
    eventId = db.get("/{}".format(url.strip("http://www.multigp.com/")), None)
    if eventId:
        return eventId["id"]
    else:
        return None

# Gets the Event ID because I'm an idiot
@app.route("/getEventIdFromURL/<path:url>", methods=["GET"])
def get_event_id_from_url(url):
    return jsonify(db.get(url, None))

# Updates the status of the race so that everyone can receive push notification
@app.route("/update/race/status/<path:url>", methods=["POST"])
def update_race_status(url):
    if not request.form or not "status" in request.form or not "racing" in request.form or not "spotting" in request.form or not "ondeck" in request.form or not "time" in request.form:
        abort(400)
    eventId = db.get(url, None)
    eventId = eventId["id"]
    db.patch("/events/{}".format(eventId), {"status": {"status": request.form["status"], "racing": request.form["racing"], "spotting":  request.form["spotting"], "ondeck": request.form["ondeck"], "time": request.form["time"]}})
    return jsonify({"result": "success"})

# Updates the structure for things like points or slot changes
@app.route("/update/race/structure/<path:url>", methods=["POST"])
def update_race_structure(url):
    if not request.form:
        abort(400)
    eventId = db.get(url, None)
    eventId = eventId["id"]
    db.patch("/events/{}/raceStructure/{}/{}/{}".format(eventId, request.form["round"], request.form["heat"], request.form["slotKey"]), {"username": request.form["username"], "frequency": request.form["frequency"], "points": request.form["points"]})
    return jsonify({"result": "success"})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
