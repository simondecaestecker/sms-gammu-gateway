import os

from flask import Flask, request
from flask_httpauth import HTTPBasicAuth
from flask_restful import reqparse, Api, Resource, abort

from waitress import serve

from support import load_user_data, init_state_machine, retrieveAllSms, deleteSms
from gammu import GSMNetworks, EncodeSMS

from datetime import datetime

from functions import checkDB, addSMS

pin = os.getenv('PIN', None)
ssl = os.getenv('SSL', False)
save = os.getenv('SAVE', False)
user_data = load_user_data()
machine = init_state_machine(pin)
app = Flask(__name__)
api = Api(app)
auth = HTTPBasicAuth()


@auth.verify_password
def verify(username, password):
    if not (username and password):
        return False
    return user_data.get(username) == password


class Sms(Resource):
    def __init__(self, sm):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('text')
        self.parser.add_argument('number')
        self.parser.add_argument('smsc')
        self.parser.add_argument('class')
        self.machine = sm

    @auth.login_required
    def get(self):
        allSms = retrieveAllSms(machine)
        list([sms.pop("Locations") for sms in allSms])
        return allSms

    @auth.login_required
    def post(self):
        args = self.parser.parse_args()
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
            addSMS("sent", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), number, args.get("text").replace("\n", "\\n").replace("\"", "\"\""), "", (args.get("class") if args.get("class") else ""), (args.get("smsc") if args.get("smsc") else ""))
        #####################################

        return {"status": 200, "message": str(result)}, 200


class Signal(Resource):
    def __init__(self, sm):
        self.machine = sm

    def get(self):
        return machine.GetSignalQuality()


class Reset(Resource):
    def __init__(self, sm):
        self.machine = sm

    def get(self):
        machine.Reset(False)
        return {"status":200, "message": "Reset done"}, 200


class Network(Resource):
    def __init__(self, sm):
        self.machine = sm

    def get(self):
        network = machine.GetNetworkInfo()
        network["NetworkName"] = GSMNetworks.get(network["NetworkCode"], 'Unknown')
        return network


class GetSms(Resource):
    def __init__(self, sm):
        self.machine = sm

    @auth.login_required
    def get(self):
        allSms = retrieveAllSms(machine)
        sms = {"Date": "", "Number": "", "State": "", "Text": ""}
        if len(allSms) > 0:
            sms = allSms[0]
            deleteSms(machine, sms)
            sms.pop("Locations")

        return sms


class SmsById(Resource):
    def __init__(self, sm):
        self.machine = sm

    @auth.login_required
    def get(self, id):
        allSms = retrieveAllSms(machine)
        self.abort_if_id_doesnt_exist(id, allSms)
        sms = allSms[id]
        sms.pop("Locations")
        return sms

    def delete(self, id):
        allSms = retrieveAllSms(machine)
        self.abort_if_id_doesnt_exist(id, allSms)
        deleteSms(machine, allSms[id])
        return '', 204

    def abort_if_id_doesnt_exist(self, id, allSms):
        if id < 0 or id >= len(allSms):
            abort(404, message = "Sms with id '{}' not found".format(id))

checkDB()
api.add_resource(Sms, '/sms', resource_class_args=[machine])
api.add_resource(SmsById, '/sms/<int:id>', resource_class_args=[machine])
api.add_resource(Signal, '/signal', resource_class_args=[machine])
api.add_resource(Network, '/network', resource_class_args=[machine])
api.add_resource(GetSms, '/getsms', resource_class_args=[machine])
api.add_resource(Reset, '/reset', resource_class_args=[machine])

if __name__ == '__main__':
    if ssl:
        app.run(port='5000', host="0.0.0.0", ssl_context=('/ssl/cert.pem', '/ssl/key.pem'))
    else:
        serve(app, host="0.0.0.0", port="5000", threads=1)
