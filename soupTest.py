from bs4 import BeautifulSoup
import requests
import urllib2
import cookielib
import mechanize
import json
from firebase import firebase

class SoupTest:
    
    def __init__(self):
        # User info to log in to site so that race data is actually displayed
        # Specific racing information (rounds, heats, etc.) are hidden by MultiGP if not logged in
        self.useremail = "omgwtflolbbl@gmail.com"
        self.password = "omgwtflolbbl7!!"
        self.loginURL = "http://www.multigp.com/user/site/login"
        self.setupBrowser()

    def setupBrowser(self):
        # Setup cookies and browser
        cj = cookielib.CookieJar()
        browser = mechanize.Browser()
        #browser.set_debug_http(True)
        #browser.set_debug_responses(True)
        browser.set_cookiejar(cj)

        # Navigate to login and find the login form by iterating all formss
        browser.open(self.loginURL)
        for form in browser.forms():
            if form.attrs["id"] == "login-form":
                browser.form = form
                break

        # The login forms are implemented strange and mechanize does not seem to interact properly with the email text control
        # Solution is to add a new text control with the proper name ("LoginForm[username]") so that it can be sent in POST
        browser.form.new_control("text", "LoginForm[username]", {"value": ""})
        browser.form.fixup()
        browser["LoginForm[username]"] = self.useremail
        browser["LoginForm[password]"] = self.password
        print browser
        browser.submit()
        self.browser = browser
        

    def scrapeMultiGPURL(self, url):
        # URL for the actual event we want to grab data from
        eventURL = url #"http://www.multigp.com/races/view/2005/Texas-Regional-Qualifier---Houston"

        # Navigate to the event page and initialize BeautifulSoup so that we can start scraping the site
        browser = self.browser
        browser.open(eventURL)
        soup = BeautifulSoup(browser.response().read(), "html5lib")
        # Get the title of the event
        # The [:-2] is used to remove the "Public/Private Event" also joined in the <h1> tag
        title = soup.find("h1", itemprop="name").text
        title = " ".join(title.split()[:-2])
        #print title

        # Get the date of the event
        date = soup.find("span", itemprop="startDate").text
        #print date

        # Get the start time of the event
        time = soup.find("div", itemprop="event").find("small").text
        time = time.strip("@ ")
        #print time

        # Get the blockquote description
        blockquote = soup.find("blockquote", itemprop="description")
        if (blockquote == None):
            blockquote = ""
        else:
            blockquote = " ".join(blockquote.text.split())
        #print blockquote

        # Get the main? description
        description = soup.find("div", class_="race-content")
        if (description == None):
            description = ""
        else:
            description = description.text
        #print description

        # Get the race admin
        adminBlock = soup.find("div", style="font-size:0.9em; text-align:center;").find_all("a")
        admin = ""
        for a in adminBlock:
            if "/user/view/" in a["href"]:
                admin = a["href"].strip("/user/view/")
        #print admin

        # Get the race schedule if it is up
        # First navigate to the panel
        raceSchedulePane = soup.find("div", role="tabpanel", id="fullRaceSchedule")
        raceTabList = raceSchedulePane.div

        # Arrange each "round" div into a list
        rounds = raceTabList.contents[1::2]

        # Initialize a list to hold ALL THE DATAS
        raceStructure = []

        # For each round, get the heats
        for round in rounds:
            heats = round.find_all("div", class_="col-md-4")

            # Also a list to raceStructure that will hold all the heats for that round
            raceStructure.append([])
            
            # For each heat, get the list of racers
            for heat in heats:
                racers = heat.find_all("li", attrs={"class":None})

                # Also append a list to the current (last appended) "round" in raceStructure
                raceStructure[-1].append([])

                # For each racer, get their name and frequency and append it to the last "heat" in raceStructure
                # If there is actually a racer in that slot, they will have an anchor tag. Empty slots have no anchor
                # The website formatting is awful so we have to do a bit of string manipulation for the frequency
                # Also start a "Points" child
                for racer in racers:
                    if (racer.find("a", class_="strong")):
                        raceStructure[-1][-1].append({"name": racer.find("a", class_="strong").text, "frequency": " ".join(racer.find("div", class_="badge").text.split()), "points": "0"})
                    else:
                        raceStructure[-1][-1].append({"name": "EMPTY SLOT", "frequency": " ".join(racer.find("div", class_="badge").text.split()), "points": "0"})

        # Get a master list of all the current people who say they'll be there
        attendees = soup.find_all("div", class_="alternating-bg-list row")

        # Initialize a list to... uhhh.. hold ALL THE OTHER DATAS
        racerList = []

        # For each person, get their name, URL, image, quad name, quad url, frequency information, and points
        for person in attendees:
            rName = person.find("strong").find("a").text
            rURL = person.find("strong").find("a")["href"]
            rImage = person.find("img", title=rName)["src"]
            qName = person.find("div", class_="col-md-3 col-sm-2 col-xs-8").find("a").text
            qURL = person.find("div", class_="col-md-3 col-sm-2 col-xs-8").find("a")["href"]
            frequency = person.find("div", class_="badge")
            if (frequency == None):
                frequency = ""
            else:
                frequency = " ".join(frequency.text.split())
            points = person.find("div", class_="visible-xs").text.split()[0]
            racerList.append({"name": rName, "racerPage": rURL, "racerURL": rImage, "droneName": qName, "droneURL": qURL, "frequency": frequency, "points": points})

        # Make a status for the race
        status = {"status": "NS", "racing": "None", "spotting": "None", "ondeck": "None", "time": "123456789123"}

        # Let's build a json object!
        data = {}
        data["title"] = title
        data["date"] = date
        data["time"] = time
        data["eventURL"] = eventURL
        data["blockquote"] = blockquote
        data["description"] = description
        data["raceSchedule"] = raceStructure
        data["racerList"] = racerList
        data["status"] = status
        data["admins"] = {admin: True}
        
        return data

    def createRaceFromScrapedData(self, data):

        title = data["title"]
        date = data["date"]
        time = data["time"]
        eventURL = data["eventURL"]
        blockquote = data["blockquote"]
        description = data["description"]
        raceStructure = data["raceSchedule"]
        racerList = data["racerList"]
        status = data["status"]
        admin = data["admins"]

        # Firebase information - LETS REFACTOR ALL THE FIREBASE STUFF LATER (possibly do it all while accessing the information the first time)
        firebaseSecret = "mEFDPnrvKMXMV5gecJYGIfabRROmInyQxx1pKb64"
        firebaseRoot = "https://project-2848401830613063315.firebaseio.com/"

        # Connect to the Firebase database so that we can push the data to create the initial info needed for the races
        authentication = firebase.FirebaseAuthentication(firebaseSecret, "WHATRDOOOOSE")
        db = firebase.FirebaseApplication(firebaseRoot, authentication)

        # Prepare data to move to Firebase
        # We send off all the heat data first while also building up the json to later send the round data
        # Also getting racer data ready while we are there
        roundMessage = {}
        raceStructureMessage = {}
        usersMessage = {}
        eventUsersMessage = {}

        for racer in racerList:
            eventUsersMessage[racer["name"]] = {"frequency": racer["frequency"], "dronename": racer["droneName"], "droneURL": racer["droneURL"], "racerPage": racer["racerPage"], "racerPhoto": racer["racerURL"]}
            usersMessage[racer["name"]+"/"+"racerURL"] = racer["racerPage"]
            usersMessage[racer["name"]+"/"+"racerPhoto"] = racer["racerURL"]
            #usersMessage[racer["name"]] = {"racerURL": racer["racerPage"], "racerPhoto": racer["racerURL"], "events": {}}

        #for roundIndex, round in enumerate(raceStructure):
        #    roundMessage[roundIndex] = {}
        #    for heatIndex, heat in enumerate(round):
        #        heatMessage = {"index": heatIndex}
        #        for racerIndex, racer in enumerate(heat):
        #            letter = chr(racerIndex + 97)
        #            heatMessage[letter] = {"username": racer["name"], "frequency": racer["frequency"]}
        #            
        #        # Individually sending off each heat is probably not the smartest way to do this, since that's a connection for each
        #        heatId = db.post("/heats", heatMessage)
        #        roundMessage[roundIndex][heatId["name"]] = True

        for roundIndex, round in enumerate(raceStructure):
            raceStructureMessage[roundIndex] = {}
            for heatIndex, heat in enumerate(round):
                heatMessage = {}
                for racerIndex, racer in enumerate(heat):
                    letter = chr(racerIndex + 97)
                    heatMessage[letter] = {"username": racer["name"], "frequency": racer["frequency"], "points": racer["points"]}
                raceStructureMessage[roundIndex][heatIndex] = heatMessage
                
        # Now we should set up the actual race event
        eventMessage = {"eventURL": eventURL, "title": title, "date": date, "time": time, "blockquote": blockquote, "description": description, "racers": eventUsersMessage, "raceStructure": raceStructureMessage, "status": status, "admins": admin}

        # Push the event to Firebase and get the event ID
        eventId = db.post("/events", eventMessage)

        # Associate ID and URL
        db.patch(eventMessage["eventURL"].split(".com/").pop(), {"id": eventId["name"]})

        # We can now add update every racers profile so that they are registered to the event in the db
        for racer in racerList:
            usersMessage[racer["name"]+"/"+"events"+"/"+eventId["name"]] = True
            #usersMessage[user]["events"][eventId["name"]] = True
        db.patch("/users", usersMessage)
        return eventId["name"]

