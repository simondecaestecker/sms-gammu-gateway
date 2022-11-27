#!/usr/bin/python3

import os

from flask import Flask, request
from flask_restful import reqparse, Api, Resource, abort

from waitress import serve

from gammu import GSMNetworks, EncodeSMS

from datetime import datetime

from functions import checkDB, addSMS, init_state_machine, retrieveAllSms, deleteSms, createApikey, getApikey, getApikeys, parseApikeyJSON, getPermissions, setPermissions

pin = os.getenv('PIN', None)
ssl = os.getenv('SSL', False)
save = os.getenv('SAVE', False)
admin_password = os.getenv('ADMIN_PASSWORD', None)
machine = init_state_machine(pin)
app = Flask(__name__)
api = Api(app)


class Sms(Resource):
    def __init__(self, sm):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('X-API-Key', location='headers', required='True')
        self.machine = sm

    def get(self):
        args = self.parser.parse_args()
        if getPermissions(args["X-API-Key"], "sms_get") == False:
            return {"status": 403, "message": "Unauthorized"}, 403

        allSms = retrieveAllSms(machine, args["X-API-Key"])
        list([sms.pop("Locations") for sms in allSms])
        return allSms

    def post(self):
        self.parser.add_argument('text')
        self.parser.add_argument('number')
        self.parser.add_argument('smsc')
        self.parser.add_argument('class')
        args = self.parser.parse_args()
        if getPermissions(args["X-API-Key"], "sms_post") == False:
            return {"status": 403, "message": "Unauthorized"}, 403

        if args['text'] is None or args['number'] is None:
            abort(404, message="Parameters 'text' and 'number' are required.")
        if len(args.get("text")) > 70:
          smsinfo = {
              "Class": -1,
              "Unicode": True,
              "Entries": [
                {
                  "ID": "ConcatenatedTextLong",
                  "Buffer": args.get("text"),
                }
              ],
          }
          encoded = EncodeSMS(smsinfo)
          for message in encoded:
            for number in args.get("number").split(','):
              message['SMSC'] = {'Number': args.get("smsc")} if args.get("smsc") else {'Location': 1}
              message["Number"] = number
              result = machine.SendSMS(message)
        else:
          result = [machine.SendSMS({
            'Text': args.get("text"),
            'SMSC': {'Number': args.get("smsc")} if args.get("smsc") else {'Location': 1},
            'Class': args.get("class") if args.get("class") else 1,
            'Number': number,
            'Coding': 'Unicode_No_Compression',
          }) for number in args.get("number").split(',')]

        # Save list of sent messages in the SQLite 3 DB
        if save:
          for number in args.get("number").split(','):
            addSMS("sent", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), number, args.get("text").replace("\n", "\\n").replace("\"", "\"\""), args["X-API-Key"], (args.get("class") if args.get("class") else ""), (args.get("smsc") if args.get("smsc") else ""))
        #####################################

        return {"status": 200, "message": str(result)}, 200


class Signal(Resource):
    def __init__(self, sm):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('X-API-Key', location='headers', required='True')
        self.machine = sm

    def get(self):
        args = self.parser.parse_args()
        if getPermissions(args["X-API-Key"], "signal") == False:
            return {"status": 403, "message": "Unauthorized"}, 403

        return machine.GetSignalQuality()


class Reset(Resource):
    def __init__(self, sm):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('X-API-Key', location='headers', required='True')
        self.machine = sm

    def get(self):
        args = self.parser.parse_args()
        if getPermissions(args["X-API-Key"], "reset") == False:
            return {"status": 403, "message": "Unauthorized"}, 403

        machine.Reset(False)
        return {"status":200, "message": "Reset done"}, 200


class Network(Resource):
    def __init__(self, sm):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('X-API-Key', location='headers', required='True')
        self.machine = sm

    def get(self):
        args = self.parser.parse_args()
        if getPermissions(args["X-API-Key"], "network") == False:
            return {"status": 403, "message": "Unauthorized"}, 403

        network = machine.GetNetworkInfo()
        network["NetworkName"] = GSMNetworks.get(network["NetworkCode"], 'Unknown')
        return network


class GetSms(Resource):
    def __init__(self, sm):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('X-API-Key', location='headers', required='True')
        self.machine = sm

    def get(self):
        args = self.parser.parse_args()
        if getPermissions(args["X-API-Key"], "sms_get") == False:
            return {"status": 403, "message": "Unauthorized"}, 403

        allSms = retrieveAllSms(machine, args["X-API-Key"])
        sms = {"Date": "", "Number": "", "State": "", "Text": ""}
        if len(allSms) > 0:
            sms = allSms[0]
            deleteSms(machine, sms)
            sms.pop("Locations")

        return sms


