#!/usr/bin/python3

import os, sqlite3

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
