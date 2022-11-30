#!/usr/bin/python3

import os, sqlite3, gammu, hashlib, random

from datetime import datetime

save = os.getenv('SAVE', False)


def createDB():
    print(" * SQLite 3 DB does not exists, creating DB...")
    conn = sqlite3.connect("/data/db.db")
    conn.execute("CREATE TABLE apikeys ( \
                	ID	INTEGER NOT NULL UNIQUE, \
                	apikey	TEXT NOT NULL UNIQUE, \
                	description	TEXT NOT NULL, \
                	created	TEXT NOT NULL, \
                	enabled	INTEGER NOT NULL DEFAULT 1, \
                	sms_post	INTEGER NOT NULL DEFAULT 0, \
                	sms_get	INTEGER NOT NULL DEFAULT 0, \
                	signal	INTEGER NOT NULL DEFAULT 0, \
                	network	INTEGER NOT NULL DEFAULT 0, \
                	reset	INTEGER NOT NULL DEFAULT 0, \
                	PRIMARY KEY(ID AUTOINCREMENT) );")
    conn.execute("CREATE TABLE sent ( \
                	ID	INTEGER NOT NULL UNIQUE, \
                	sent	TEXT NOT NULL, \
                	number	TEXT NOT NULL, \
                	text	TEXT NOT NULL, \
                	smsc	TEXT, \
                	class	INTEGER NOT NULL DEFAULT 1, \
                    apikey	TEXT NOT NULL, \
                	PRIMARY KEY(ID AUTOINCREMENT) );")
    conn.execute("CREATE TABLE received ( \
                	ID	INTEGER NOT NULL UNIQUE, \
                	received	TEXT NOT NULL, \
                    read	TEXT NOT NULL, \
                	number	TEXT NOT NULL, \
                	text	TEXT NOT NULL, \
                    apikey	TEXT NOT NULL, \
                	PRIMARY KEY(ID AUTOINCREMENT) );")
    conn.close()


def addSMS(type="", datetime="", number="", text="", apikey="", smsclass="", smsc="", datetime2=""):
    if type not in ["sent", "received"] or len(datetime) == 0 or len(number) == 0 or len(text) == 0:
        return False
    if type == "received" and len(datetime2) == 0:
        return False

    conn = sqlite3.connect("/data/db.db")
    if type == "sent":
        conn.execute("INSERT INTO sent (sent, number, text, smsc, class, apikey) \
                        VALUES (?, ?, ?, ?, ?, ?)", (datetime, number, text, smsc, smsclass, apikey));
    elif type == "received":
        conn.execute("INSERT INTO received (received, read, number, text, apikey) \
                        VALUES (?, ?, ?, ?, ?)", (datetime, datetime2, number, text, apikey));
    conn.commit()
    conn.close()

    return True


def csvToDB(type=""):
    if type not in ["sent", "received"]:
        return False

    filename = type + ".csv"
    print(" * " + filename + " file found, moving data to SQLite 3 DB...")

    file = open("/data/" + filename, "r")
    for line in file:
        data = line.split(";")
        if type == "sent":
            addSMS(type, data[0], data[1], data[2][1:-1], "", data[4].replace("\n", ""), data[3])
        elif type == "received":
            addSMS(type, data[0], data[2], data[3].replace("\n", "")[1:-1], "", "", "", data[1])
    file.close()

    return True


def checkDB():
    print(" * Checking if SQLite3 DB exists...")
    if os.path.isfile("/data/db.db") == False:
        createDB()
    print(" * Checking if there is an existing sent.csv file...")
    if os.path.isfile("/data/sent.csv"):
        csvToDB("sent")
        os.remove("/data/sent.csv")
    print(" * Checking if there is an existing received.csv file...")
    if os.path.isfile("/data/received.csv"):
        csvToDB("received")
        os.remove("/data/received.csv")


def init_state_machine(pin, filename='gammu.config'):
    sm = gammu.StateMachine()
    sm.ReadConfig(Filename=filename)
    sm.Init()

    if sm.GetSecurityStatus() == 'PIN':
        if pin is None or pin == '':
            print("PIN is required.")
            sys.exit(1)
        else:
            sm.EnterSecurityCode('PIN', pin)
    return sm