class SmsById(Resource):
    def __init__(self, sm):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('X-API-Key', location='headers', required='True')
        self.machine = sm

    def get(self, id):
        args = self.parser.parse_args()
        if getPermissions(args["X-API-Key"], "sms_get") == False:
            return {"status": 403, "message": "Unauthorized"}, 403

        allSms = retrieveAllSms(machine, args["X-API-Key"])
        self.abort_if_id_doesnt_exist(id, allSms)
        sms = allSms[id]
        sms.pop("Locations")
        return sms

    def delete(self, id):
        args = self.parser.parse_args()
        if getPermissions(args["X-API-Key"], "sms_get") == False:
            return {"status": 403, "message": "Unauthorized"}, 403

        allSms = retrieveAllSms(machine, args["X-API-Key"])
        self.abort_if_id_doesnt_exist(id, allSms)
        deleteSms(machine, allSms[id])
        return '', 204

    def abort_if_id_doesnt_exist(self, id, allSms):
        if id < 0 or id >= len(allSms):
            abort(404, message = "Sms with id '{}' not found".format(id))


class AdminApikeys(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('X-Admin-Password', location='headers', required='True')

    def get(self):
        args = self.parser.parse_args()
        if args["X-Admin-Password"] != admin_password:
            return {"status": 403, "message": "Unauthorized"}, 403

        data = getApikeys()
        data_json = {}
        if data is False:
            return {"status": 200, "message": data_json}, 200

        i = 0
        for apikey in getApikeys():
            data_json[i] = parseApikeyJSON(apikey)
            i += 1

        return {"status": 200, "message": data_json}, 200


class AdminApikey(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('X-Admin-Password', location='headers', required='True')

    def post(self):
        self.parser.add_argument('description')
        args = self.parser.parse_args()
        if args["X-Admin-Password"] != admin_password:
            return {"status": 403, "message": "Unauthorized"}, 403

        apikey = createApikey(args["description"])

        if len(apikey) != 32:
            return {"status": 500, "message": "Internal Server Error"}, 500

        return {"status": 200, "message": "New API key created: " + apikey}, 200


class AdminApikeyByApikey(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('X-Admin-Password', location='headers', required='True')

    def get(self, apikey):
        args = self.parser.parse_args()
        if args["X-Admin-Password"] != admin_password:
            return {"status": 403, "message": "Unauthorized"}, 403

        return {"status": 200, "message": parseApikeyJSON(getApikey(apikey))}, 200

    def put(self, apikey):
        self.parser.add_argument('sms_post')
        self.parser.add_argument('sms_get')
        self.parser.add_argument('signal')
        self.parser.add_argument('network')
        self.parser.add_argument('reset')
        args = self.parser.parse_args()
        if args["X-Admin-Password"] != admin_password:
            return {"status": 403, "message": "Unauthorized"}, 403

        i = 0
        for function in ["sms_post", "sms_get", "signal", "network", "reset"]:
            if args[function] is not None:
                if int(args[function]) in [0, 1] :
                    if setPermissions(apikey, function, int(args[function])):
                        i += 1

        if i == 0:
            return {"status": 200, "message": "No permissions update for API key " + apikey}, 200

        return {"status": 200, "message": "Permissions updated for API key " + apikey}, 200


if admin_password is None:
    print(" * No admin password configured")
else:
    admin_password = str(admin_password)[1:-1]
    checkDB()
    api.add_resource(Sms, '/sms', resource_class_args=[machine])
    api.add_resource(SmsById, '/sms/<int:id>', resource_class_args=[machine])
    api.add_resource(Signal, '/signal', resource_class_args=[machine])
    api.add_resource(Network, '/network', resource_class_args=[machine])
    api.add_resource(GetSms, '/getsms', resource_class_args=[machine])
    api.add_resource(Reset, '/reset', resource_class_args=[machine])
    api.add_resource(AdminApikeys, '/admin/apikeys')
    api.add_resource(AdminApikey, '/admin/apikey')
    api.add_resource(AdminApikeyByApikey, '/admin/apikey/<apikey>')

    if __name__ == '__main__':
        if ssl:
            app.run(port='5000', host="0.0.0.0", ssl_context=('/ssl/cert.pem', '/ssl/key.pem'))
        else:
            serve(app, host="0.0.0.0", port="5000", threads=1)