#curl -i -H "Content-Type: application/json" -X POST -d "{"""url""":"""http://www.multigp.com/races/view/2005/Texas-Regional-Qualifier---Houston"""}" http://localhost:5000/add/event
#curl -i -H "Content-Type: application/json" -X POST -d "{"""url""":"""http://www.multigp.com/races/view/2342/Texas-Regional-Qualifier-practice-race-3"""}" http://localhost:5000/add/event
#curl -i -H "Content-Type: application/json" -X POST -d "{"""url""":"""http://www.multigp.com/races/view/2240/Texas-Regional-Qualifier-practice-race-2"""}" http://localhost:5000/add/event
#curl -i -H "Content-Type: application/json" -X POST -d "{"""url""":"""http://www.multigp.com/races/view/2057/Lone-Star-Noobcake-Deluxe"""}" http://localhost:5000/add/event
#curl -i -H "Content-Type: application/json" -X POST -d "{"""url""":"""http://www.multigp.com/races/view/2344/Lone-Star-Ranch-Race"""}" http://localhost:5000/add/event

    def verifyLogin(self, email, password):
        tempBrowser = mechanize.Browser()
        # Setup cookies and browser
        #cj = cookielib.CookieJar()
        tempBrowser = mechanize.Browser()
        #browser.set_debug_http(True)
        #browser.set_debug_responses(True)
        #browser.set_cookiejar(cj)

        # Navigate to login and find the login form by iterating all formss
        tempBrowser.open(self.loginURL)
        for form in tempBrowser.forms():
            if form.attrs["id"] == "login-form":
                tempBrowser.form = form
                break

        # The login forms are implemented strange and mechanize does not seem to interact properly with the email text control
        # Solution is to add a new text control with the proper name ("LoginForm[username]") so that it can be sent in POST
        tempBrowser.form.new_control("text", "LoginForm[username]", {"value": ""})
        tempBrowser.form.fixup()
        tempBrowser["LoginForm[username]"] = email
        tempBrowser["LoginForm[password]"] = password
        response = tempBrowser.submit()
        tempSoup = BeautifulSoup(tempBrowser.response().read(), "html5lib")
        userFound = tempSoup.find("div", id="topbar").find("a", href="/user/user/myProfile")
        result = None
        if "Please fix the following input errors:" in response.read():
            result = None
        elif userFound == None:
            result = None
        else:
            result = userFound.text.strip()
        tempBrowser.close()
        return result


    def scrapeAttendance(self, eventURL):
        browser = self.browser
        browser.open(eventURL)
        soup = BeautifulSoup(browser.response().read(), "html5lib")

        # Get a master list of all the current people who say they'll be there
        attendees = soup.find_all("div", class_="alternating-bg-list row")
        racerList = []

        # For each person, get their name, URL, image, quad name, quad url, frequency information, and points
        for person in attendees:
            rName = person.find("strong").find("a").text
            rURL = person.find("strong").find("a")["href"]
            rImage = person.find("img", title=rName)["src"]
            qName = person.find("div", class_="col-md-3 col-sm-2 col-xs-8").find("a").text
            qURL = person.find("div", class_="col-md-3 col-sm-2 col-xs-8").find("a")["href"]
            frequency = person.find("div", class_="badge")
            if (frequency == None):
                frequency = ""
            else:
                frequency = " ".join(frequency.text.split())
            points = person.find("div", class_="visible-xs").text.split()[0]
            racerList.append({"name": rName, "racerPage": rURL, "racerURL": rImage, "droneName": qName, "droneURL": qURL, "frequency": frequency, "points": points})

        eventUsersMessage = {}

        for racer in racerList:
            eventUsersMessage[racer["name"]] = {"frequency": racer["frequency"], "dronename": racer["droneName"], "droneURL": racer["droneURL"], "racerPage": racer["racerPage"], "racerPhoto": racer["racerURL"]}

        return eventUsersMessage









        