def retrieveAllSms(machine, apikey=""):
    status = machine.GetSMSStatus()
    allMultiPartSmsCount = status['SIMUsed'] + status['PhoneUsed'] + status['TemplatesUsed']

    allMultiPartSms = []
    start = True

    while len(allMultiPartSms) < allMultiPartSmsCount:
        if start:
            currentMultiPartSms = machine.GetNextSMS(Start = True, Folder = 0)
            start = False
        else:
            currentMultiPartSms = machine.GetNextSMS(Location = currentMultiPartSms[0]['Location'], Folder = 0)
        allMultiPartSms.append(currentMultiPartSms)

    allSms = gammu.LinkSMS(allMultiPartSms)

    results = []
    for sms in allSms:
        smsPart = sms[0]

        result = {
            "Date": str(smsPart['DateTime']),
            "Number": smsPart['Number'],
            "State": smsPart['State'],
            "Locations": [smsPart['Location'] for smsPart in sms],
        }

        decodedSms = gammu.DecodeSMS(sms)
        if decodedSms == None:
            result["Text"] = smsPart['Text']
        else:
            text = ""
            for entry in decodedSms['Entries']:
                if entry['Buffer'] != None:
                    text += entry['Buffer']

            result["Text"] = text

        results.append(result)

        # Save list of received messages in the SQLite 3 DB
        if save and result["State"] == "UnRead" :
          addSMS("received", result["Date"], result["Number"], (result["Text"].replace("\n", "\\n").replace("\"", "\"\"") if result["Text"] else ""), apikey, "", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        #####################################

    return results


def deleteSms(machine, sms):
    list([machine.DeleteSMS(Folder=0, Location=location) for location in sms["Locations"]])


def createApikey(description="No description"):
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    apikey = hashlib.md5((created + str(random.random())).encode()).hexdigest()

    conn = sqlite3.connect("/data/db.db")
    conn.execute("INSERT INTO apikeys (apikey, description, created) \
                    VALUES (?, ?, ?)", (apikey, description, created));
    conn.commit()
    conn.close()

    return apikey


def getApikey(apikey=""):
    if len(apikey) == 0:
        return False

    conn = sqlite3.connect("/data/db.db")
    select = conn.execute("SELECT * FROM apikeys \
                            WHERE apikey = ?", (apikey,));
    data = select.fetchall()
    conn.close()

    if len(data) == 0:
    	return False
    else:
    	return data[0]


def getApikeys():
    conn = sqlite3.connect("/data/db.db")
    select = conn.execute("SELECT * FROM apikeys");
    data = select.fetchall()
    conn.close()

    if len(data) == 0:
    	return False
    else:
    	return data


def parseApikeyJSON(data=""):
    if data is False or len(data) == 0:
        return False

    data_json = {
        "apikey": data[1],
        "description": data[2],
        "created": data[3],
        "enabled": str(data[4]),
        "permissions": {
            "sms_post": str(data[5]),
            "sms_get": str(data[6]),
            "signal": str(data[7]),
            "network": str(data[8]),
            "reset": str(data[9])
        }
    }

    return data_json


def getPermissions(apikey="", function=""):
    functions = ["sms_post", "sms_get", "signal", "network", "reset"]
    if len(apikey) == 0 or function not in functions:
        return False

    conn = sqlite3.connect("/data/db.db")
    select = conn.execute("SELECT %s FROM apikeys \
                            WHERE enabled = 1 and apikey = ?" % (function), (apikey,));
    data = select.fetchall()
    conn.close()

    if len(data) == 0 or data[0][0] != 1:
    	return False
    else:
    	return True


def setPermissions(apikey="", function="", value=""):
    functions = ["sms_post", "sms_get", "signal", "network", "reset"]
    if len(apikey) == 0 or function not in functions or value not in [0, 1]:
        return False

    if getApikey(apikey) is False:
        return False

    conn = sqlite3.connect("/data/db.db")
    conn.execute("UPDATE apikeys SET %s = ? \
                    WHERE apikey = ?" % (function), (value, apikey,));
    conn.commit()
    conn.close()

    return True


def getHistory(type="", offset="0", limit="10", apikey="%"):
    if type not in ["sent", "received"]:
        return []

    if (offset is not None and offset.isnumeric() == False) or (limit is not None and limit.isnumeric() == False):
        return []

    if offset is None:
        offset = "0"
    if limit is None:
        limit = "10"

    conn = sqlite3.connect("/data/db.db")
    select = conn.execute("SELECT * FROM %s WHERE apikey LIKE '%s' ORDER BY id DESC LIMIT %s,%s" % (type, apikey, offset, limit));
    data = select.fetchall()
    conn.close()

    return data


def parseSentJSON(data=""):
    if len(data) == 0:
        False

    data_json = {
        "sent": data[1],
        "number": data[2],
        "text": data[3],
        "smsc": data[4],
        "class": data[5],
        "apikey": data[6]
    }

    return data_json


def parseReceivedJSON(data=""):
    if len(data) == 0:
        False

    data_json = {
        "received": data[1],
        "read": data[2],
        "number": data[3],
        "text": data[4],
        "apikey": data[5]
    }

    return data_json
