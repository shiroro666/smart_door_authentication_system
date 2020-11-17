import logging
import boto3
import json
from datetime import datetime
from botocore.exceptions import ClientError

def validate_passcode(faceID, passcode):
    db = boto3.resource('dynamodb')
    table = db.Table('passcodes')
    info = table.get_item(Key={'faceID': faceID})
    if 'Item' not in info:
        return "Sorry, your passcode may have expired."
    correct = info["Item"]["passcode"]
    curr = datetime.now().timestamp()
    guest_info = getGuest(faceID)
    name = ""
    if guest_info is not None:
        name = guest_info["Item"]["name"].replace("-"," ")
        name += "! "
    if passcode == correct and float(info["Item"]["validUntil"]) >= curr:
        return "Hello, " + name+ "Your passcode is correct! Welcome!"
    elif float(info["Item"]["validUntil"]) < curr:
        return "Sorry, your passcode have expired."
    else:
        return "Sorry, your passcode is not correct."
        
def getGuest(faceId):
    db = boto3.resource('dynamodb')
    table = db.Table('visitors')
    info = table.get_item(Key={'faceID': faceId})
    if 'Item' not in info:
        return None
    else:
        return info
        
def lambda_handler(event, context):
    message = "submitted"
    print(event)
    info = json.loads(event['body'])['messages'][0]["unstructured"]["text"].split(",")

    if len(info[1]) != 4 or not info[1].isdigit():
        message = "The OTP should be 4 digits!"
    #faceID = info[0]
    #passcode = info[1]
    else:
        message = validate_passcode(info[0], info[1])
    print(message)
    return {
        'headers':{
            'Access-Control-Allow-Origin': '*'
        },
        'statusCode': 200,
        'body': message
    }